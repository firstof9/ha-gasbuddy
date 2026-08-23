---
name: pr_workflow
description: Guide and instructions on how coding agents should format code, commit changes, run pre-commit checks, push branches, and create pull requests using the project templates.
---

# Pull Request Workflow for Agents

This guide assists AI agents in preparing, checking, and submitting Pull Requests (PRs) in this repository.

## 1. Code Preparation & Formatting
Before committing any changes, ensure all code conforms to the project's formatting and styling rules:

```bash
# Format the code using Ruff (target is Python 3.14)
.venv/bin/ruff format custom_components/ tests/

# Run lint checks and auto-fix simple errors
.venv/bin/ruff check --fix custom_components/ tests/
```

Verify that all local unit tests pass before opening a PR:
```bash
.venv/bin/python -m pytest -q --no-header
```

## 2. Git Staging & Commits
Stage changes and commit them with meaningful conventional commit messages:

```bash
git checkout -b feat/your-feature-branch
git add custom_components/ tests/
git commit -m "feat: Describe your changes clearly"
```

*Note: Staging/committing triggers local pre-commit hooks (like `ruff`, `codespell`, and large file checks). Make sure they pass.*

## 3. Creating the Pull Request
1. Push your branch to the remote:
   ```bash
   git push origin feat/your-feature-branch
   ```
2. Locate the project's PR template at `.github/PULL_REQUEST_TEMPLATE.md`.
3. Create the Pull Request (either using Git commands, the GitHub UI, or `github-mcp-server` tools).
4. **Important**: The PR description **must use the exact content of the PR template**. Do not delete sections from the template (unless explicitly instructed, e.g. the breaking changes warning when no breaking changes exist). Make sure all checkboxes indicating test status, formatting, and Conventional Commits are checked off appropriately.
