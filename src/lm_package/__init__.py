"""lm-package — Package Lumengine extensions into .lmext archives."""

__version__ = "1.0.0"

from lm_package.packager import create_package, PackageError
from lm_package.validator import validate_manifest

__all__ = ["create_package", "validate_manifest", "PackageError", "__version__"]