"""Accessors for the package's version information.
"""

from pkg_resources import DistributionNotFound, get_distribution

try:
    __version__ = get_distribution("strimzi-registry-operator").version
except DistributionNotFound:
    # Package is not installed
    __version__ = "unknown"


def print_version():
    print(__version__)


if __name__ == "__main__":
    print_version()
