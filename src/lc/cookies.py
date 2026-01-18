"""Read LeetCode session cookies from Chrome's cookie store on Linux/WSL."""

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

from Crypto.Cipher import AES

from lc.exceptions import CookieError

# Path to manual credentials file
CREDENTIALS_FILE = Path.home() / ".leetcode" / "credentials.json"


def _get_manual_cookies() -> tuple[str, str] | None:
    """Check for manually configured cookies (env vars or credentials file)."""
    # Check environment variables first
    session = os.environ.get("LEETCODE_SESSION")
    csrf = os.environ.get("LEETCODE_CSRF")
    if session and csrf:
        return session, csrf

    # Check credentials file
    if CREDENTIALS_FILE.exists():
        try:
            with open(CREDENTIALS_FILE, "r") as f:
                creds = json.load(f)
            session = creds.get("leetcode_session")
            csrf = creds.get("csrf_token")
            if session and csrf:
                return session, csrf
        except (json.JSONDecodeError, IOError):
            pass

    return None


def _is_wsl() -> bool:
    """Detect if running in Windows Subsystem for Linux."""
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower()
    except FileNotFoundError:
        return False


def _get_windows_username() -> str | None:
    """Get Windows username when running in WSL."""
    try:
        import subprocess
        result = subprocess.run(
            ["cmd.exe", "/c", "echo %USERNAME%"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        username = result.stdout.strip()
        if username and username != "%USERNAME%":
            return username
    except Exception:
        pass
    return None


def _find_chrome_cookie_path(profile: str = "Default") -> Path:
    """Find Chrome cookie database path, supporting both Linux and WSL."""
    # Try Linux path first
    linux_path = Path.home() / ".config/google-chrome" / profile / "Network/Cookies"
    if linux_path.exists():
        return linux_path

    # Check if we're in WSL and try Windows path
    if _is_wsl():
        win_username = _get_windows_username()
        if win_username:
            # Try standard Windows Chrome path
            win_path = Path(f"/mnt/c/Users/{win_username}/AppData/Local/Google/Chrome/User Data/{profile}/Network/Cookies")
            if win_path.exists():
                return win_path

        # Try to find Chrome in common locations
        for user_dir in Path("/mnt/c/Users").iterdir():
            if user_dir.is_dir() and user_dir.name not in ("Public", "Default", "Default User", "All Users"):
                candidate = user_dir / f"AppData/Local/Google/Chrome/User Data/{profile}/Network/Cookies"
                if candidate.exists():
                    return candidate

    raise CookieError(
        f"Chrome cookie database not found. Searched:\n"
        f"  - {linux_path}\n"
        + (f"  - /mnt/c/Users/<username>/AppData/Local/Google/Chrome/User Data/{profile}/Network/Cookies\n" if _is_wsl() else "")
        + "Please ensure Chrome is installed and you're logged into leetcode.com."
    )


def get_chrome_cookies(profile: str = "Default") -> tuple[str, str]:
    """Read LeetCode session cookies from Chrome's cookie store or manual config."""
    # Check for manual cookies first (env vars or credentials file)
    manual = _get_manual_cookies()
    if manual:
        return manual

    # Try to read from Chrome
    try:
        cookie_path = _find_chrome_cookie_path(profile)
    except CookieError:
        raise CookieError(
            "Chrome cookies not found and no manual credentials configured.\n\n"
            "To set up manually, create ~/.leetcode/credentials.json:\n"
            '{\n'
            '  "leetcode_session": "your_session_cookie",\n'
            '  "csrf_token": "your_csrf_token"\n'
            '}\n\n'
            "Get these values from Chrome DevTools (F12) → Application → Cookies → leetcode.com"
        )

    is_windows_chrome = str(cookie_path).startswith("/mnt/")

    try:
        if is_windows_chrome:
            cookies = _read_windows_chrome_cookies(cookie_path, profile)
        else:
            encryption_key = _derive_encryption_key()
            cookies = _read_cookies_from_db(cookie_path, encryption_key)
    except CookieError:
        raise CookieError(
            "Cannot read Chrome cookies (database may be locked).\n\n"
            "Options:\n"
            "1. Close Chrome completely and retry\n"
            "2. Set up manual credentials in ~/.leetcode/credentials.json:\n"
            '   {\n'
            '     "leetcode_session": "your_session_cookie",\n'
            '     "csrf_token": "your_csrf_token"\n'
            '   }\n\n'
            "Get these values from Chrome DevTools (F12) → Application → Cookies → leetcode.com"
        )

    leetcode_session = cookies.get("LEETCODE_SESSION")
    csrf_token = cookies.get("csrftoken")

    if not leetcode_session or not csrf_token:
        raise CookieError(
            "LeetCode cookies not found in Chrome.\n\n"
            "Please login to leetcode.com in Chrome, or set up manual credentials:\n"
            "~/.leetcode/credentials.json:\n"
            '{\n'
            '  "leetcode_session": "your_session_cookie",\n'
            '  "csrf_token": "your_csrf_token"\n'
            '}\n\n'
            "Get these values from Chrome DevTools (F12) → Application → Cookies → leetcode.com"
        )

    return leetcode_session, csrf_token


def _read_windows_chrome_cookies(cookie_path: Path, profile: str) -> dict[str, str]:
    """Read cookies from Windows Chrome using PowerShell for DPAPI decryption."""
    import base64
    import json
    import subprocess

    # Find Local State file (contains the encryption key)
    chrome_user_data = cookie_path.parent.parent.parent
    local_state_path = chrome_user_data / "Local State"

    if not local_state_path.exists():
        raise CookieError(f"Chrome Local State not found at {local_state_path}")

    # Read the encrypted key from Local State
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)

    encrypted_key_b64 = local_state.get("os_crypt", {}).get("encrypted_key")
    if not encrypted_key_b64:
        raise CookieError("Could not find encrypted key in Chrome Local State")

    # The key is base64 encoded and prefixed with "DPAPI"
    encrypted_key = base64.b64decode(encrypted_key_b64)
    if encrypted_key[:5] != b"DPAPI":
        raise CookieError("Unexpected key format in Chrome Local State")

    encrypted_key = encrypted_key[5:]  # Remove DPAPI prefix

    # Use PowerShell to decrypt the key using DPAPI
    key_b64 = base64.b64encode(encrypted_key).decode()
    ps_script = f'''
    Add-Type -AssemblyName System.Security
    $encrypted = [Convert]::FromBase64String("{key_b64}")
    $decrypted = [Security.Cryptography.ProtectedData]::Unprotect($encrypted, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
    [Convert]::ToBase64String($decrypted)
    '''

    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise CookieError(f"PowerShell decryption failed: {result.stderr}")

        decryption_key = base64.b64decode(result.stdout.strip())
    except FileNotFoundError:
        raise CookieError(
            "PowerShell not available. WSL requires PowerShell to decrypt Windows Chrome cookies.\n"
            "Ensure PowerShell is accessible from WSL."
        )
    except subprocess.TimeoutExpired:
        raise CookieError("PowerShell decryption timed out")

    # Now read and decrypt the cookies using AES-GCM
    return _read_cookies_from_db_windows(cookie_path, decryption_key)


def _wsl_to_windows_path(wsl_path: Path) -> str:
    """Convert WSL path to Windows path."""
    path_str = str(wsl_path)
    if path_str.startswith("/mnt/"):
        drive_letter = path_str[5].upper()
        return f"{drive_letter}:{path_str[6:]}".replace("/", "\\")
    return path_str.replace("/", "\\")


def _copy_windows_file(src: Path, dst: Path) -> None:
    """Copy a file using Windows commands to handle locked files."""
    import subprocess

    src_win = _wsl_to_windows_path(src)
    dst_win = _wsl_to_windows_path(dst)

    # Try multiple methods to copy the locked file

    # Method 1: Try PowerShell with file stream (can read locked files)
    ps_script = f'''
    try {{
        $source = [System.IO.File]::Open("{src_win}", [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        $dest = [System.IO.File]::Create("{dst_win}")
        $source.CopyTo($dest)
        $dest.Close()
        $source.Close()
        "SUCCESS"
    }} catch {{
        $_.Exception.Message
    }}
    '''

    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", ps_script],
        capture_output=True,
        text=True,
        timeout=10,
    )

    if "SUCCESS" in result.stdout:
        return

    # Method 2: Try simple copy
    ps_simple = f'Copy-Item -Path "{src_win}" -Destination "{dst_win}" -Force'
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", ps_simple],
        capture_output=True,
        text=True,
        timeout=10,
    )

    if result.returncode == 0:
        return

    raise CookieError(
        "Cannot read Chrome cookies - the database is locked.\n"
        "Please close Chrome completely and try again."
    )


