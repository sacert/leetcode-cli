# LeetCode CLI - Product Document

## Overview

A command-line interface tool that enables developers to solve LeetCode problems using their preferred terminal workflow. Write solutions in vim, submit directly from the CLI, and get instant feedback on test results.

## Problem Statement

The LeetCode web interface interrupts developer flow. Switching between browser and editor, copy-pasting code, and navigating the web UI creates friction. Developers want to stay in their terminal.

## Solution

A Python CLI that:
- Reads LeetCode session from Chrome's cookie store (no manual token copying)
- Fetches problems with code templates
- Submits solutions and displays results
- Detects expired sessions and prompts re-login

---

## User Stories

1. **As a developer**, I want to fetch a problem by its slug so I can work on it locally
2. **As a developer**, I want to submit my solution from the CLI so I don't leave my terminal
3. **As a developer**, I want to test against sample cases before submitting
4. **As a developer**, I want clear feedback when my session expires so I know to re-login
5. **As a developer**, I want to list problems so I can discover what to solve next

---

## Commands

### `lc fetch <slug>`
Fetches a problem and creates local files.

```bash
$ lc fetch two-sum

Fetching "Two Sum"...
Created: ~/.leetcode/problems/two-sum/
  - problem.md
  - solution.py
  - metadata.json

Open with: vim ~/.leetcode/problems/two-sum/solution.py
```

### `lc submit [slug]`
Submits solution to LeetCode.

```bash
$ lc submit two-sum

Submitting "Two Sum"...
✓ Accepted
  Runtime: 40ms (beats 95%)
  Memory: 14.2MB (beats 80%)

# Or with failure:
✗ Wrong Answer
  Test case 3/55 failed
  Input: [3,2,4], target=6
  Expected: [1,2]
  Got: [0,1]
```

**Slug resolution order:**
1. Explicit argument: `lc submit two-sum`
2. Current directory: `cd ~/.leetcode/problems/two-sum && lc submit`
3. Error with guidance if neither

### `lc test [slug]`
Runs solution against sample test cases locally (if possible) or via LeetCode's run API.

```bash
$ lc test two-sum

Running sample tests for "Two Sum"...
✓ Test 1 passed
✓ Test 2 passed
✓ Test 3 passed

All sample tests passed.
```

### `lc list`
Lists problems with optional filters.

```bash
$ lc list --difficulty easy --limit 10

#    Title                 Difficulty  Status
1    Two Sum               Easy        ✓ Solved
9    Palindrome Number     Easy        ✓ Solved
13   Roman to Integer      Easy        - Not attempted
...
```

### `lc show [slug]`
Displays problem description in terminal.

```bash
$ lc show two-sum

# Two Sum (Easy)

Given an array of integers nums and an integer target, return indices
of the two numbers such that they add up to target.
...
```

### `lc open [slug]`
Opens solution file in `$EDITOR` (defaults to vim).

```bash
$ lc open two-sum
# Opens vim with ~/.leetcode/problems/two-sum/solution.py
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                            CLI Layer                             │
│                         (click/typer)                            │
│  Commands: fetch, submit, test, list, show, open                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Session Manager                           │
│  - Validate session before API calls                            │
│  - Handle 401/403 → prompt re-login                             │
│  - Cache valid sessions                                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                ▼                               ▼
┌───────────────────────────┐   ┌─────────────────────────────────┐
│     Chrome Cookie Reader  │   │      LeetCode Client            │
│                           │   │                                 │
│  - Locate Chrome cookies  │   │  - GraphQL: problems, submit    │
│  - Read SQLite DB         │   │  - REST: submission polling     │
│  - Decrypt values (Linux) │   │  - Response parsing             │
└───────────────────────────┘   └─────────────────────────────────┘
                                                │
                                                ▼
                                ┌─────────────────────────────────┐
                                │       Problem Storage           │
                                │                                 │
                                │  - Read/write local files       │
                                │  - Manage ~/.leetcode/          │
                                └─────────────────────────────────┘
```

---

## File Structure

