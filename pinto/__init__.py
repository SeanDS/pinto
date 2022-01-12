"""Supercharged command line interface for Beancount."""

PROGRAM = "pinto"

# Get package version.
try:
    from ._version import version as __version__
except ImportError:
    raise Exception("Could not find version.py. Ensure you have run setup.")
