"""LeetCode API client for fetching problems and submitting solutions."""

import time
from typing import Any

import httpx

from lc.exceptions import ProblemNotFoundError, SessionExpiredError, SubmissionError
from lc.models import Problem, SampleTestCase, SubmissionResult


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

        return Problem(
            id=int(question["questionId"]),
            slug=question["titleSlug"],
            title=question["title"],
            difficulty=question["difficulty"],
            content=question.get("content", ""),
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
    ) -> SubmissionResult:
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

        return self._poll_submission_result(interpret_id)

    def _poll_submission_result(self, submission_id: int | str) -> SubmissionResult:
        check_url = f"{BASE_URL}/submissions/detail/{submission_id}/check/"

        for _ in range(MAX_POLL_ATTEMPTS):
            response = self._client.get(check_url)
            self._check_response_auth(response)
            response.raise_for_status()

            data = response.json()
            state = data.get("state")

            if state == "PENDING":
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            return self._parse_submission_result(data)

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
