"""Data models for the LeetCode CLI."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SampleTestCase:
    """Represents a test case with input and expected output."""

    input: str
    expected: str


@dataclass
class Problem:
    """Represents a LeetCode problem."""

    id: int
    slug: str
    title: str
    difficulty: str
    content: str
    code_template: str
    sample_test_cases: list[SampleTestCase]


@dataclass
class SubmissionResult:
    """Represents the result of a submission to LeetCode."""

    accepted: bool
    status_msg: str
    runtime: Optional[str]
    runtime_percentile: Optional[float]
    memory: Optional[str]
    memory_percentile: Optional[float]
    test_cases_passed: int
    total_test_cases: int
    failed_test_case: Optional[SampleTestCase] = None


@dataclass
class TestCaseResult:
    """Represents the result of a single test case."""

    input: str
    expected: str
    actual: str
    passed: bool
    stdout: str = ""


@dataclass
class TestResult:
    """Represents the result of running test cases."""

    accepted: bool
    status_msg: str
    test_case_results: list[TestCaseResult]


@dataclass
class Config:
    """User configuration for the CLI."""

    language: str
    editor: str
    browser: str
    profile: str
