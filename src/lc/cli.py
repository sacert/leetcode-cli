"""CLI interface for the LeetCode CLI using Typer."""

import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from lc.exceptions import CookieError, ProblemNotFoundError, SessionExpiredError
from lc.session import SessionManager
from lc.storage import Storage

app = typer.Typer(help="Solve LeetCode problems from your terminal")
console = Console()


def _resolve_slug(slug: Optional[str], storage: Storage) -> str:
    """Resolve slug from argument or current working directory."""
    if slug:
        return slug

    cwd = Path.cwd()
    problems_dir = storage.problems_dir

    if problems_dir in cwd.parents or cwd == problems_dir:
        # We're inside ~/.leetcode/problems/ or a subdirectory
        try:
            relative = cwd.relative_to(problems_dir)
            parts = relative.parts
            if parts:
                return parts[0]
        except ValueError:
            pass

    console.print(
        "[red]Error:[/red] No slug provided and not in a problem directory.\n"
        "Usage: lc <command> <slug> or cd to ~/.leetcode/problems/<slug>/"
    )
    raise typer.Exit(1)


def _handle_error(e: Exception) -> None:
    """Handle common exceptions with user-friendly messages."""
    if isinstance(e, SessionExpiredError):
        console.print("[red]Session expired. Please login to leetcode.com in Chrome and retry.[/red]")
    elif isinstance(e, ProblemNotFoundError):
        console.print(f"[red]Problem '{e.slug}' not found.[/red]")
    elif isinstance(e, CookieError):
        console.print(f"[red]{e.message}[/red]")
    else:
        console.print(f"[red]Error: {e}[/red]")
    raise typer.Exit(1)


@app.command()
def fetch(slug: str = typer.Argument(..., help="Problem slug (e.g., 'two-sum')")) -> None:
    """Fetch problem from LeetCode and save locally."""
    storage = Storage()
    session = SessionManager(storage)

    try:
        client = session.get_client()
        problem = client.fetch_problem(slug)
        console.print(f"Fetching '[bold]{problem.title}[/bold]'...")

        solution_path = storage.save_problem(problem)
        problem_dir = solution_path.parent

        console.print(f"[green]Created:[/green] {problem_dir}/")
        console.print("  - problem.md")
        console.print("  - solution.py")
        console.print("  - metadata.json")
        console.print(f"\nOpen with: [cyan]vim {solution_path}[/cyan]")
    except (SessionExpiredError, ProblemNotFoundError, CookieError) as e:
        _handle_error(e)


@app.command()
def submit(
    slug: Optional[str] = typer.Argument(None, help="Problem slug (optional if in problem directory)")
) -> None:
    """Submit solution to LeetCode."""
    storage = Storage()
    resolved_slug = _resolve_slug(slug, storage)
    session = SessionManager(storage)

    try:
        problem = storage.load_problem(resolved_slug)
        code = storage.get_solution_code(resolved_slug)
        client = session.get_client()

        console.print(f"Submitting '[bold]{problem.title}[/bold]'...")

        result = client.submit_solution(resolved_slug, problem.id, code)

        if result.accepted:
            console.print("[green bold]Accepted[/green bold]")
            if result.runtime:
                percentile = f" (beats {result.runtime_percentile:.0f}%)" if result.runtime_percentile else ""
                console.print(f"  Runtime: {result.runtime}{percentile}")
            if result.memory:
                percentile = f" (beats {result.memory_percentile:.0f}%)" if result.memory_percentile else ""
                console.print(f"  Memory: {result.memory}{percentile}")
        else:
            console.print(f"[red bold]{result.status_msg}[/red bold]")
            console.print(f"  Test case {result.test_cases_passed}/{result.total_test_cases} failed")
            if result.failed_test_case:
                console.print(f"  Input: {result.failed_test_case.input}")
                console.print(f"  Expected: {result.failed_test_case.expected}")
    except (SessionExpiredError, ProblemNotFoundError, CookieError) as e:
        _handle_error(e)


