# LeetCode CLI

Solve LeetCode problems from your terminal.

## Features

- Fetch problems with code templates
- Submit solutions directly from CLI
- Test against sample cases
- Reads session from Chrome (no manual token copying)
- Detects expired sessions and prompts re-login

## Installation

```bash
pip install -e .
```

## Usage

```bash
# Fetch a problem
lc fetch two-sum

# Edit in vim
vim ~/.leetcode/problems/two-sum/solution.py

# Submit
lc submit two-sum

# Or infer from current directory
cd ~/.leetcode/problems/two-sum
lc submit

# Test against sample cases
lc test two-sum

# List saved problems
lc list

# Show problem description
lc show two-sum

# Open in editor
lc open two-sum
```

## Requirements

- Python 3.10+
- Chrome browser (logged into leetcode.com)
- Linux (Chrome cookie decryption is Linux-specific)

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=src/lc

# Lint
ruff check src/ tests/

# Type check
mypy src/

# Format
ruff format src/ tests/
```

## License

MIT
