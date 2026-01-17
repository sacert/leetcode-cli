"""Custom exceptions for the leetcode-cli application."""


class LeetCodeError(Exception):
    """Base exception for all leetcode-cli errors."""

    def __init__(self, message: str = "An error occurred with LeetCode CLI") -> None:
        self.message = message
        super().__init__(self.message)


class SessionExpiredError(LeetCodeError):
    """Raised when LeetCode session is expired (401/403)."""

    def __init__(
        self, message: str = "Session expired. Please login to leetcode.com in Chrome and retry."
    ) -> None:
        super().__init__(message)


class ProblemNotFoundError(LeetCodeError):
    """Raised when a problem slug doesn't exist."""

    def __init__(self, slug: str | None = None) -> None:
        if slug:
            message = f"Problem not found: {slug}"
        else:
            message = "Problem not found"
        super().__init__(message)
        self.slug = slug


class CookieError(LeetCodeError):
    """Raised when cookies can't be read from Chrome."""

    def __init__(
        self, message: str = "Failed to read cookies from Chrome. Ensure Chrome is installed and you're logged into LeetCode."
    ) -> None:
        super().__init__(message)


class SubmissionError(LeetCodeError):
    """Raised when submission fails."""

    def __init__(self, message: str = "Submission failed") -> None:
        super().__init__(message)
