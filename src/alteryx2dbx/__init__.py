"""alteryx2dbx - Convert Alteryx workflows to PySpark Databricks notebooks."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("alteryx2dbx")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"