### Application Data
```
~/.leetcode/
├── config.toml              # User preferences
├── session_cache.json       # Cached session (optional optimization)
└── problems/
    └── {problem-slug}/
        ├── problem.md       # Problem description
        ├── solution.py      # User's solution (editable)
        └── metadata.json    # Problem ID, test cases, etc.
```

### Config File
```toml
# ~/.leetcode/config.toml

[general]
language = "python3"         # Default language for solutions
editor = "vim"               # Editor for 'lc open'

[browser]
name = "chrome"              # Browser to read cookies from
profile = "Default"          # Chrome profile name
```

### Metadata File
```json
{
  "id": 1,
  "slug": "two-sum",
  "title": "Two Sum",
  "difficulty": "Easy",
  "sample_test_cases": [
    {"input": "[2,7,11,15]\n9", "expected": "[0,1]"}
  ]
}
```

---

## Technical Specifications

### Language & Runtime
- Python 3.10+
- Package manager: pip with pyproject.toml

### Dependencies
| Package | Purpose |
|---------|---------|
| `typer` | CLI framework |
| `httpx` | HTTP client (async-capable) |
| `pycryptodome` | Chrome cookie decryption |
| `rich` | Terminal formatting |

### Chrome Cookie Decryption (Linux)

Chrome stores cookies in `~/.config/google-chrome/Default/Network/Cookies` (SQLite).

