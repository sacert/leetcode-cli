"""Tests for local file storage."""

import json

import pytest

from lc.exceptions import ProblemNotFoundError
from lc.models import Config, Problem, SampleTestCase
from lc.storage import DEFAULT_CONFIG, Storage


@pytest.fixture
def sample_problem() -> Problem:
    """Create a sample problem for testing."""
    return Problem(
        id=1,
        slug="two-sum",
        title="Two Sum",
        difficulty="Easy",
        content="# Two Sum\n\nGiven an array of integers...",
        code_template="class Solution:\n    def twoSum(self, nums, target):\n        pass\n",
        sample_test_cases=[
            SampleTestCase(input="[2,7,11,15]\n9", expected="[0,1]"),
            SampleTestCase(input="[3,2,4]\n6", expected="[1,2]"),
        ],
    )


@pytest.fixture
def storage(tmp_path) -> Storage:
    """Create a Storage instance with a temporary base path."""
    return Storage(base_path=tmp_path)


class TestSaveProblem:
    """Tests for Storage.save_problem()."""

    def test_creates_problem_files(self, storage, sample_problem, tmp_path):
        """Test that problem files are created correctly."""
        storage.save_problem(sample_problem)

        problem_dir = tmp_path / "problems" / "two-sum"
        assert problem_dir.exists()
        assert (problem_dir / "problem.md").exists()
        assert (problem_dir / "solution.py").exists()
        assert (problem_dir / "metadata.json").exists()

    def test_problem_md_content(self, storage, sample_problem, tmp_path):
        """Test that problem.md has correct content."""
        storage.save_problem(sample_problem)

        problem_md = tmp_path / "problems" / "two-sum" / "problem.md"
        content = problem_md.read_text(encoding="utf-8")
        assert content == sample_problem.content

    def test_solution_py_content(self, storage, sample_problem, tmp_path):
        """Test that solution.py has correct content."""
        storage.save_problem(sample_problem)

        solution_py = tmp_path / "problems" / "two-sum" / "solution.py"
        content = solution_py.read_text(encoding="utf-8")
        assert content == sample_problem.code_template

    def test_metadata_json_content(self, storage, sample_problem, tmp_path):
        """Test that metadata.json has correct content."""
        storage.save_problem(sample_problem)

        metadata_json = tmp_path / "problems" / "two-sum" / "metadata.json"
        metadata = json.loads(metadata_json.read_text(encoding="utf-8"))

        assert metadata["id"] == sample_problem.id
        assert metadata["slug"] == sample_problem.slug
        assert metadata["title"] == sample_problem.title
        assert metadata["difficulty"] == sample_problem.difficulty
        assert len(metadata["sample_test_cases"]) == 2
        assert metadata["sample_test_cases"][0]["input"] == "[2,7,11,15]\n9"
        assert metadata["sample_test_cases"][0]["expected"] == "[0,1]"

    def test_returns_solution_path(self, storage, sample_problem, tmp_path):
        """Test that save_problem returns the correct solution path."""
        solution_path = storage.save_problem(sample_problem)

        expected_path = tmp_path / "problems" / "two-sum" / "solution.py"
        assert solution_path == expected_path


class TestLoadProblem:
    """Tests for Storage.load_problem()."""

    def test_loads_saved_problem(self, storage, sample_problem):
        """Test that loading a saved problem returns correct Problem object."""
        storage.save_problem(sample_problem)
        loaded = storage.load_problem("two-sum")

        assert loaded.id == sample_problem.id
        assert loaded.slug == sample_problem.slug
        assert loaded.title == sample_problem.title
        assert loaded.difficulty == sample_problem.difficulty
        assert loaded.content == sample_problem.content
        assert loaded.code_template == sample_problem.code_template
        assert len(loaded.sample_test_cases) == len(sample_problem.sample_test_cases)
        assert loaded.sample_test_cases[0].input == sample_problem.sample_test_cases[0].input
        assert loaded.sample_test_cases[0].expected == sample_problem.sample_test_cases[0].expected

    def test_raises_problem_not_found_error(self, storage):
        """Test that ProblemNotFoundError is raised when problem doesn't exist."""
        with pytest.raises(ProblemNotFoundError) as exc_info:
            storage.load_problem("nonexistent-problem")

        assert exc_info.value.slug == "nonexistent-problem"


