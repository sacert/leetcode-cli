"""Tests for the lc.exceptions module."""

import pytest

from lc.exceptions import (
    CookieError,
    LeetCodeError,
    ProblemNotFoundError,
    SessionExpiredError,
    SubmissionError,
)


class TestLeetCodeError:
    """Tests for the base LeetCodeError exception."""

    def test_leetcode_error_can_be_raised(self):
        """Test that LeetCodeError can be raised and caught."""
        with pytest.raises(LeetCodeError):
            raise LeetCodeError()

    def test_leetcode_error_default_message(self):
        """Test LeetCodeError has a default message."""
        error = LeetCodeError()
        assert error.message == "An error occurred with LeetCode CLI"
        assert str(error) == "An error occurred with LeetCode CLI"

    def test_leetcode_error_custom_message(self):
        """Test LeetCodeError with a custom message."""
        error = LeetCodeError("Custom error message")
        assert error.message == "Custom error message"
        assert str(error) == "Custom error message"


class TestSessionExpiredError:
    """Tests for the SessionExpiredError exception."""

    def test_session_expired_error_can_be_raised(self):
        """Test that SessionExpiredError can be raised and caught."""
        with pytest.raises(SessionExpiredError):
            raise SessionExpiredError()

    def test_session_expired_error_inherits_from_leetcode_error(self):
        """Test that SessionExpiredError inherits from LeetCodeError."""
        error = SessionExpiredError()
        assert isinstance(error, LeetCodeError)

    def test_session_expired_error_caught_as_leetcode_error(self):
        """Test that SessionExpiredError can be caught as LeetCodeError."""
        with pytest.raises(LeetCodeError):
            raise SessionExpiredError()

    def test_session_expired_error_default_message(self):
        """Test SessionExpiredError has an informative default message."""
        error = SessionExpiredError()
        assert "Session expired" in error.message
        assert "leetcode.com" in error.message

    def test_session_expired_error_custom_message(self):
        """Test SessionExpiredError with a custom message."""
        error = SessionExpiredError("Token invalid")
        assert error.message == "Token invalid"
        assert str(error) == "Token invalid"


class TestProblemNotFoundError:
    """Tests for the ProblemNotFoundError exception."""

    def test_problem_not_found_error_can_be_raised(self):
        """Test that ProblemNotFoundError can be raised and caught."""
        with pytest.raises(ProblemNotFoundError):
            raise ProblemNotFoundError("two-sum")

    def test_problem_not_found_error_inherits_from_leetcode_error(self):
        """Test that ProblemNotFoundError inherits from LeetCodeError."""
        error = ProblemNotFoundError("two-sum")
        assert isinstance(error, LeetCodeError)

    def test_problem_not_found_error_caught_as_leetcode_error(self):
        """Test that ProblemNotFoundError can be caught as LeetCodeError."""
        with pytest.raises(LeetCodeError):
            raise ProblemNotFoundError("two-sum")

    def test_problem_not_found_error_with_slug(self):
        """Test ProblemNotFoundError includes the slug in message."""
        error = ProblemNotFoundError("two-sum")
        assert error.slug == "two-sum"
        assert "two-sum" in error.message
        assert "Problem not found" in error.message

    def test_problem_not_found_error_without_slug(self):
        """Test ProblemNotFoundError without a slug."""
        error = ProblemNotFoundError()
        assert error.slug is None
        assert error.message == "Problem not found"

    def test_problem_not_found_error_none_slug(self):
        """Test ProblemNotFoundError with explicit None slug."""
        error = ProblemNotFoundError(None)
        assert error.slug is None
        assert error.message == "Problem not found"


class TestCookieError:
    """Tests for the CookieError exception."""

    def test_cookie_error_can_be_raised(self):
        """Test that CookieError can be raised and caught."""
        with pytest.raises(CookieError):
            raise CookieError()

    def test_cookie_error_inherits_from_leetcode_error(self):
        """Test that CookieError inherits from LeetCodeError."""
        error = CookieError()
        assert isinstance(error, LeetCodeError)

    def test_cookie_error_caught_as_leetcode_error(self):
        """Test that CookieError can be caught as LeetCodeError."""
        with pytest.raises(LeetCodeError):
            raise CookieError()

    def test_cookie_error_default_message(self):
        """Test CookieError has an informative default message."""
        error = CookieError()
        assert "cookies" in error.message.lower()
        assert "Chrome" in error.message

    def test_cookie_error_custom_message(self):
        """Test CookieError with a custom message."""
        error = CookieError("Cookie database locked")
        assert error.message == "Cookie database locked"
        assert str(error) == "Cookie database locked"


class TestSubmissionError:
    """Tests for the SubmissionError exception."""

    def test_submission_error_can_be_raised(self):
        """Test that SubmissionError can be raised and caught."""
        with pytest.raises(SubmissionError):
            raise SubmissionError()

    def test_submission_error_inherits_from_leetcode_error(self):
        """Test that SubmissionError inherits from LeetCodeError."""
        error = SubmissionError()
        assert isinstance(error, LeetCodeError)

    def test_submission_error_caught_as_leetcode_error(self):
        """Test that SubmissionError can be caught as LeetCodeError."""
        with pytest.raises(LeetCodeError):
            raise SubmissionError()

    def test_submission_error_default_message(self):
        """Test SubmissionError has a default message."""
        error = SubmissionError()
        assert error.message == "Submission failed"

    def test_submission_error_custom_message(self):
        """Test SubmissionError with a custom message."""
        error = SubmissionError("Rate limit exceeded")
        assert error.message == "Rate limit exceeded"
        assert str(error) == "Rate limit exceeded"


class TestExceptionHierarchy:
    """Tests for verifying the exception inheritance hierarchy."""

    def test_all_exceptions_inherit_from_leetcode_error(self):
        """Test that all custom exceptions inherit from LeetCodeError."""
        exceptions = [
            SessionExpiredError(),
            ProblemNotFoundError("test"),
            CookieError(),
            SubmissionError(),
        ]

        for exc in exceptions:
            assert isinstance(exc, LeetCodeError), f"{type(exc).__name__} should inherit from LeetCodeError"

    def test_all_exceptions_inherit_from_exception(self):
        """Test that all custom exceptions inherit from Exception."""
        exceptions = [
            LeetCodeError(),
            SessionExpiredError(),
            ProblemNotFoundError("test"),
            CookieError(),
            SubmissionError(),
        ]

        for exc in exceptions:
            assert isinstance(exc, Exception), f"{type(exc).__name__} should inherit from Exception"

    def test_catch_all_with_leetcode_error(self):
        """Test that catching LeetCodeError catches all subclasses."""
        exception_classes = [
            SessionExpiredError,
            ProblemNotFoundError,
            CookieError,
            SubmissionError,
        ]

        for exc_class in exception_classes:
            try:
                if exc_class == ProblemNotFoundError:
                    raise exc_class("test-slug")
                else:
                    raise exc_class()
            except LeetCodeError as e:
                assert isinstance(e, exc_class)
            else:
                pytest.fail(f"{exc_class.__name__} was not caught by LeetCodeError")