Values are encrypted with AES-128-CBC. The key derivation:
1. Read `Chrome Safe Storage` from GNOME Keyring or kwallet
2. If unavailable, use hardcoded key `peanuts` (Chrome's default)
3. PBKDF2 with salt `saltysalt`, 1 iteration, 16-byte key
4. Decrypt with IV of 16 space characters

### LeetCode API

**GraphQL Endpoint:** `https://leetcode.com/graphql/`

Required headers:
```
Cookie: LEETCODE_SESSION=xxx; csrftoken=xxx
X-CSRFToken: xxx
Referer: https://leetcode.com
```

**Key Queries:**

1. Fetch problem:
```graphql
query getQuestionDetail($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionId
    title
    difficulty
    content
    codeSnippets {
      lang
      langSlug
      code
    }
    sampleTestCase
  }
}
```

2. Submit solution:
```
POST /problems/{slug}/submit/
Body: {"lang": "python3", "question_id": "1", "typed_code": "..."}
Response: {"submission_id": 123456}
```

3. Check result:
```
GET /submissions/detail/{id}/check/
Response: {"state": "SUCCESS", "status_msg": "Accepted", ...}
```

### Session Expiry Detection

LeetCode returns:
- `401 Unauthorized` - session invalid
- `403 Forbidden` - CSRF token mismatch or expired

On either, display:
```
Session expired. Please login to leetcode.com in Chrome and retry.
```

---

## Coding Standards

### Design Philosophy

Follow the **Facade Pattern** from refactoring.guru:

> "Facade is a structural design pattern that provides a simplified interface to a library, framework, or complex set of classes."

Each module exposes a simple interface hiding internal complexity:

```python
# Good: Simple facade
class LeetCodeClient:
    def fetch_problem(self, slug: str) -> Problem: ...
    def submit_solution(self, slug: str, code: str) -> SubmissionResult: ...

# The CLI layer only interacts with this clean interface
```

### Code Style

1. **Simplicity over cleverness**
   - Prefer straightforward solutions
   - Avoid premature abstraction
   - One class/function should do one thing

2. **No redundant comments**
   - Do not explain "what" the code does
   - Only comment on "why" when non-obvious
   - Docstrings for public module interfaces only

   ```python
   # Bad
   def get_cookies():
       # Get the cookies from Chrome
       cookies = read_chrome_db()
       return cookies

   # Good
   def get_cookies():
       """Read LeetCode session cookies from Chrome's cookie store."""
       return read_chrome_db()
   ```

3. **Type hints everywhere**
   - All function signatures must have type hints
   - Use `typing` module for complex types
   - Enables IDE support and catches bugs early

4. **Flat is better than nested**
   - Early returns over deep nesting
   - Guard clauses at function start

   ```python
   # Bad
   def submit(slug):
       if slug:
           problem = find_problem(slug)
           if problem:
               result = send_submission(problem)
               if result:
                   return result

   # Good
   def submit(slug: str) -> SubmissionResult:
       if not slug:
           raise ValueError("Slug required")

       problem = find_problem(slug)
       if not problem:
           raise ProblemNotFound(slug)

       return send_submission(problem)
   ```

5. **Explicit dependencies**
   - Pass dependencies as arguments
   - Avoid global state
   - Makes testing straightforward

### Project Structure

```
leetcode-cli/
├── pyproject.toml
├── README.md
├── src/
│   └── lc/
│       ├── __init__.py
│       ├── cli.py              # CLI commands (typer app)
│       ├── client.py           # LeetCode API client
│       ├── cookies.py          # Chrome cookie reader
│       ├── session.py          # Session management
│       ├── storage.py          # Local file operations
│       ├── models.py           # Data classes (Problem, Submission, etc.)
│       └── exceptions.py       # Custom exceptions
└── tests/
    ├── conftest.py             # Shared fixtures
    ├── test_cli.py
    ├── test_client.py
    ├── test_cookies.py
    ├── test_session.py
    └── test_storage.py
```

---

## Testing Strategy

### Requirements
- Minimum 80% code coverage
- All public interfaces must have tests
- Use pytest as the test framework

### Test Types

1. **Unit Tests**
   - Test each module in isolation
   - Mock external dependencies (HTTP, filesystem, Chrome DB)
   - Fast execution

   ```python
   def test_submit_returns_accepted_result(mock_http):
       mock_http.post.return_value = {"submission_id": 123}
       mock_http.get.return_value = {"state": "SUCCESS", "status_msg": "Accepted"}

       client = LeetCodeClient(http=mock_http)
       result = client.submit_solution("two-sum", "def twoSum(): ...")

       assert result.accepted is True
   ```

2. **Integration Tests**
   - Test module interactions
   - Use temporary directories for file operations
   - May use recorded HTTP responses (VCR pattern)

3. **CLI Tests**
   - Use typer's `CliRunner`
   - Test command output and exit codes

   ```python
   def test_fetch_creates_problem_files(runner, tmp_path):
       result = runner.invoke(app, ["fetch", "two-sum"])

       assert result.exit_code == 0
       assert (tmp_path / "problems/two-sum/solution.py").exists()
   ```

### Fixtures

```python
# conftest.py

@pytest.fixture
def mock_leetcode_client():
    """Provides a mock LeetCode client for testing."""
    ...

@pytest.fixture
def sample_problem():
    """Returns a sample Problem object."""
    return Problem(
        id=1,
        slug="two-sum",
        title="Two Sum",
        difficulty="Easy",
        content="Given an array...",
        code_template="class Solution:\n    def twoSum(self, nums, target):\n        pass"
    )
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml

name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Lint with ruff
        run: ruff check src/ tests/

      - name: Type check with mypy
        run: mypy src/

      - name: Run tests with coverage
        run: pytest --cov=src/lc --cov-report=xml --cov-fail-under=80

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml

  build:
    runs-on: ubuntu-latest
    needs: test

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Build package
        run: |
          pip install build
          python -m build

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/
```

### Development Dependencies

```toml
# pyproject.toml

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "ruff>=0.1",
    "mypy>=1.0",
    "httpx[http2]",  # For async mock support
]
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml

repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.0.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

---

## Success Criteria

1. User can fetch, edit, and submit a LeetCode problem entirely from terminal
2. Session management is seamless - reads from Chrome, prompts on expiry
3. All commands complete in < 3 seconds (excluding network latency)
4. Test coverage >= 80%
5. Zero mypy errors, zero ruff errors

---

## Out of Scope (v1)

- Firefox/Safari/other browser support
- Multiple language support (Python only for v1)
- Contest participation
- Premium-only problems
- Solution history/versioning
- File watcher for auto-submit

---

## Future Considerations (v2+)

- `lc daily` - fetch the daily challenge
- `lc random --difficulty easy` - fetch a random problem
- `lc stats` - show user's solving statistics
- Browser selection in config
- Solution templates per problem type
