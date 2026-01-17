"""Local file operations for problem storage and configuration."""

import json
from pathlib import Path

from lc.exceptions import ProblemNotFoundError
from lc.models import Config, Problem, SampleTestCase


DEFAULT_CONFIG = Config(
    language="python3",
    editor="vim",
    browser="chrome",
    profile="Default",
)


class Storage:
    """Manages local file storage for problems and configuration."""

    def __init__(self, base_path: Path | None = None) -> None:
        self.base_path = base_path or Path.home() / ".leetcode"
        self.problems_dir = self.base_path / "problems"
        self.config_path = self.base_path / "config.json"

    def _ensure_dirs(self) -> None:
        """Create base directories if they don't exist."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.problems_dir.mkdir(parents=True, exist_ok=True)

    def _problem_dir(self, slug: str) -> Path:
        return self.problems_dir / slug

    def save_problem(self, problem: Problem) -> Path:
        """Save problem to disk. Returns the solution file path."""
        self._ensure_dirs()
        problem_dir = self._problem_dir(problem.slug)
        problem_dir.mkdir(parents=True, exist_ok=True)

        # Save problem description
        problem_md = problem_dir / "problem.md"
        problem_md.write_text(problem.content, encoding="utf-8")

        # Save code template
        solution_py = problem_dir / "solution.py"
        solution_py.write_text(problem.code_template, encoding="utf-8")

        # Save metadata
        metadata = {
            "id": problem.id,
            "slug": problem.slug,
            "title": problem.title,
            "difficulty": problem.difficulty,
            "sample_test_cases": [
                {"input": tc.input, "expected": tc.expected}
                for tc in problem.sample_test_cases
            ],
        }
        metadata_json = problem_dir / "metadata.json"
        metadata_json.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        return solution_py

    def load_problem(self, slug: str) -> Problem:
        """Load problem from disk."""
        if not self.problem_exists(slug):
            raise ProblemNotFoundError(slug)

        problem_dir = self._problem_dir(slug)

        # Load content
        problem_md = problem_dir / "problem.md"
        content = problem_md.read_text(encoding="utf-8")

        # Load code template
        solution_py = problem_dir / "solution.py"
        code_template = solution_py.read_text(encoding="utf-8")

        # Load metadata
        metadata_json = problem_dir / "metadata.json"
        metadata = json.loads(metadata_json.read_text(encoding="utf-8"))

        sample_test_cases = [
            SampleTestCase(input=tc["input"], expected=tc["expected"])
            for tc in metadata.get("sample_test_cases", [])
        ]

        return Problem(
            id=metadata["id"],
            slug=metadata["slug"],
            title=metadata["title"],
            difficulty=metadata["difficulty"],
            content=content,
            code_template=code_template,
            sample_test_cases=sample_test_cases,
        )

    def get_solution_code(self, slug: str) -> str:
        """Read the solution file content."""
        if not self.problem_exists(slug):
            raise ProblemNotFoundError(slug)

        solution_py = self._problem_dir(slug) / "solution.py"
        return solution_py.read_text(encoding="utf-8")

    def problem_exists(self, slug: str) -> bool:
        """Check if problem is saved locally."""
        problem_dir = self._problem_dir(slug)
        return (
            problem_dir.exists()
            and (problem_dir / "problem.md").exists()
            and (problem_dir / "solution.py").exists()
            and (problem_dir / "metadata.json").exists()
        )

    def list_problems(self) -> list[str]:
        """List all saved problem slugs."""
        if not self.problems_dir.exists():
            return []

        return sorted(
            d.name
            for d in self.problems_dir.iterdir()
            if d.is_dir() and self.problem_exists(d.name)
        )

    def get_config(self) -> Config:
        """Load config from config.json."""
        if not self.config_path.exists():
            return DEFAULT_CONFIG

        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        return Config(
            language=data.get("language", DEFAULT_CONFIG.language),
            editor=data.get("editor", DEFAULT_CONFIG.editor),
            browser=data.get("browser", DEFAULT_CONFIG.browser),
            profile=data.get("profile", DEFAULT_CONFIG.profile),
        )

    def save_config(self, config: Config) -> None:
        """Save config to config.json."""
        self._ensure_dirs()
        data = {
            "language": config.language,
            "editor": config.editor,
            "browser": config.browser,
            "profile": config.profile,
        }
        self.config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
