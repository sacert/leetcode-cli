"""Shared pytest fixtures for the leetcode-cli test suite."""

from unittest.mock import MagicMock

import pytest

from lc.client import LeetCodeClient
from lc.models import Config, Problem, SampleTestCase, SubmissionResult
from lc.storage import Storage


@pytest.fixture
def sample_problem() -> Problem:
    """Returns a sample Problem object for testing."""
    return Problem(
        id=1,
        slug="two-sum",
        title="Two Sum",
        difficulty="Easy",
        content="Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.",
        code_template="class Solution:\n    def twoSum(self, nums: list[int], target: int) -> list[int]:\n        pass",
        sample_test_cases=[
            SampleTestCase(input="[2,7,11,15]\n9", expected="[0,1]"),
            SampleTestCase(input="[3,2,4]\n6", expected="[1,2]"),
        ],
    )


@pytest.fixture
def sample_submission_result() -> SubmissionResult:
    """Returns an accepted SubmissionResult for testing."""
    return SubmissionResult(
        accepted=True,
        status_msg="Accepted",
        runtime="40 ms",
        runtime_percentile=95.0,
        memory="14.2 MB",
        memory_percentile=80.0,
        test_cases_passed=55,
        total_test_cases=55,
        failed_test_case=None,
    )


@pytest.fixture
def sample_config() -> Config:
    """Returns a default Config for testing."""
    return Config(
        language="python3",
        editor="vim",
        browser="chrome",
        profile="Default",
    )


@pytest.fixture
def tmp_storage(tmp_path) -> Storage:
    """Returns a Storage instance using a temporary directory."""
    return Storage(base_path=tmp_path)


@pytest.fixture
def mock_leetcode_client() -> MagicMock:
    """Returns a MagicMock for LeetCodeClient."""
    mock = MagicMock(spec=LeetCodeClient)
    return mock
