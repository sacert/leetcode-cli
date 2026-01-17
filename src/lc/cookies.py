"""Read LeetCode session cookies from Chrome's cookie store on Linux."""

import hashlib
import shutil
import sqlite3
import tempfile
from pathlib import Path

from Crypto.Cipher import AES

from lc.exceptions import CookieError


def get_chrome_cookies(profile: str = "Default") -> tuple[str, str]:
    """Read LeetCode session cookies from Chrome's cookie store."""
    cookie_path = Path.home() / ".config/google-chrome" / profile / "Network/Cookies"

    if not cookie_path.exists():
        raise CookieError(f"Chrome cookie database not found at {cookie_path}")

    encryption_key = _derive_encryption_key()
    cookies = _read_cookies_from_db(cookie_path, encryption_key)

    leetcode_session = cookies.get("LEETCODE_SESSION")
    csrf_token = cookies.get("csrftoken")

    if not leetcode_session:
        raise CookieError("LEETCODE_SESSION cookie not found. Please login to leetcode.com in Chrome.")

    if not csrf_token:
        raise CookieError("csrftoken cookie not found. Please login to leetcode.com in Chrome.")

    return leetcode_session, csrf_token


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
