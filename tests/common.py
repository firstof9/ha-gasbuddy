"""Provide common pytest fixtures."""

import pathlib


def get_fixture_path(filename: str, integration: str | None = None) -> pathlib.Path:
    """Get path of fixture."""
    if integration is None and "/" in filename and not filename.startswith("helpers/"):
        integration, filename = filename.split("/", 1)

    if integration is None:
        return pathlib.Path(__file__).parent.joinpath("fixtures", filename)

    return pathlib.Path(__file__).parent.joinpath(
        "components", integration, "fixtures", filename
    )


def load_fixture(filename: str, integration: str | None = None) -> str:
    """Load a fixture."""
    return get_fixture_path(filename, integration).read_text(encoding="utf8")
