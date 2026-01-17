"""Tests for the lc.models module."""

import pytest

from lc.models import Config, Problem, SampleTestCase, SubmissionResult


class TestProblem:
    """Tests for the Problem dataclass."""

    def test_problem_creation(self):
        """Test that a Problem can be created with all required fields."""
        problem = Problem(
            id=1,
            slug="two-sum",
            title="Two Sum",
            difficulty="Easy",
            content="Problem description here",
            code_template="def solution(): pass",
            sample_test_cases=[],
        )

        assert problem.id == 1
        assert problem.slug == "two-sum"
        assert problem.title == "Two Sum"
        assert problem.difficulty == "Easy"
        assert problem.content == "Problem description here"
        assert problem.code_template == "def solution(): pass"
        assert problem.sample_test_cases == []

    def test_problem_with_test_cases(self, sample_problem):
        """Test that a Problem can hold test cases."""
        assert len(sample_problem.sample_test_cases) == 2
        assert sample_problem.sample_test_cases[0].input == "[2,7,11,15]\n9"
        assert sample_problem.sample_test_cases[0].expected == "[0,1]"

    def test_problem_field_access(self, sample_problem):
        """Test all fields are accessible on the Problem."""
        assert sample_problem.id == 1
        assert sample_problem.slug == "two-sum"
        assert sample_problem.title == "Two Sum"
        assert sample_problem.difficulty == "Easy"
        assert "array of integers" in sample_problem.content
        assert "class Solution" in sample_problem.code_template


class TestTestCase:
    """Tests for the TestCase dataclass."""

    def test_testcase_creation(self):
        """Test that a TestCase can be created."""
        tc = SampleTestCase(input="[1,2,3]", expected="6")

        assert tc.input == "[1,2,3]"
        assert tc.expected == "6"

    def test_testcase_with_multiline_input(self):
        """Test TestCase with multiline input."""
        tc = SampleTestCase(input="[2,7,11,15]\n9", expected="[0,1]")

        assert "\n" in tc.input
        assert tc.expected == "[0,1]"

    def test_testcase_empty_expected(self):
        """Test TestCase with empty expected value."""
        tc = SampleTestCase(input="test input", expected="")

        assert tc.input == "test input"
        assert tc.expected == ""


class TestSubmissionResult:
    """Tests for the SubmissionResult dataclass."""

    def test_submission_result_accepted(self, sample_submission_result):
        """Test an accepted SubmissionResult."""
        assert sample_submission_result.accepted is True
        assert sample_submission_result.status_msg == "Accepted"
        assert sample_submission_result.runtime == "40 ms"
        assert sample_submission_result.runtime_percentile == 95.0
        assert sample_submission_result.memory == "14.2 MB"
        assert sample_submission_result.memory_percentile == 80.0
        assert sample_submission_result.test_cases_passed == 55
        assert sample_submission_result.total_test_cases == 55
        assert sample_submission_result.failed_test_case is None

    def test_submission_result_rejected(self):
        """Test a rejected SubmissionResult with optional fields."""
        failed_tc = SampleTestCase(input="[3,2,4]\n6", expected="[1,2]")
        result = SubmissionResult(
            accepted=False,
            status_msg="Wrong Answer",
            runtime=None,
            runtime_percentile=None,
            memory=None,
            memory_percentile=None,
            test_cases_passed=2,
            total_test_cases=55,
            failed_test_case=failed_tc,
        )

        assert result.accepted is False
        assert result.status_msg == "Wrong Answer"
        assert result.runtime is None
        assert result.runtime_percentile is None
        assert result.memory is None
        assert result.memory_percentile is None
        assert result.test_cases_passed == 2
        assert result.total_test_cases == 55
        assert result.failed_test_case is not None
        assert result.failed_test_case.input == "[3,2,4]\n6"

    def test_submission_result_with_optional_fields_none(self):
        """Test SubmissionResult with all optional fields as None."""
        result = SubmissionResult(
            accepted=False,
            status_msg="Time Limit Exceeded",
            runtime=None,
            runtime_percentile=None,
            memory=None,
            memory_percentile=None,
            test_cases_passed=10,
            total_test_cases=55,
        )

        assert result.runtime is None
        assert result.runtime_percentile is None
        assert result.memory is None
        assert result.memory_percentile is None
        assert result.failed_test_case is None

    def test_submission_result_default_failed_test_case(self):
        """Test that failed_test_case defaults to None."""
        result = SubmissionResult(
            accepted=True,
            status_msg="Accepted",
            runtime="10 ms",
            runtime_percentile=99.0,
            memory="10 MB",
            memory_percentile=90.0,
            test_cases_passed=55,
            total_test_cases=55,
        )

        assert result.failed_test_case is None


class TestConfig:
    """Tests for the Config dataclass."""

    def test_config_creation(self, sample_config):
        """Test that a Config can be created with all fields."""
        assert sample_config.language == "python3"
        assert sample_config.editor == "vim"
        assert sample_config.browser == "chrome"
        assert sample_config.profile == "Default"

    def test_config_custom_values(self):
        """Test Config with custom values."""
        config = Config(
            language="java",
            editor="code",
            browser="firefox",
            profile="Work",
        )

        assert config.language == "java"
        assert config.editor == "code"
        assert config.browser == "firefox"
        assert config.profile == "Work"

    def test_config_defaults_match_expected(self):
        """Test that default config matches expected defaults from product doc."""
        config = Config(
            language="python3",
            editor="vim",
            browser="chrome",
            profile="Default",
        )

        assert config.language == "python3"
        assert config.editor == "vim"
        assert config.browser == "chrome"
        assert config.profile == "Default"
