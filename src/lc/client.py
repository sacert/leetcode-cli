"""LeetCode API client for fetching problems and submitting solutions."""

import time
from typing import Any

import httpx
from markdownify import markdownify

from lc.exceptions import ProblemNotFoundError, SessionExpiredError, SubmissionError
from lc.models import Problem, SampleTestCase, SubmissionResult, TestCaseResult, TestResult


GRAPHQL_ENDPOINT = "https://leetcode.com/graphql/"
BASE_URL = "https://leetcode.com"

PROBLEM_QUERY = """
query getQuestionDetail($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionId
    title
    titleSlug
    difficulty
    content
    codeSnippets {
      lang
      langSlug
      code
    }
    sampleTestCase
    exampleTestcases
  }
}
"""

MAX_POLL_ATTEMPTS = 30
POLL_INTERVAL_SECONDS = 1.0


class LeetCodeClient:
    """Client for interacting with LeetCode's API."""

    def __init__(self, session_token: str, csrf_token: str) -> None:
        self._session_token = session_token
        self._csrf_token = csrf_token
        self._client = httpx.Client(
            headers=self._build_headers(),
            timeout=30.0,
        )

    def _build_headers(self) -> dict[str, str]:
        return {
            "Cookie": f"LEETCODE_SESSION={self._session_token}; csrftoken={self._csrf_token}",
            "X-CSRFToken": self._csrf_token,
            "Referer": BASE_URL,
            "Content-Type": "application/json",
        }

    def _check_response_auth(self, response: httpx.Response) -> None:
        if response.status_code in (401, 403):
            raise SessionExpiredError()

    def fetch_problem(self, slug: str) -> Problem:
        """Fetch problem details from LeetCode via GraphQL."""
        payload = {
            "query": PROBLEM_QUERY,
            "variables": {"titleSlug": slug},
        }

        response = self._client.post(GRAPHQL_ENDPOINT, json=payload)
        self._check_response_auth(response)
        response.raise_for_status()

        data = response.json()
        question = data.get("data", {}).get("question")

        if not question:
            raise ProblemNotFoundError(slug)

        code_template = self._extract_python_template(question.get("codeSnippets", []))
        test_cases = self._parse_test_cases(
            question.get("sampleTestCase", ""),
            question.get("exampleTestcases", ""),
        )

        html_content = question.get("content", "")
        markdown_content = markdownify(html_content, heading_style="ATX", strip=["script", "style"])

        return Problem(
            id=int(question["questionId"]),
            slug=question["titleSlug"],
            title=question["title"],
            difficulty=question["difficulty"],
            content=markdown_content,
            code_template=code_template,
            sample_test_cases=test_cases,
        )

    def _extract_python_template(self, code_snippets: list[dict[str, Any]]) -> str:
        for snippet in code_snippets:
            if snippet.get("langSlug") == "python3":
                return snippet.get("code", "")
        return ""

    def _parse_test_cases(self, sample_test_case: str, example_testcases: str) -> list[SampleTestCase]:
        # Use exampleTestcases if available, otherwise fall back to sampleTestCase
        test_input = example_testcases if example_testcases else sample_test_case
        if not test_input:
            return []

        # Each test case input is separated by newlines within the string
        # For problems with multiple inputs per test case, they appear on consecutive lines
        return [SampleTestCase(input=test_input.strip(), expected="")]

    def submit_solution(
        self,
        slug: str,
        problem_id: int,
        code: str,
        language: str = "python3",
    ) -> SubmissionResult:
        """Submit a solution and poll for the result."""
        submit_url = f"{BASE_URL}/problems/{slug}/submit/"
        payload = {
            "lang": language,
            "question_id": str(problem_id),
            "typed_code": code,
        }

        response = self._client.post(submit_url, json=payload)
        self._check_response_auth(response)

        if response.status_code != 200:
            raise SubmissionError(f"Failed to submit: HTTP {response.status_code}")

        data = response.json()
        submission_id = data.get("submission_id")

        if not submission_id:
            raise SubmissionError("No submission ID returned")

        return self._poll_submission_result(submission_id)

    def run_tests(
        self,
        slug: str,
        problem_id: int,
        code: str,
        test_cases: str,
        language: str = "python3",
    ) -> TestResult:
        """Run solution against sample test cases."""
        interpret_url = f"{BASE_URL}/problems/{slug}/interpret_solution/"
        payload = {
            "lang": language,
            "question_id": str(problem_id),
            "typed_code": code,
            "data_input": test_cases,
        }

        response = self._client.post(interpret_url, json=payload)
        self._check_response_auth(response)

        if response.status_code != 200:
            raise SubmissionError(f"Failed to run tests: HTTP {response.status_code}")

        data = response.json()
        interpret_id = data.get("interpret_id")

        if not interpret_id:
            raise SubmissionError("No interpret ID returned")

        return self._poll_test_result(interpret_id, test_cases)

    def _poll_test_result(self, interpret_id: str, test_cases: str) -> TestResult:
        """Poll for test result and parse with full details."""
        check_url = f"{BASE_URL}/submissions/detail/{interpret_id}/check/"

        for _ in range(MAX_POLL_ATTEMPTS):
            response = self._client.get(check_url)
            self._check_response_auth(response)
            response.raise_for_status()

            data = response.json()
            state = data.get("state")

            if state == "SUCCESS":
                return self._parse_test_result(data, test_cases)

            time.sleep(POLL_INTERVAL_SECONDS)

        raise SubmissionError("Test run timed out")

    def _parse_test_result(self, data: dict[str, Any], test_cases: str) -> TestResult:
        """Parse test result with detailed per-test-case information."""
        status_msg = data.get("status_msg", "Unknown")
        correct_answer = data.get("correct_answer", False)

        # Check for compile/runtime errors
        if status_msg in ("Compile Error", "Runtime Error", "Time Limit Exceeded"):
            error_msg = data.get("full_compile_error") or data.get("full_runtime_error") or ""
            return TestResult(
                accepted=False,
                status_msg=f"{status_msg}: {error_msg}" if error_msg else status_msg,
                test_case_results=[],
            )

        # Get arrays of results - filter out empty trailing entries
        code_answers = data.get("code_answer", [])
        expected_answers = data.get("expected_code_answer", [])
        std_outputs = data.get("std_output_list", [])
        compare_results = data.get("compare_result", "")

        # Determine actual number of test cases from expected answers (most reliable)
        # Filter out empty strings that LeetCode sometimes appends
        num_cases = len([e for e in expected_answers if e])

        if num_cases == 0:
            return TestResult(
                accepted=False,
                status_msg=status_msg,
                test_case_results=[],
            )

        # Parse test case inputs - each test case may have multiple lines
        input_lines = test_cases.strip().split("\n")

        # Calculate lines per test case
        lines_per_case = max(1, len(input_lines) // num_cases)

        test_case_results: list[TestCaseResult] = []

        for i in range(num_cases):
            # Get input lines for this test case
            start_line = i * lines_per_case
            end_line = start_line + lines_per_case
            test_input = "\n".join(input_lines[start_line:end_line])

            expected = expected_answers[i] if i < len(expected_answers) else ""
            actual = code_answers[i] if i < len(code_answers) else ""
            stdout = std_outputs[i] if i < len(std_outputs) else ""
            passed = compare_results[i] == "1" if i < len(compare_results) else False

            test_case_results.append(
                TestCaseResult(
                    input=test_input,
                    expected=expected,
                    actual=actual,
                    passed=passed,
                    stdout=stdout,
                )
            )

        return TestResult(
            accepted=correct_answer,
            status_msg=status_msg,
            test_case_results=test_case_results,
        )

    def _poll_submission_result(self, submission_id: int | str) -> SubmissionResult:
        check_url = f"{BASE_URL}/submissions/detail/{submission_id}/check/"

        for _ in range(MAX_POLL_ATTEMPTS):
            response = self._client.get(check_url)
            self._check_response_auth(response)
            response.raise_for_status()

            data = response.json()
            state = data.get("state")

            if state == "SUCCESS":
                return self._parse_submission_result(data)

            # Keep polling for PENDING, STARTED, or other intermediate states
            time.sleep(POLL_INTERVAL_SECONDS)

        raise SubmissionError("Submission check timed out")

    def _parse_submission_result(self, data: dict[str, Any]) -> SubmissionResult:
        status_msg = data.get("status_msg", "Unknown")
        accepted = status_msg == "Accepted"

        failed_test_case = None
        if not accepted and data.get("input_formatted"):
            failed_test_case = SampleTestCase(
                input=data.get("input_formatted", ""),
                expected=data.get("expected_output", ""),
            )

        return SubmissionResult(
            accepted=accepted,
            status_msg=status_msg,
            runtime=data.get("status_runtime"),
            runtime_percentile=data.get("runtime_percentile"),
            memory=data.get("status_memory"),
            memory_percentile=data.get("memory_percentile"),
            test_cases_passed=data.get("total_correct", 0),
            total_test_cases=data.get("total_testcases", 0),
            failed_test_case=failed_test_case,
        )
