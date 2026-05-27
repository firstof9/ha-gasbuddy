# Contributing to ha-gasbuddy

Thanks for considering a contribution! This integration depends on
[py-gasbuddy](https://github.com/firstof9/py-gasbuddy) for the upstream
GraphQL client — bug fixes that affect the GasBuddy API itself usually
land there first, then this repo bumps the dependency.

> AI coding agents: also read [AGENTS.md](AGENTS.md), which covers
> repo-specific conventions in more detail than this file.

## Getting started

```bash
git clone https://github.com/firstof9/ha-gasbuddy
cd ha-gasbuddy

# Python 3.14 is required (matches the integration's target + CI)
uv venv --python 3.14
source .venv/bin/activate
uv pip install -r requirements_test.txt

# Install pre-commit hooks
pre-commit install
```

## Running tests

```bash
# Full suite (~15s)
pytest -q

# Single test
pytest tests/test_config_flow.py::test_form_manual_renders -v

# With coverage report
pytest --cov=custom_components/gasbuddy --cov-report=term-missing
```

CI enforces 80% coverage; the suite currently runs at 100%. Try to
keep it there when adding new code paths.

## Linting + formatting

```bash
pre-commit run --all-files
```

The project uses **ruff 0.15.14** (pinned in `.pre-commit-config.yaml`).
If you've installed a different ruff system-wide, install the pinned
version into your venv:

```bash
uv pip install 'ruff==0.15.14'
```

`pyproject.toml` ignores the `PLW0717` rule, which only exists in ruff
0.15.14+. An older ruff (such as 0.15.12) refuses to run at all with
`Unknown rule selector: PLW0717`, so match the pinned version.

### Python 3.14 syntax

The project targets Python 3.14 (`target-version = "py314"`). Ruff
format applies PEP 758 parenthesis-free `except` clauses:

```python
# What you might write:
except (TypeError, ValueError):
    ...

# What ruff format rewrites it to:
except TypeError, ValueError:
    ...
```

Both are valid Python 3.14. Don't fight the reformat.

## Pull requests

1. **Branch from `main`** (`git checkout -b fix/short-description`).
2. **Keep PRs small and focused.** One bug or one feature per PR. Big
   "polish bundles" are harder to review and revert.
3. **Run the full suite + pre-commit before pushing.** CI runs both.
4. **Add tests** for new behavior. Existing test files give good
   templates — see `tests/test_config_flow.py` for flow tests and
   `tests/test_ev_coverage.py` for coordinator/EV paths.
5. **Update translations** if you add a new user-facing string. The
   source is `strings.json`; mirror keys into `translations/en.json`,
   `translations/fr.json`, and `translations/pt.json`.
6. **Bump `CONFIG_VER`** in `const.py` if you change the config-entry
   data/options shape, and extend `async_migrate_entry` so existing
   users don't lose their config.
7. **Reference the issue** if there is one (`Fixes #232`).

## Translations

`strings.json` is the source of truth. Translations live under
`translations/`:

- `en.json` — mirror of `strings.json`
- `fr.json` — French (community-maintained)
- `pt.json` — Portuguese (community-maintained)

When you add a new key, add it to `strings.json` and `en.json` at
minimum. Native-speaker contributions for `fr.json` / `pt.json` are
welcome.

## Reporting bugs

Use the [issue tracker](https://github.com/firstof9/ha-gasbuddy/issues).
Useful information:

- Home Assistant version
- ha-gasbuddy version (from HACS or `manifest.json`)
- py-gasbuddy version (from HA logs at startup)
- Whether you're using FlareSolverr, and if so the version
- Relevant log lines (set `gasbuddy` to debug under `logger:` in
  `configuration.yaml`)

## Releases

The maintainer publishes releases via GitHub Releases. The manifest's
`"version": "0.0.0-dev"` is rewritten by the release pipeline.

## License

By contributing you agree your changes are licensed under the
project's existing license (see `LICENSE`).
