---
name: test_integration
description: Guide and instructions on how to run tests, set up test environments, and mock HTTP layers in the ha-gasbuddy repository.
---

# Testing the GasBuddy Integration

This guide helps AI agents run and add tests in this repository.

## Environment & Run Commands

Ensure you are using the correct Python version (target is 3.14) and dependencies:

```bash
# Setup virtual environment
uv venv --python 3.14
uv pip install -r requirements_test.txt
uv pip install 'ruff==0.15.14'

# Run the test suite
.venv/bin/python -m pytest -q --no-header
```

## Adding New Tests

Add new test cases to `tests/`. Identify the target area to add tests:
- `test_config_flow.py`: Form steps, reconfigurations, and options validation.
- `test_init.py`: Component setup, uninstallation, migration logic, and background services.
- `test_sensor.py`: Price state assertions, unit of measure changes, and device attribute assertions.
- **100% Coverage Rule**: All patch/added code in the PR must have **100% test coverage** before submission.

## Test Mocking Guidelines

- **HTTP Mocking**: Use `aioresponses` to mock the GraphQL endpoints (`https://www.gasbuddy.com/graphql`) and the web client page (`https://www.gasbuddy.com/home`).
- **Method Patching**: Avoid bypassing `price_lookup` on `py_gasbuddy.GasBuddy` by directly calling `process_request` in code, as this breaks existing HTTP-level mocks. Patch at the public method level or configure appropriate mock responses.
