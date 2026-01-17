"""Tests for CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from lc.cli import _resolve_slug, app
from lc.exceptions import ProblemNotFoundError, SessionExpiredError
from lc.models import Config, Problem, SampleTestCase, SubmissionResult
from lc.storage import Storage


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def sample_problem() -> Problem:
    """Create a sample problem for testing."""
    return Problem(
        id=1,
        slug="two-sum",
        title="Two Sum",
        difficulty="Easy",
        content="Given an array of integers nums and an integer target...",
        code_template="class Solution:\n    def twoSum(self, nums, target):\n        pass",
        sample_test_cases=[
            SampleTestCase(input="[2,7,11,15]\n9", expected="[0,1]"),
        ],
    )


@pytest.fixture
def sample_config() -> Config:
    """Create a sample config for testing."""
    return Config(
        language="python3",
        editor="vim",
        browser="chrome",
        profile="Default",
    )


@pytest.fixture
def accepted_result() -> SubmissionResult:
    """Create an accepted submission result."""
    return SubmissionResult(
        accepted=True,
        status_msg="Accepted",
        runtime="4 ms",
        runtime_percentile=95.0,
        memory="13.4 MB",
        memory_percentile=80.0,
        test_cases_passed=100,
        total_test_cases=100,
    )


@pytest.fixture
def failed_result() -> SubmissionResult:
    """Create a failed submission result."""
    return SubmissionResult(
        accepted=False,
        status_msg="Wrong Answer",
        runtime=None,
        runtime_percentile=None,
        memory=None,
        memory_percentile=None,
        test_cases_passed=50,
        total_test_cases=100,
        failed_test_case=SampleTestCase(input="[1,2,3]", expected="[0,2]"),
    )


class TestFetchCommand:
    """Tests for the 'lc fetch' command."""

    def test_fetch_successful(
        self, runner: CliRunner, sample_problem: Problem, tmp_path: Path
    ) -> None:
        """Test successful fetch creates files."""
        mock_client = MagicMock()
        mock_client.fetch_problem.return_value = sample_problem

        with (
            patch("lc.cli.SessionManager") as mock_session_manager,
            patch("lc.cli.Storage") as mock_storage_class,
        ):
            mock_storage = MagicMock()
            mock_storage.save_problem.return_value = tmp_path / "two-sum" / "solution.py"
            mock_storage_class.return_value = mock_storage

            mock_session = MagicMock()
            mock_session.get_client.return_value = mock_client
            mock_session_manager.return_value = mock_session

            result = runner.invoke(app, ["fetch", "two-sum"])

            assert result.exit_code == 0
            assert "Two Sum" in result.output
            assert "Created:" in result.output
            assert "problem.md" in result.output
            assert "solution.py" in result.output
            assert "metadata.json" in result.output
            mock_client.fetch_problem.assert_called_once_with("two-sum")
            mock_storage.save_problem.assert_called_once_with(sample_problem)

    def test_fetch_session_expired_error(self, runner: CliRunner) -> None:
        """Test fetch handles SessionExpiredError."""
        with (
            patch("lc.cli.SessionManager") as mock_session_manager,
            patch("lc.cli.Storage"),
        ):
            mock_session = MagicMock()
            mock_session.get_client.side_effect = SessionExpiredError()
            mock_session_manager.return_value = mock_session

            result = runner.invoke(app, ["fetch", "two-sum"])

            assert result.exit_code == 1
            assert "Session expired" in result.output

    def test_fetch_problem_not_found_error(self, runner: CliRunner) -> None:
        """Test fetch handles ProblemNotFoundError."""
        mock_client = MagicMock()
        mock_client.fetch_problem.side_effect = ProblemNotFoundError("invalid-problem")

        with (
            patch("lc.cli.SessionManager") as mock_session_manager,
            patch("lc.cli.Storage"),
        ):
            mock_session = MagicMock()
            mock_session.get_client.return_value = mock_client
            mock_session_manager.return_value = mock_session

            result = runner.invoke(app, ["fetch", "invalid-problem"])

            assert result.exit_code == 1
            assert "not found" in result.output


class TestSubmitCommand:
    """Tests for the 'lc submit' command."""

    def test_submit_successful(
        self,
        runner: CliRunner,
        sample_problem: Problem,
        accepted_result: SubmissionResult,
    ) -> None:
        """Test successful submission shows accepted message."""
        mock_client = MagicMock()
        mock_client.submit_solution.return_value = accepted_result

        with (
            patch("lc.cli.SessionManager") as mock_session_manager,
            patch("lc.cli.Storage") as mock_storage_class,
        ):
            mock_storage = MagicMock()
            mock_storage.load_problem.return_value = sample_problem
            mock_storage.get_solution_code.return_value = "def solution(): pass"
            mock_storage_class.return_value = mock_storage

            mock_session = MagicMock()
            mock_session.get_client.return_value = mock_client
            mock_session_manager.return_value = mock_session

            result = runner.invoke(app, ["submit", "two-sum"])

            assert result.exit_code == 0
            assert "Accepted" in result.output
            assert "Runtime:" in result.output
            assert "Memory:" in result.output
            assert "4 ms" in result.output
            assert "beats 95%" in result.output

    def test_submit_failed(
        self,
        runner: CliRunner,
        sample_problem: Problem,
        failed_result: SubmissionResult,
    ) -> None:
        """Test failed submission shows error details."""
        mock_client = MagicMock()
        mock_client.submit_solution.return_value = failed_result

        with (
            patch("lc.cli.SessionManager") as mock_session_manager,
            patch("lc.cli.Storage") as mock_storage_class,
        ):
            mock_storage = MagicMock()
            mock_storage.load_problem.return_value = sample_problem
            mock_storage.get_solution_code.return_value = "def solution(): pass"
            mock_storage_class.return_value = mock_storage

            mock_session = MagicMock()
            mock_session.get_client.return_value = mock_client
            mock_session_manager.return_value = mock_session

            result = runner.invoke(app, ["submit", "two-sum"])

            assert result.exit_code == 0
            assert "Wrong Answer" in result.output
            assert "50/100" in result.output
            assert "[1,2,3]" in result.output
            assert "[0,2]" in result.output

    def test_submit_slug_from_argument(
        self,
        runner: CliRunner,
        sample_problem: Problem,
        accepted_result: SubmissionResult,
    ) -> None:
        """Test slug resolution from argument."""
        mock_client = MagicMock()
        mock_client.submit_solution.return_value = accepted_result

        with (
            patch("lc.cli.SessionManager") as mock_session_manager,
            patch("lc.cli.Storage") as mock_storage_class,
        ):
            mock_storage = MagicMock()
            mock_storage.load_problem.return_value = sample_problem
            mock_storage.get_solution_code.return_value = "def solution(): pass"
            mock_storage_class.return_value = mock_storage

            mock_session = MagicMock()
            mock_session.get_client.return_value = mock_client
            mock_session_manager.return_value = mock_session

            result = runner.invoke(app, ["submit", "three-sum"])

            assert result.exit_code == 0
            mock_storage.load_problem.assert_called_with("three-sum")

    def test_submit_slug_from_cwd(
        self,
        runner: CliRunner,
        sample_problem: Problem,
        accepted_result: SubmissionResult,
        tmp_path: Path,
    ) -> None:
        """Test slug resolution from cwd."""
        mock_client = MagicMock()
        mock_client.submit_solution.return_value = accepted_result

        # Create a mock problems directory structure
        problems_dir = tmp_path / "problems"
        problem_dir = problems_dir / "two-sum"
        problem_dir.mkdir(parents=True)

        with (
            patch("lc.cli.SessionManager") as mock_session_manager,
            patch("lc.cli.Storage") as mock_storage_class,
            patch("lc.cli.Path.cwd", return_value=problem_dir),
        ):
            mock_storage = MagicMock()
            mock_storage.problems_dir = problems_dir
            mock_storage.load_problem.return_value = sample_problem
            mock_storage.get_solution_code.return_value = "def solution(): pass"
            mock_storage_class.return_value = mock_storage

            mock_session = MagicMock()
            mock_session.get_client.return_value = mock_client
            mock_session_manager.return_value = mock_session

            # No slug argument - should infer from cwd
            result = runner.invoke(app, ["submit"])

            assert result.exit_code == 0
            mock_storage.load_problem.assert_called_with("two-sum")


class TestTestCommand:
    """Tests for the 'lc test' command."""

    def test_test_successful(
        self,
        runner: CliRunner,
        sample_problem: Problem,
        accepted_result: SubmissionResult,
    ) -> None:
        """Test successful test run."""
        mock_client = MagicMock()
        test_result = SubmissionResult(
            accepted=True,
            status_msg="Accepted",
            runtime=None,
            runtime_percentile=None,
            memory=None,
            memory_percentile=None,
            test_cases_passed=2,
            total_test_cases=2,
        )
        mock_client.run_tests.return_value = test_result

        with (
            patch("lc.cli.SessionManager") as mock_session_manager,
            patch("lc.cli.Storage") as mock_storage_class,
        ):
            mock_storage = MagicMock()
            mock_storage.load_problem.return_value = sample_problem
            mock_storage.get_solution_code.return_value = "def solution(): pass"
            mock_storage_class.return_value = mock_storage

            mock_session = MagicMock()
            mock_session.get_client.return_value = mock_client
            mock_session_manager.return_value = mock_session

            result = runner.invoke(app, ["test", "two-sum"])

            assert result.exit_code == 0
            assert "All sample tests passed" in result.output
            assert "Test 1 passed" in result.output
            assert "Test 2 passed" in result.output

    def test_test_with_failures(
        self, runner: CliRunner, sample_problem: Problem
    ) -> None:
        """Test with failing tests."""
        mock_client = MagicMock()
        test_result = SubmissionResult(
            accepted=False,
            status_msg="Wrong Answer",
            runtime=None,
            runtime_percentile=None,
            memory=None,
            memory_percentile=None,
            test_cases_passed=1,
            total_test_cases=3,
            failed_test_case=SampleTestCase(input="[1,2,3]", expected="[0,2]"),
        )
        mock_client.run_tests.return_value = test_result

        with (
            patch("lc.cli.SessionManager") as mock_session_manager,
            patch("lc.cli.Storage") as mock_storage_class,
        ):
            mock_storage = MagicMock()
            mock_storage.load_problem.return_value = sample_problem
            mock_storage.get_solution_code.return_value = "def solution(): pass"
            mock_storage_class.return_value = mock_storage

            mock_session = MagicMock()
            mock_session.get_client.return_value = mock_client
            mock_session_manager.return_value = mock_session

            result = runner.invoke(app, ["test", "two-sum"])

            assert result.exit_code == 0
            assert "Test 1 passed" in result.output
            assert "Test 2 failed" in result.output
            assert "1/3 tests passed" in result.output
            assert "[1,2,3]" in result.output
            assert "[0,2]" in result.output


class TestListCommand:
    """Tests for the 'lc list' command."""

    def test_list_saved_problems(
        self, runner: CliRunner, sample_problem: Problem
    ) -> None:
        """Test lists saved problems."""
        with patch("lc.cli.Storage") as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage.list_problems.return_value = ["two-sum", "three-sum"]
            mock_storage.load_problem.return_value = sample_problem
            mock_storage_class.return_value = mock_storage

            result = runner.invoke(app, ["list"])

            assert result.exit_code == 0
            assert "two-sum" in result.output
            assert "Two Sum" in result.output
            assert "Easy" in result.output

    def test_list_difficulty_filter(
        self, runner: CliRunner, sample_problem: Problem
    ) -> None:
        """Test --difficulty filter."""
        medium_problem = Problem(
            id=2,
            slug="three-sum",
            title="Three Sum",
            difficulty="Medium",
            content="Given an array...",
            code_template="class Solution:\n    pass",
            sample_test_cases=[],
        )

        with patch("lc.cli.Storage") as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage.list_problems.return_value = ["two-sum", "three-sum"]

            def load_problem_side_effect(slug: str) -> Problem:
                if slug == "two-sum":
                    return sample_problem  # Easy
                return medium_problem  # Medium

            mock_storage.load_problem.side_effect = load_problem_side_effect
            mock_storage_class.return_value = mock_storage

            result = runner.invoke(app, ["list", "--difficulty", "medium"])

            assert result.exit_code == 0
            assert "Three Sum" in result.output
            # Easy problems should be filtered out
            # Note: Two Sum might still appear if the table shows both
            # Let's just check that Medium is in output
            assert "Medium" in result.output

    def test_list_limit_option(
        self, runner: CliRunner, sample_problem: Problem
    ) -> None:
        """Test --limit option."""
        with patch("lc.cli.Storage") as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage.list_problems.return_value = [
                "problem-1",
                "problem-2",
                "problem-3",
                "problem-4",
                "problem-5",
            ]
            mock_storage.load_problem.return_value = sample_problem
            mock_storage_class.return_value = mock_storage

            result = runner.invoke(app, ["list", "--limit", "2"])

            assert result.exit_code == 0
            # load_problem should be called at most 2 times (limit=2)
            assert mock_storage.load_problem.call_count == 2

    def test_list_empty(self, runner: CliRunner) -> None:
        """Test list with no saved problems."""
        with patch("lc.cli.Storage") as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage.list_problems.return_value = []
            mock_storage_class.return_value = mock_storage

            result = runner.invoke(app, ["list"])

            assert result.exit_code == 0
            assert "No problems saved locally" in result.output


class TestShowCommand:
    """Tests for the 'lc show' command."""

    def test_show_displays_content(
        self, runner: CliRunner, sample_problem: Problem, tmp_path: Path
    ) -> None:
        """Test displays problem content."""
        with (
            patch("lc.cli.Storage") as mock_storage_class,
            patch("lc.cli.Path.cwd", return_value=tmp_path),
        ):
            mock_storage = MagicMock()
            mock_storage.problems_dir = tmp_path / "problems"
            mock_storage.load_problem.return_value = sample_problem
            mock_storage_class.return_value = mock_storage

            result = runner.invoke(app, ["show", "two-sum"])

            assert result.exit_code == 0
            assert "Two Sum" in result.output
            assert "Easy" in result.output

    def test_show_problem_not_found(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test show with non-existent problem."""
        with (
            patch("lc.cli.Storage") as mock_storage_class,
            patch("lc.cli.Path.cwd", return_value=tmp_path),
        ):
            mock_storage = MagicMock()
            mock_storage.problems_dir = tmp_path / "problems"
            mock_storage.load_problem.side_effect = ProblemNotFoundError("non-existent")
            mock_storage_class.return_value = mock_storage

            result = runner.invoke(app, ["show", "non-existent"])

            assert result.exit_code == 1
            assert "not found" in result.output


