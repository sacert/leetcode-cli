"""Tests for session management in SessionManager."""

import unittest
from unittest.mock import MagicMock, patch

from lc.client import LeetCodeClient
from lc.exceptions import CookieError
from lc.models import Config
from lc.session import SessionManager
from lc.storage import Storage


class TestSessionManagerGetClient(unittest.TestCase):
    """Tests for SessionManager.get_client() method."""

    @patch("lc.session.LeetCodeClient")
    @patch("lc.session.get_chrome_cookies")
    def test_get_client_returns_authenticated_client_with_mocked_cookies(
        self, mock_get_cookies, mock_client_class
    ):
        """Test successful client creation with mocked cookies."""
        # Arrange
        fake_session_token = "fake_session_token_12345"
        fake_csrf_token = "fake_csrf_token_67890"
        mock_get_cookies.return_value = (fake_session_token, fake_csrf_token)

        mock_storage = MagicMock(spec=Storage)
        mock_storage.get_config.return_value = Config(
            language="python3",
            editor="vim",
            browser="chrome",
            profile="Default",
        )

        mock_client_instance = MagicMock(spec=LeetCodeClient)
        mock_client_class.return_value = mock_client_instance

        session_manager = SessionManager(storage=mock_storage)

        # Act
        client = session_manager.get_client()

        # Assert
        mock_storage.get_config.assert_called_once()
        mock_get_cookies.assert_called_once_with("Default")
        mock_client_class.assert_called_once_with(fake_session_token, fake_csrf_token)
        self.assertEqual(client, mock_client_instance)

    @patch("lc.session.get_chrome_cookies")
    def test_get_client_catches_cookie_error_and_reraises_with_user_friendly_message(
        self, mock_get_cookies
    ):
        """Test CookieError is caught and re-raised with user-friendly message."""
        # Arrange
        original_error_message = "Cookie database not found"
        mock_get_cookies.side_effect = CookieError(original_error_message)

        mock_storage = MagicMock(spec=Storage)
        mock_storage.get_config.return_value = Config(
            language="python3",
            editor="vim",
            browser="chrome",
            profile="Default",
        )

        session_manager = SessionManager(storage=mock_storage)

        # Act & Assert
        with self.assertRaises(CookieError) as context:
            session_manager.get_client()

        # Verify the error message is user-friendly and contains helpful information
        error_message = context.exception.message
        self.assertIn("Failed to read cookies from Chrome", error_message)
        self.assertIn(original_error_message, error_message)
        self.assertIn("Please ensure Chrome is installed", error_message)
        self.assertIn("logged into leetcode.com", error_message)

    @patch("lc.session.LeetCodeClient")
    @patch("lc.session.get_chrome_cookies")
    def test_get_client_uses_correct_profile_from_config(
        self, mock_get_cookies, mock_client_class
    ):
        """Test that get_client uses the correct profile from config."""
        # Arrange
        custom_profile = "Profile 2"
        mock_get_cookies.return_value = ("session_token", "csrf_token")

        mock_storage = MagicMock(spec=Storage)
        mock_storage.get_config.return_value = Config(
            language="python3",
            editor="vim",
            browser="chrome",
            profile=custom_profile,
        )

        session_manager = SessionManager(storage=mock_storage)

        # Act
        session_manager.get_client()

        # Assert
        mock_get_cookies.assert_called_once_with(custom_profile)

    @patch("lc.session.LeetCodeClient")
    @patch("lc.session.get_chrome_cookies")
    def test_get_client_uses_work_profile_from_config(
        self, mock_get_cookies, mock_client_class
    ):
        """Test that get_client correctly handles a work profile configuration."""
        # Arrange
        work_profile = "Profile 3"
        mock_get_cookies.return_value = ("work_session", "work_csrf")

        mock_storage = MagicMock(spec=Storage)
        mock_storage.get_config.return_value = Config(
            language="python3",
            editor="code",
            browser="chrome",
            profile=work_profile,
        )

        session_manager = SessionManager(storage=mock_storage)

        # Act
        session_manager.get_client()

        # Assert
        mock_get_cookies.assert_called_once_with(work_profile)
        mock_client_class.assert_called_once_with("work_session", "work_csrf")


class TestSessionManagerDependencyInjection(unittest.TestCase):
    """Tests for SessionManager dependency injection."""

    def test_custom_storage_can_be_passed_to_constructor(self):
        """Test that a custom Storage instance can be passed to the constructor."""
        # Arrange
        custom_storage = MagicMock(spec=Storage)

        # Act
        session_manager = SessionManager(storage=custom_storage)

        # Assert
        self.assertIs(session_manager._storage, custom_storage)

    @patch("lc.session.Storage")
    def test_default_storage_is_created_if_not_provided(self, mock_storage_class):
        """Test that a default Storage is created if none is provided."""
        # Arrange
        mock_storage_instance = MagicMock(spec=Storage)
        mock_storage_class.return_value = mock_storage_instance

        # Act
        session_manager = SessionManager()

        # Assert
        mock_storage_class.assert_called_once_with()
        self.assertIs(session_manager._storage, mock_storage_instance)

    def test_storage_is_used_for_config_retrieval(self):
        """Test that the injected storage is used for config retrieval."""
        # Arrange
        mock_storage = MagicMock(spec=Storage)
        mock_storage.get_config.return_value = Config(
            language="python3",
            editor="vim",
            browser="chrome",
            profile="TestProfile",
        )

        session_manager = SessionManager(storage=mock_storage)

        # Act - Access storage through get_client (with mocked dependencies)
        with patch("lc.session.get_chrome_cookies") as mock_cookies:
            with patch("lc.session.LeetCodeClient"):
                mock_cookies.return_value = ("token", "csrf")
                session_manager.get_client()

        # Assert
        mock_storage.get_config.assert_called_once()


class TestSessionManagerCookieErrorChaining(unittest.TestCase):
    """Tests for CookieError chaining behavior."""

    @patch("lc.session.get_chrome_cookies")
    def test_cookie_error_is_chained_from_original_exception(self, mock_get_cookies):
        """Test that the new CookieError is chained from the original exception."""
        # Arrange
        original_error = CookieError("Original error message")
        mock_get_cookies.side_effect = original_error

        mock_storage = MagicMock(spec=Storage)
        mock_storage.get_config.return_value = Config(
            language="python3",
            editor="vim",
            browser="chrome",
            profile="Default",
        )

        session_manager = SessionManager(storage=mock_storage)

        # Act & Assert
        with self.assertRaises(CookieError) as context:
            session_manager.get_client()

        # Verify exception chaining (from e)
        self.assertIs(context.exception.__cause__, original_error)


if __name__ == "__main__":
    unittest.main()
