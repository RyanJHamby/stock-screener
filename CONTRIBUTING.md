# Contributing

Thanks for your interest in contributing to the Intelligent Stock Screener.

## Ways to Contribute

- **Bug reports** — Open an issue with steps to reproduce, expected behavior, and actual behavior
- **Feature requests** — Open an issue describing the use case and why it fits the project's scope
- **Pull requests** — Bug fixes and well-scoped features are welcome

## Development Setup

```bash
git clone https://github.com/RyanJHamby/stock-screener.git
cd stock-screener
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Code Standards

- **Python 3.12+** with type hints on all public functions
- **Black** for formatting (`pip install black && black .`)
- **pytest** for tests — new features should include tests, coverage target is 80%+
- Docstrings on public functions (one-line summary is enough for simple functions)

## Running Tests

```bash
pytest tests/
```

## Pull Request Guidelines

1. Fork the repo and create a branch from `main`
2. Keep PRs focused — one logical change per PR
3. Include tests for new behavior
4. Run `black .` before pushing
5. Describe *why* the change is needed, not just what it does

## Scope

This project implements Mark Minervini's Trend Template methodology. Contributions that stay within that philosophy (phase-based trend analysis, relative strength, risk management) are most likely to be merged. Proposals to add fundamentally different screening methodologies are better suited as forks.

## Questions

Open an issue — no question is too small.