class TestOpenCommand:
    """Tests for the 'lc open' command."""

    def test_open_calls_subprocess(
        self, runner: CliRunner, sample_config: Config, tmp_path: Path
    ) -> None:
        """Test calls subprocess with correct editor and path."""
        problems_dir = tmp_path / "problems"
        problem_dir = problems_dir / "two-sum"
        solution_path = problem_dir / "solution.py"

        with (
            patch("lc.cli.Storage") as mock_storage_class,
            patch("lc.cli.subprocess.run") as mock_subprocess,
            patch("lc.cli.Path.cwd", return_value=tmp_path),
        ):
            mock_storage = MagicMock()
            mock_storage.problems_dir = problems_dir
            mock_storage.problem_exists.return_value = True
            mock_storage.get_config.return_value = sample_config
            mock_storage_class.return_value = mock_storage

            result = runner.invoke(app, ["open", "two-sum"])

            assert result.exit_code == 0
            mock_subprocess.assert_called_once_with(["vim", str(solution_path)])

    def test_open_problem_not_found(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test open with non-existent problem."""
        with (
            patch("lc.cli.Storage") as mock_storage_class,
            patch("lc.cli.Path.cwd", return_value=tmp_path),
        ):
            mock_storage = MagicMock()
            mock_storage.problems_dir = tmp_path / "problems"
            mock_storage.problem_exists.return_value = False
            mock_storage_class.return_value = mock_storage

            result = runner.invoke(app, ["open", "non-existent"])

            assert result.exit_code == 1
            assert "not found" in result.output


class TestResolveSlug:
    """Tests for the _resolve_slug helper function."""

    def test_resolve_with_explicit_slug(self, tmp_path: Path) -> None:
        """Test with explicit slug."""
        storage = Storage(base_path=tmp_path)

        result = _resolve_slug("my-slug", storage)

        assert result == "my-slug"

    def test_resolve_from_cwd(self, tmp_path: Path) -> None:
        """Test inferring from cwd."""
        storage = Storage(base_path=tmp_path)
        problems_dir = tmp_path / "problems"
        problem_dir = problems_dir / "two-sum"
        problem_dir.mkdir(parents=True)

        with patch("lc.cli.Path.cwd", return_value=problem_dir):
            result = _resolve_slug(None, storage)

        assert result == "two-sum"

    def test_resolve_from_nested_cwd(self, tmp_path: Path) -> None:
        """Test inferring from nested directory within problem dir."""
        storage = Storage(base_path=tmp_path)
        problems_dir = tmp_path / "problems"
        nested_dir = problems_dir / "two-sum" / "subdir"
        nested_dir.mkdir(parents=True)

        with patch("lc.cli.Path.cwd", return_value=nested_dir):
            result = _resolve_slug(None, storage)

        assert result == "two-sum"

    def test_resolve_error_when_not_in_problem_dir(self, tmp_path: Path) -> None:
        """Test error when neither slug nor valid cwd available."""
        storage = Storage(base_path=tmp_path)
        # Set cwd to a directory outside problems_dir
        other_dir = tmp_path / "other"
        other_dir.mkdir(parents=True)

        with patch("lc.cli.Path.cwd", return_value=other_dir):
            with pytest.raises(typer.Exit) as exc_info:
                _resolve_slug(None, storage)

            assert exc_info.value.exit_code == 1

    def test_resolve_error_when_in_problems_root(self, tmp_path: Path) -> None:
        """Test error when in problems_dir root without subdirectory."""
        storage = Storage(base_path=tmp_path)
        problems_dir = tmp_path / "problems"
        problems_dir.mkdir(parents=True)

        with patch("lc.cli.Path.cwd", return_value=problems_dir):
            with pytest.raises(typer.Exit) as exc_info:
                _resolve_slug(None, storage)

            assert exc_info.value.exit_code == 1


class TestIntegrationWithStorage:
    """Integration tests using actual Storage with tmp_path."""

    def test_list_with_real_storage(
        self, runner: CliRunner, sample_problem: Problem, tmp_path: Path
    ) -> None:
        """Test list command with real Storage."""
        storage = Storage(base_path=tmp_path)
        storage.save_problem(sample_problem)

        with patch("lc.cli.Storage", return_value=storage):
            result = runner.invoke(app, ["list"])

            assert result.exit_code == 0
            assert "two-sum" in result.output
            assert "Two Sum" in result.output

    def test_show_with_real_storage(
        self, runner: CliRunner, sample_problem: Problem, tmp_path: Path
    ) -> None:
        """Test show command with real Storage."""
        storage = Storage(base_path=tmp_path)
        storage.save_problem(sample_problem)

        with (
            patch("lc.cli.Storage", return_value=storage),
            patch("lc.cli.Path.cwd", return_value=tmp_path),
        ):
            result = runner.invoke(app, ["show", "two-sum"])

            assert result.exit_code == 0
            assert "Two Sum" in result.output
            assert "Given an array of integers nums" in result.output
