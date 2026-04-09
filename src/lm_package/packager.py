"""Core packaging logic for Lumengine extensions."""

from __future__ import annotations

import hashlib
import json
import os
import zipfile
from pathlib import Path

from lm_package.validator import validate_manifest, is_cpp_project

EXCLUDE_PATTERNS = {
    "__pycache__", ".git", ".github", ".vscode", ".vs", "build", "dist",
    ".lmext", ".pyc", ".pyo", ".DS_Store", "Thumbs.db",
    ".gitignore", ".gitattributes",
    "Release", "Debug", "x64", ".sln", ".vcxproj",
}


class PackageError(Exception):
    pass


def should_exclude(path: str) -> bool:
    """Check if a file/dir should be excluded from the package."""
    parts = Path(path).parts
    for part in parts:
        if part in EXCLUDE_PATTERNS:
            return True
        for pattern in EXCLUDE_PATTERNS:
            if part.endswith(pattern):
                return True
    return False


def create_package(
    project_dir: Path,
    output_dir: Path,
    build_dir: Path | None = None,
    abi_tag: str = "",
) -> tuple[Path, str, int, int]:
    """Create a .lmext package.

    For Python extensions: packages source files from project_dir.
    For C++ extensions: packages build output from build_dir + manifest from project_dir.

    If abi_tag is provided, it is injected into the manifest embedded in the archive
    and appended to the output filename.

    Returns (path, sha256, size, file_count).
    """
    # Read manifest
    manifest_path = project_dir / "manifest.json"
    if not manifest_path.exists():
        raise PackageError(f"No manifest.json found in {project_dir}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Inject abi_tag into manifest before validation
    if abi_tag:
        manifest["abiTag"] = abi_tag

    # Validate
    errors = validate_manifest(manifest, project_dir)
    if errors:
        raise PackageError(
            "Manifest validation failed:\n" +
            "\n".join(f"  - {e}" for e in errors)
        )

    ext_id = manifest["id"]
    version = manifest["version"]

    # Filename includes abi_tag when present
    if abi_tag:
        filename = f"{ext_id.replace('.', '-')}-{version}-{abi_tag}.lmext"
    else:
        filename = f"{ext_id.replace('.', '-')}-{version}.lmext"

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    files: list[tuple[Path, str]] = []  # (absolute_path, archive_name)

    if build_dir:
        # C++ mode: package build output + manifest (with injected abiTag)
        if not build_dir.is_dir():
            raise PackageError(f"Build directory not found: {build_dir}")

        # manifest.json will be written from the modified dict (not copied from disk)
        # Everything from build_dir (lib/, resources/)
        for root, _dirs, filenames in os.walk(build_dir):
            for fname in filenames:
                full_path = Path(root) / fname
                rel_path = full_path.relative_to(build_dir)
                files.append((full_path, str(rel_path)))

        if not files:
            raise PackageError(f"No build output found in {build_dir}")

    else:
        # Python mode: package source files
        for root, dirs, filenames in os.walk(project_dir):
            dirs[:] = [d for d in dirs if not should_exclude(d)]

            for fname in filenames:
                full_path = Path(root) / fname
                rel_path = full_path.relative_to(project_dir)

                if should_exclude(str(rel_path)):
                    continue
                if full_path.suffix == ".lmext":
                    continue
                # Skip manifest.json — we write it from the (potentially modified) dict
                if str(rel_path) == "manifest.json":
                    continue

                files.append((full_path, str(rel_path)))

    # For C++ multi-plugin extensions, generate a root plugInfo.json so USD
    # can chain-discover sub-plugins (e.g. lidar/resources/, lidar_nodes/resources/).
    needs_discovery = (
        build_dir is not None
        and any(Path(arc).match("*/resources/plugInfo.json") for _, arc in files)
    )

    # Create ZIP
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Always write manifest first (from the in-memory dict, which may include abiTag)
        manifest_json = json.dumps(manifest, indent=4, ensure_ascii=False)
        zf.writestr("manifest.json", manifest_json)

        if needs_discovery:
            zf.writestr("plugInfo.json", '{\n    "Includes": ["*/resources/"]\n}\n')

        for abs_path, arc_name in sorted(files, key=lambda x: x[1]):
            zf.write(abs_path, arc_name)

    sha256 = _sha256(output_path)
    size = output_path.stat().st_size

    return output_path, sha256, size, len(files) + 1  # +1 for manifest


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()