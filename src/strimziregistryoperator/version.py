"""Accessors for the package's version information."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("strimzi-registry-operator")
except PackageNotFoundError:
    __version__ = "unknown"


def get_version() -> str:
    """Return the current version string."""
    return __version__


if __name__ == "__main__":
    print(get_version())  # noqa: T201
