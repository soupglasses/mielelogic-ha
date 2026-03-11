"""Internal package version lookup."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mielelogic-api")
except PackageNotFoundError:
    __version__ = "1.0.0"