class TestGetSolutionCode:
    """Tests for Storage.get_solution_code()."""

    def test_reads_solution_content(self, storage, sample_problem):
        """Test that solution content is read correctly."""
        storage.save_problem(sample_problem)
        code = storage.get_solution_code("two-sum")

        assert code == sample_problem.code_template

    def test_raises_problem_not_found_error(self, storage):
        """Test that ProblemNotFoundError is raised when problem doesn't exist."""
        with pytest.raises(ProblemNotFoundError) as exc_info:
            storage.get_solution_code("nonexistent-problem")

        assert exc_info.value.slug == "nonexistent-problem"


class TestProblemExists:
    """Tests for Storage.problem_exists()."""

    def test_returns_true_when_exists(self, storage, sample_problem):
        """Test that True is returned when problem exists."""
        storage.save_problem(sample_problem)

        assert storage.problem_exists("two-sum") is True

    def test_returns_false_when_not_exists(self, storage):
        """Test that False is returned when problem doesn't exist."""
        assert storage.problem_exists("nonexistent-problem") is False


class TestListProblems:
    """Tests for Storage.list_problems()."""

    def test_empty_list_when_no_problems(self, storage):
        """Test that an empty list is returned when no problems exist."""
        result = storage.list_problems()

        assert result == []

    def test_returns_correct_slugs(self, storage, sample_problem):
        """Test that correct slugs are returned when problems exist."""
        storage.save_problem(sample_problem)

        another_problem = Problem(
            id=2,
            slug="add-two-numbers",
            title="Add Two Numbers",
            difficulty="Medium",
            content="# Add Two Numbers\n\nDescription...",
            code_template="class Solution:\n    def addTwoNumbers(self, l1, l2):\n        pass\n",
            sample_test_cases=[],
        )
        storage.save_problem(another_problem)

        result = storage.list_problems()

        assert "two-sum" in result
        assert "add-two-numbers" in result
        assert len(result) == 2

    def test_list_is_sorted(self, storage):
        """Test that the list of problems is sorted."""
        problems = [
            Problem(
                id=i,
                slug=slug,
                title=slug.replace("-", " ").title(),
                difficulty="Easy",
                content=f"# {slug}",
                code_template="pass",
                sample_test_cases=[],
            )
            for i, slug in enumerate(["zebra-problem", "alpha-problem", "middle-problem"])
        ]

        for problem in problems:
            storage.save_problem(problem)

        result = storage.list_problems()

        assert result == ["alpha-problem", "middle-problem", "zebra-problem"]


class TestGetConfig:
    """Tests for Storage.get_config()."""

    def test_returns_default_config_when_no_file(self, storage):
        """Test that default config is returned when no config file exists."""
        config = storage.get_config()

        assert config.language == DEFAULT_CONFIG.language
        assert config.editor == DEFAULT_CONFIG.editor
        assert config.browser == DEFAULT_CONFIG.browser
        assert config.profile == DEFAULT_CONFIG.profile

    def test_loads_config_from_file(self, storage, tmp_path):
        """Test that config is loaded from file when it exists."""
        tmp_path.mkdir(parents=True, exist_ok=True)
        config_data = {
            "language": "java",
            "editor": "code",
            "browser": "firefox",
            "profile": "work",
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_data), encoding="utf-8")

        config = storage.get_config()

        assert config.language == "java"
        assert config.editor == "code"
        assert config.browser == "firefox"
        assert config.profile == "work"


class TestSaveConfig:
    """Tests for Storage.save_config()."""

    def test_config_saved_correctly(self, storage, tmp_path):
        """Test that config is saved correctly."""
        config = Config(
            language="cpp",
            editor="nano",
            browser="safari",
            profile="personal",
        )

        storage.save_config(config)

        config_path = tmp_path / "config.json"
        assert config_path.exists()

        saved_data = json.loads(config_path.read_text(encoding="utf-8"))
        assert saved_data["language"] == "cpp"
        assert saved_data["editor"] == "nano"
        assert saved_data["browser"] == "safari"
        assert saved_data["profile"] == "personal"

    def test_round_trip_save_and_load(self, storage):
        """Test that config can be saved and loaded back correctly."""
        original_config = Config(
            language="rust",
            editor="emacs",
            browser="edge",
            profile="testing",
        )

        storage.save_config(original_config)
        loaded_config = storage.get_config()

        assert loaded_config.language == original_config.language
        assert loaded_config.editor == original_config.editor
        assert loaded_config.browser == original_config.browser
        assert loaded_config.profile == original_config.profile
