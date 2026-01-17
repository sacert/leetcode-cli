"""Tests for the LeetCode API client."""

import pytest
from unittest.mock import MagicMock, patch

import httpx

from lc.client import LeetCodeClient, GRAPHQL_ENDPOINT, BASE_URL
from lc.exceptions import ProblemNotFoundError, SessionExpiredError, SubmissionError
from lc.models import Problem, SampleTestCase, SubmissionResult


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_graphql_response() -> dict:
    """Sample problem response from GraphQL API."""
    return {
        "data": {
            "question": {
                "questionId": "1",
                "title": "Two Sum",
                "titleSlug": "two-sum",
                "difficulty": "Easy",
                "content": "<p>Given an array of integers nums and an integer target...</p>",
                "codeSnippets": [
                    {
                        "lang": "Python3",
                        "langSlug": "python3",
                        "code": "class Solution:\n    def twoSum(self, nums: List[int], target: int) -> List[int]:\n        pass",
                    },
                    {
                        "lang": "Java",
                        "langSlug": "java",
                        "code": "class Solution { }",
                    },
                ],
                "sampleTestCase": "[2,7,11,15]\n9",
                "exampleTestcases": "[2,7,11,15]\n9\n[3,2,4]\n6",
            }
        }
    }


@pytest.fixture
def mock_graphql_response_not_found() -> dict:
    """Sample response when problem doesn't exist."""
    return {"data": {"question": None}}


@pytest.fixture
def mock_submit_response() -> dict:
    """Sample submission ID response."""
    return {"submission_id": 123456789}


@pytest.fixture
def mock_interpret_response() -> dict:
    """Sample interpret (run tests) ID response."""
    return {"interpret_id": "runcode_987654321"}


@pytest.fixture
def mock_check_response_pending() -> dict:
    """Sample pending check response (still processing)."""
    return {"state": "PENDING"}


@pytest.fixture
def mock_check_response_accepted() -> dict:
    """Sample accepted check response."""
    return {
        "state": "SUCCESS",
        "status_msg": "Accepted",
        "status_runtime": "40 ms",
        "runtime_percentile": 95.5,
        "status_memory": "14.2 MB",
        "memory_percentile": 80.3,
        "total_correct": 57,
        "total_testcases": 57,
    }


@pytest.fixture
def mock_check_response_wrong() -> dict:
    """Sample wrong answer check response."""
    return {
        "state": "SUCCESS",
        "status_msg": "Wrong Answer",
        "total_correct": 45,
        "total_testcases": 57,
        "input_formatted": "[2,7,11,15]\n9",
        "expected_output": "[0,1]",
    }


@pytest.fixture
def mock_check_response_runtime_error() -> dict:
    """Sample runtime error check response."""
    return {
        "state": "SUCCESS",
        "status_msg": "Runtime Error",
        "total_correct": 0,
        "total_testcases": 57,
        "input_formatted": "[1,2,3]",
        "expected_output": "[0,1]",
    }


@pytest.fixture
def client() -> LeetCodeClient:
    """Create a LeetCodeClient instance for testing."""
    return LeetCodeClient(session_token="test_session", csrf_token="test_csrf")


# ============================================================================
# Tests for fetch_problem()
# ============================================================================


