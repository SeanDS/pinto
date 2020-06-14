PROGRAM = "pinto"

# Get package version.
try:
    from ._version import version as __version__
except ImportError:
    # Packaging resources are not installed.
    __version__ = "?.?.?"
