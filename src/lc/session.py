"""Session manager for coordinating LeetCode authentication."""

from lc.client import LeetCodeClient
from lc.cookies import get_chrome_cookies
from lc.exceptions import CookieError
from lc.storage import Storage


class SessionManager:
    """Coordinates authentication and provides authenticated LeetCode clients."""

    def __init__(self, storage: Storage | None = None) -> None:
        self._storage = storage or Storage()

    def get_client(self) -> LeetCodeClient:
        """Return an authenticated LeetCode client using Chrome cookies."""
        config = self._storage.get_config()

        try:
            session_token, csrf_token = get_chrome_cookies(config.profile)
        except CookieError as e:
            raise CookieError(
                f"Failed to read cookies from Chrome: {e.message}. "
                "Please ensure Chrome is installed and you're logged into leetcode.com."
            ) from e

        return LeetCodeClient(session_token, csrf_token)