def _read_cookies_from_db_windows(cookie_path: Path, key: bytes) -> dict[str, str]:
    """Read cookies from Windows Chrome database using AES-GCM decryption."""
    # Try Method 1: Connect directly with immutable mode (bypasses locks)
    try:
        # SQLite URI with immutable=1 opens in read-only mode without locking
        db_uri = f"file:{cookie_path}?immutable=1"
        conn = sqlite3.connect(db_uri, uri=True)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name, encrypted_value FROM cookies WHERE host_key = '.leetcode.com' AND name IN (?, ?)",
            ("LEETCODE_SESSION", "csrftoken"),
        )

        cookies: dict[str, str] = {}
        for name, encrypted_value in cursor.fetchall():
            if encrypted_value:
                decrypted = _decrypt_windows_cookie(encrypted_value, key)
                if decrypted:
                    cookies[name] = decrypted

        conn.close()

        if cookies:
            return cookies
    except sqlite3.OperationalError:
        pass  # Fall through to copy method

    # Method 2: Copy to temp file and read
    import subprocess

    result = subprocess.run(
        ["cmd.exe", "/c", "echo %TEMP%"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    win_temp = result.stdout.strip()

    if win_temp and "%" not in win_temp:
        drive = win_temp[0].lower()
        wsl_temp = f"/mnt/{drive}{win_temp[2:].replace(chr(92), '/')}"
        tmp_path = Path(wsl_temp) / f"lc_cookies_{id(key)}.db"
    else:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp_file:
            tmp_path = Path(tmp_file.name)

    try:
        _copy_windows_file(cookie_path, tmp_path)

        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name, encrypted_value FROM cookies WHERE host_key = '.leetcode.com' AND name IN (?, ?)",
            ("LEETCODE_SESSION", "csrftoken"),
        )

        cookies: dict[str, str] = {}
        for name, encrypted_value in cursor.fetchall():
            if encrypted_value:
                decrypted = _decrypt_windows_cookie(encrypted_value, key)
                if decrypted:
                    cookies[name] = decrypted

        conn.close()
        return cookies
    finally:
        tmp_path.unlink(missing_ok=True)


def _decrypt_windows_cookie(encrypted_value: bytes, key: bytes) -> str | None:
    """Decrypt a Windows Chrome cookie using AES-GCM."""
    try:
        # Windows Chrome uses v10 prefix followed by 12-byte nonce, ciphertext, and 16-byte tag
        if encrypted_value[:3] != b"v10":
            # Might be unencrypted
            return encrypted_value.decode("utf-8", errors="ignore")

        nonce = encrypted_value[3:15]
        ciphertext_with_tag = encrypted_value[15:]

        from Crypto.Cipher import AES as AES_GCM

        cipher = AES_GCM.new(key, AES_GCM.MODE_GCM, nonce=nonce)
        # Last 16 bytes are the auth tag
        ciphertext = ciphertext_with_tag[:-16]
        tag = ciphertext_with_tag[-16:]

        decrypted = cipher.decrypt_and_verify(ciphertext, tag)
        return decrypted.decode("utf-8")
    except Exception:
        return None


def _derive_encryption_key() -> bytes:
    password = _get_keyring_password() or b"peanuts"
    return hashlib.pbkdf2_hmac(
        hash_name="sha1",
        password=password,
        salt=b"saltysalt",
        iterations=1,
        dklen=16,
    )


def _get_keyring_password() -> bytes | None:
    try:
        import secretstorage

        connection = secretstorage.dbus_init()
        collection = secretstorage.get_default_collection(connection)

        if collection.is_locked():
            collection.unlock()

        for item in collection.get_all_items():
            if item.get_label() == "Chrome Safe Storage":
                return item.get_secret()
    except Exception:
        pass

    return None


def _read_cookies_from_db(cookie_path: Path, encryption_key: bytes) -> dict[str, str]:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        shutil.copy2(cookie_path, tmp_path)

        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name, encrypted_value FROM cookies WHERE host_key = '.leetcode.com' AND name IN (?, ?)",
            ("LEETCODE_SESSION", "csrftoken"),
        )

        cookies: dict[str, str] = {}
        for name, encrypted_value in cursor.fetchall():
            if encrypted_value:
                decrypted = _decrypt_cookie_value(encrypted_value, encryption_key)
                if decrypted:
                    cookies[name] = decrypted

        conn.close()
        return cookies
    finally:
        tmp_path.unlink(missing_ok=True)


def _decrypt_cookie_value(encrypted_value: bytes, key: bytes) -> str | None:
    if encrypted_value[:3] in (b"v10", b"v11"):
        encrypted_value = encrypted_value[3:]
    else:
        return encrypted_value.decode("utf-8", errors="ignore")

    if len(encrypted_value) < 16:
        return None

    try:
        iv = b" " * 16
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(encrypted_value)
        decrypted = _remove_pkcs7_padding(decrypted)
        return decrypted.decode("utf-8")
    except Exception:
        return None


def _remove_pkcs7_padding(data: bytes) -> bytes:
    if not data:
        return data

    padding_length = data[-1]

    if padding_length > 16 or padding_length == 0:
        return data

    if data[-padding_length:] != bytes([padding_length]) * padding_length:
        return data

    return data[:-padding_length]