class TestFetchProblem:
    """Tests for LeetCodeClient.fetch_problem()."""

    def test_fetch_problem_success(
        self, client: LeetCodeClient, mock_graphql_response: dict
    ) -> None:
        """Test successful problem fetch with mocked GraphQL response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_graphql_response

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            problem = client.fetch_problem("two-sum")

            # Verify the request was made correctly
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == GRAPHQL_ENDPOINT
            assert "titleSlug" in call_args[1]["json"]["variables"]
            assert call_args[1]["json"]["variables"]["titleSlug"] == "two-sum"

            # Verify the returned problem
            assert isinstance(problem, Problem)
            assert problem.id == 1
            assert problem.slug == "two-sum"
            assert problem.title == "Two Sum"
            assert problem.difficulty == "Easy"
            assert "Given an array of integers" in problem.content
            assert "class Solution:" in problem.code_template
            assert "twoSum" in problem.code_template
            assert len(problem.sample_test_cases) == 1
            assert "[2,7,11,15]" in problem.sample_test_cases[0].input

    def test_fetch_problem_not_found(
        self, client: LeetCodeClient, mock_graphql_response_not_found: dict
    ) -> None:
        """Test ProblemNotFoundError when problem doesn't exist."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_graphql_response_not_found

        with patch.object(client._client, "post", return_value=mock_response):
            with pytest.raises(ProblemNotFoundError) as exc_info:
                client.fetch_problem("nonexistent-problem")

            assert "nonexistent-problem" in str(exc_info.value)
            assert exc_info.value.slug == "nonexistent-problem"

    def test_fetch_problem_session_expired_401(self, client: LeetCodeClient) -> None:
        """Test SessionExpiredError on 401 response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401

        with patch.object(client._client, "post", return_value=mock_response):
            with pytest.raises(SessionExpiredError):
                client.fetch_problem("two-sum")

    def test_fetch_problem_session_expired_403(self, client: LeetCodeClient) -> None:
        """Test SessionExpiredError on 403 response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 403

        with patch.object(client._client, "post", return_value=mock_response):
            with pytest.raises(SessionExpiredError):
                client.fetch_problem("two-sum")

    def test_fetch_problem_no_python_template(self, client: LeetCodeClient) -> None:
        """Test fetching problem with no Python3 code snippet."""
        response_data = {
            "data": {
                "question": {
                    "questionId": "2",
                    "title": "Add Two Numbers",
                    "titleSlug": "add-two-numbers",
                    "difficulty": "Medium",
                    "content": "<p>Problem description</p>",
                    "codeSnippets": [
                        {"lang": "Java", "langSlug": "java", "code": "class Solution { }"},
                    ],
                    "sampleTestCase": "[1,2,3]",
                    "exampleTestcases": "",
                }
            }
        }

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_data

        with patch.object(client._client, "post", return_value=mock_response):
            problem = client.fetch_problem("add-two-numbers")

            assert problem.code_template == ""


# ============================================================================
# Tests for submit_solution()
# ============================================================================