@app.command()
def test(
    slug: Optional[str] = typer.Argument(None, help="Problem slug (optional if in problem directory)")
) -> None:
    """Run solution against sample test cases."""
    storage = Storage()
    resolved_slug = _resolve_slug(slug, storage)
    session = SessionManager(storage)

    try:
        problem = storage.load_problem(resolved_slug)
        code = storage.get_solution_code(resolved_slug)
        client = session.get_client()

        console.print(f"Running sample tests for '[bold]{problem.title}[/bold]'...")

        if not problem.sample_test_cases:
            console.print("[yellow]No sample test cases found.[/yellow]")
            return

        test_input = problem.sample_test_cases[0].input
        result = client.run_tests(resolved_slug, problem.id, code, test_input)

        if result.accepted:
            for i in range(result.total_test_cases):
                console.print(f"[green]Test {i + 1} passed[/green]")
            console.print("\n[green bold]All sample tests passed.[/green bold]")
        else:
            passed = result.test_cases_passed
            total = result.total_test_cases
            for i in range(passed):
                console.print(f"[green]Test {i + 1} passed[/green]")
            console.print(f"[red]Test {passed + 1} failed[/red]")
            if result.failed_test_case:
                console.print(f"  Input: {result.failed_test_case.input}")
                console.print(f"  Expected: {result.failed_test_case.expected}")
            console.print(f"\n[red]{passed}/{total} tests passed.[/red]")
    except (SessionExpiredError, ProblemNotFoundError, CookieError) as e:
        _handle_error(e)


@app.command("list")
def list_problems(
    difficulty: Optional[str] = typer.Option(
        None, "--difficulty", "-d", help="Filter by difficulty (easy/medium/hard)"
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of problems to show"),
) -> None:
    """List locally saved problems."""
    storage = Storage()
    slugs = storage.list_problems()

    if not slugs:
        console.print("[yellow]No problems saved locally.[/yellow]")
        console.print("Use 'lc fetch <slug>' to fetch a problem.")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Slug", style="cyan")
    table.add_column("Title")
    table.add_column("Difficulty")

    count = 0
    for slug in slugs:
        if count >= limit:
            break

        try:
            problem = storage.load_problem(slug)
            prob_difficulty = problem.difficulty.lower()

            if difficulty and prob_difficulty != difficulty.lower():
                continue

            difficulty_color = {
                "easy": "green",
                "medium": "yellow",
                "hard": "red",
            }.get(prob_difficulty, "white")

            table.add_row(
                problem.slug,
                problem.title,
                f"[{difficulty_color}]{problem.difficulty}[/{difficulty_color}]",
            )
            count += 1
        except ProblemNotFoundError:
            continue

    if count == 0:
        console.print(f"[yellow]No problems found with difficulty '{difficulty}'.[/yellow]")
    else:
        console.print(table)


@app.command()
def show(
    slug: Optional[str] = typer.Argument(None, help="Problem slug (optional if in problem directory)")
) -> None:
    """Display problem description in terminal."""
    storage = Storage()
    resolved_slug = _resolve_slug(slug, storage)

    try:
        problem = storage.load_problem(resolved_slug)

        difficulty_color = {
            "easy": "green",
            "medium": "yellow",
            "hard": "red",
        }.get(problem.difficulty.lower(), "white")

        console.print(
            f"\n[bold]{problem.title}[/bold] ([{difficulty_color}]{problem.difficulty}[/{difficulty_color}])\n"
        )
        md = Markdown(problem.content)
        console.print(md)
    except ProblemNotFoundError as e:
        _handle_error(e)


@app.command("open")
def open_solution(
    slug: Optional[str] = typer.Argument(None, help="Problem slug (optional if in problem directory)")
) -> None:
    """Open solution file in editor."""
    storage = Storage()
    resolved_slug = _resolve_slug(slug, storage)

    try:
        if not storage.problem_exists(resolved_slug):
            raise ProblemNotFoundError(resolved_slug)

        config = storage.get_config()
        editor = config.editor
        solution_path = storage.problems_dir / resolved_slug / "solution.py"

        subprocess.run([editor, str(solution_path)])
    except ProblemNotFoundError as e:
        _handle_error(e)


if __name__ == "__main__":
    app()