class TestSubmitSolution:
    """Tests for LeetCodeClient.submit_solution()."""

    def test_submit_solution_accepted(
        self,
        client: LeetCodeClient,
        mock_submit_response: dict,
        mock_check_response_accepted: dict,
    ) -> None:
        """Test successful submission (accepted)."""
        mock_submit_resp = MagicMock(spec=httpx.Response)
        mock_submit_resp.status_code = 200
        mock_submit_resp.json.return_value = mock_submit_response

        mock_check_resp = MagicMock(spec=httpx.Response)
        mock_check_resp.status_code = 200
        mock_check_resp.json.return_value = mock_check_response_accepted

        with patch.object(client._client, "post", return_value=mock_submit_resp):
            with patch.object(client._client, "get", return_value=mock_check_resp):
                result = client.submit_solution(
                    slug="two-sum",
                    problem_id=1,
                    code="class Solution:\n    def twoSum(self, nums, target):\n        return [0, 1]",
                )

                assert isinstance(result, SubmissionResult)
                assert result.accepted is True
                assert result.status_msg == "Accepted"
                assert result.runtime == "40 ms"
                assert result.runtime_percentile == 95.5
                assert result.memory == "14.2 MB"
                assert result.memory_percentile == 80.3
                assert result.test_cases_passed == 57
                assert result.total_test_cases == 57
                assert result.failed_test_case is None

    def test_submit_solution_wrong_answer(
        self,
        client: LeetCodeClient,
        mock_submit_response: dict,
        mock_check_response_wrong: dict,
    ) -> None:
        """Test failed submission (wrong answer)."""
        mock_submit_resp = MagicMock(spec=httpx.Response)
        mock_submit_resp.status_code = 200
        mock_submit_resp.json.return_value = mock_submit_response

        mock_check_resp = MagicMock(spec=httpx.Response)
        mock_check_resp.status_code = 200
        mock_check_resp.json.return_value = mock_check_response_wrong

        with patch.object(client._client, "post", return_value=mock_submit_resp):
            with patch.object(client._client, "get", return_value=mock_check_resp):
                result = client.submit_solution(
                    slug="two-sum",
                    problem_id=1,
                    code="class Solution:\n    def twoSum(self, nums, target):\n        return []",
                )

                assert result.accepted is False
                assert result.status_msg == "Wrong Answer"
                assert result.test_cases_passed == 45
                assert result.total_test_cases == 57
                assert result.failed_test_case is not None
                assert result.failed_test_case.input == "[2,7,11,15]\n9"
                assert result.failed_test_case.expected == "[0,1]"

    def test_submit_solution_polling_mechanism(
        self,
        client: LeetCodeClient,
        mock_submit_response: dict,
        mock_check_response_pending: dict,
        mock_check_response_accepted: dict,
    ) -> None:
        """Test polling mechanism (mock multiple check responses)."""
        mock_submit_resp = MagicMock(spec=httpx.Response)
        mock_submit_resp.status_code = 200
        mock_submit_resp.json.return_value = mock_submit_response

        # First two calls return PENDING, third returns SUCCESS
        mock_check_resp_pending = MagicMock(spec=httpx.Response)
        mock_check_resp_pending.status_code = 200
        mock_check_resp_pending.json.return_value = mock_check_response_pending

        mock_check_resp_success = MagicMock(spec=httpx.Response)
        mock_check_resp_success.status_code = 200
        mock_check_resp_success.json.return_value = mock_check_response_accepted

        with patch.object(client._client, "post", return_value=mock_submit_resp):
            with patch.object(
                client._client,
                "get",
                side_effect=[
                    mock_check_resp_pending,
                    mock_check_resp_pending,
                    mock_check_resp_success,
                ],
            ):
                with patch("lc.client.time.sleep") as mock_sleep:
                    result = client.submit_solution(
                        slug="two-sum",
                        problem_id=1,
                        code="class Solution:\n    pass",
                    )

                    # Verify sleep was called for each PENDING response
                    assert mock_sleep.call_count == 2
                    assert result.accepted is True

    def test_submit_solution_session_expired(
        self, client: LeetCodeClient
    ) -> None:
        """Test SessionExpiredError on auth failure during submission."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401

        with patch.object(client._client, "post", return_value=mock_response):
            with pytest.raises(SessionExpiredError):
                client.submit_solution(
                    slug="two-sum",
                    problem_id=1,
                    code="class Solution:\n    pass",
                )

    def test_submit_solution_session_expired_during_poll(
        self, client: LeetCodeClient, mock_submit_response: dict
    ) -> None:
        """Test SessionExpiredError on auth failure during polling."""
        mock_submit_resp = MagicMock(spec=httpx.Response)
        mock_submit_resp.status_code = 200
        mock_submit_resp.json.return_value = mock_submit_response

        mock_check_resp = MagicMock(spec=httpx.Response)
        mock_check_resp.status_code = 403

        with patch.object(client._client, "post", return_value=mock_submit_resp):
            with patch.object(client._client, "get", return_value=mock_check_resp):
                with pytest.raises(SessionExpiredError):
                    client.submit_solution(
                        slug="two-sum",
                        problem_id=1,
                        code="class Solution:\n    pass",
                    )

    def test_submit_solution_no_submission_id(self, client: LeetCodeClient) -> None:
        """Test SubmissionError when no submission ID is returned."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        with patch.object(client._client, "post", return_value=mock_response):
            with pytest.raises(SubmissionError) as exc_info:
                client.submit_solution(
                    slug="two-sum",
                    problem_id=1,
                    code="class Solution:\n    pass",
                )

            assert "No submission ID" in str(exc_info.value)

    def test_submit_solution_http_error(self, client: LeetCodeClient) -> None:
        """Test SubmissionError on HTTP error during submission."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500

        with patch.object(client._client, "post", return_value=mock_response):
            with pytest.raises(SubmissionError) as exc_info:
                client.submit_solution(
                    slug="two-sum",
                    problem_id=1,
                    code="class Solution:\n    pass",
                )

            assert "HTTP 500" in str(exc_info.value)

    def test_submit_solution_timeout(
        self, client: LeetCodeClient, mock_submit_response: dict, mock_check_response_pending: dict
    ) -> None:
        """Test SubmissionError when polling times out."""
        mock_submit_resp = MagicMock(spec=httpx.Response)
        mock_submit_resp.status_code = 200
        mock_submit_resp.json.return_value = mock_submit_response

        mock_check_resp = MagicMock(spec=httpx.Response)
        mock_check_resp.status_code = 200
        mock_check_resp.json.return_value = mock_check_response_pending

        with patch.object(client._client, "post", return_value=mock_submit_resp):
            with patch.object(client._client, "get", return_value=mock_check_resp):
                with patch("lc.client.time.sleep"):
                    with patch("lc.client.MAX_POLL_ATTEMPTS", 3):
                        with pytest.raises(SubmissionError) as exc_info:
                            client.submit_solution(
                                slug="two-sum",
                                problem_id=1,
                                code="class Solution:\n    pass",
                            )

                        assert "timed out" in str(exc_info.value)


# ============================================================================
# Tests for run_tests()
# ============================================================================


class TestRunTests:
    """Tests for LeetCodeClient.run_tests()."""

    def test_run_tests_success(
        self,
        client: LeetCodeClient,
        mock_interpret_response: dict,
        mock_check_response_accepted: dict,
    ) -> None:
        """Test successful test run."""
        mock_interpret_resp = MagicMock(spec=httpx.Response)
        mock_interpret_resp.status_code = 200
        mock_interpret_resp.json.return_value = mock_interpret_response

        mock_check_resp = MagicMock(spec=httpx.Response)
        mock_check_resp.status_code = 200
        mock_check_resp.json.return_value = mock_check_response_accepted

        with patch.object(client._client, "post", return_value=mock_interpret_resp) as mock_post:
            with patch.object(client._client, "get", return_value=mock_check_resp):
                result = client.run_tests(
                    slug="two-sum",
                    problem_id=1,
                    code="class Solution:\n    def twoSum(self, nums, target):\n        return [0, 1]",
                    test_cases="[2,7,11,15]\n9",
                )

                # Verify the request URL
                call_args = mock_post.call_args
                assert f"{BASE_URL}/problems/two-sum/interpret_solution/" == call_args[0][0]

                # Verify payload
                payload = call_args[1]["json"]
                assert payload["lang"] == "python3"
                assert payload["question_id"] == "1"
                assert payload["data_input"] == "[2,7,11,15]\n9"

                assert isinstance(result, SubmissionResult)
                assert result.accepted is True
                assert result.status_msg == "Accepted"

    def test_run_tests_failing(
        self,
        client: LeetCodeClient,
        mock_interpret_response: dict,
        mock_check_response_wrong: dict,
    ) -> None:
        """Test with failing tests."""
        mock_interpret_resp = MagicMock(spec=httpx.Response)
        mock_interpret_resp.status_code = 200
        mock_interpret_resp.json.return_value = mock_interpret_response

        mock_check_resp = MagicMock(spec=httpx.Response)
        mock_check_resp.status_code = 200
        mock_check_resp.json.return_value = mock_check_response_wrong

        with patch.object(client._client, "post", return_value=mock_interpret_resp):
            with patch.object(client._client, "get", return_value=mock_check_resp):
                result = client.run_tests(
                    slug="two-sum",
                    problem_id=1,
                    code="class Solution:\n    def twoSum(self, nums, target):\n        return []",
                    test_cases="[2,7,11,15]\n9",
                )

                assert result.accepted is False
                assert result.status_msg == "Wrong Answer"
                assert result.failed_test_case is not None
                assert result.failed_test_case.expected == "[0,1]"

    def test_run_tests_session_expired(self, client: LeetCodeClient) -> None:
        """Test SessionExpiredError during run_tests."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401

        with patch.object(client._client, "post", return_value=mock_response):
            with pytest.raises(SessionExpiredError):
                client.run_tests(
                    slug="two-sum",
                    problem_id=1,
                    code="class Solution:\n    pass",
                    test_cases="[1,2,3]",
                )

    def test_run_tests_no_interpret_id(self, client: LeetCodeClient) -> None:
        """Test SubmissionError when no interpret ID is returned."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        with patch.object(client._client, "post", return_value=mock_response):
            with pytest.raises(SubmissionError) as exc_info:
                client.run_tests(
                    slug="two-sum",
                    problem_id=1,
                    code="class Solution:\n    pass",
                    test_cases="[1,2,3]",
                )

            assert "No interpret ID" in str(exc_info.value)

    def test_run_tests_http_error(self, client: LeetCodeClient) -> None:
        """Test SubmissionError on HTTP error during run_tests."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500

        with patch.object(client._client, "post", return_value=mock_response):
            with pytest.raises(SubmissionError) as exc_info:
                client.run_tests(
                    slug="two-sum",
                    problem_id=1,
                    code="class Solution:\n    pass",
                    test_cases="[1,2,3]",
                )

            assert "HTTP 500" in str(exc_info.value)

    def test_run_tests_with_custom_language(
        self,
        client: LeetCodeClient,
        mock_interpret_response: dict,
        mock_check_response_accepted: dict,
    ) -> None:
        """Test run_tests with a custom language parameter."""
        mock_interpret_resp = MagicMock(spec=httpx.Response)
        mock_interpret_resp.status_code = 200
        mock_interpret_resp.json.return_value = mock_interpret_response

        mock_check_resp = MagicMock(spec=httpx.Response)
        mock_check_resp.status_code = 200
        mock_check_resp.json.return_value = mock_check_response_accepted

        with patch.object(client._client, "post", return_value=mock_interpret_resp) as mock_post:
            with patch.object(client._client, "get", return_value=mock_check_resp):
                client.run_tests(
                    slug="two-sum",
                    problem_id=1,
                    code="class Solution { }",
                    test_cases="[1,2,3]",
                    language="java",
                )

                payload = mock_post.call_args[1]["json"]
                assert payload["lang"] == "java"


# ============================================================================
# Tests for client initialization and headers
# ============================================================================


class TestClientInitialization:
    """Tests for LeetCodeClient initialization."""

    def test_client_headers(self) -> None:
        """Test that headers are built correctly."""
        client = LeetCodeClient(session_token="my_session", csrf_token="my_csrf")
        headers = client._build_headers()

        assert "LEETCODE_SESSION=my_session" in headers["Cookie"]
        assert "csrftoken=my_csrf" in headers["Cookie"]
        assert headers["X-CSRFToken"] == "my_csrf"
        assert headers["Referer"] == BASE_URL
        assert headers["Content-Type"] == "application/json"

    def test_client_creates_httpx_client(self) -> None:
        """Test that httpx.Client is created with correct configuration."""
        with patch("lc.client.httpx.Client") as mock_client_class:
            LeetCodeClient(session_token="session", csrf_token="csrf")

            mock_client_class.assert_called_once()
            call_kwargs = mock_client_class.call_args[1]
            assert "headers" in call_kwargs
            assert call_kwargs["timeout"] == 30.0
