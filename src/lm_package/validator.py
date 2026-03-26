"""Manifest and plugInfo validation for Lumengine extensions."""

from __future__ import annotations

import json
import re
from pathlib import Path

_VALID_ID = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*)+$")
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")

REQUIRED_MANIFEST_FIELDS = [
    "formatVersion", "id", "name", "version", "description",
    "author", "engine", "platforms", "pluginType",
]

# Plugin types that use USD SdfFileFormat registration (no pluginName check)
_USD_ONLY_PLUGIN_TYPES = {"importer"}


def is_cpp_project(project_dir: Path) -> bool:
    """Detect if this is a C++ extension project."""
    return (project_dir / "CMakeLists.txt").exists()


def validate_manifest(manifest: dict, project_dir: Path) -> list[str]:
    """Validate a manifest dict. Returns a list of errors (empty = valid)."""
    errors: list[str] = []

    # Required fields
    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest:
            errors.append(f"Missing required field: {field}")

    if errors:
        return errors

    # Format version
    if manifest["formatVersion"] != 1:
        errors.append(f"Unsupported formatVersion: {manifest['formatVersion']} (expected 1)")

    # ID format
    ext_id = manifest["id"]
    if not _VALID_ID.match(ext_id):
        errors.append(
            f"Invalid extension ID: '{ext_id}'. "
            f"Must be reverse-domain format (e.g. com.author.my-extension)"
        )

    # Version format
    version = manifest["version"]
    if not _SEMVER.match(version):
        errors.append(f"Invalid version: '{version}'. Must be semver (e.g. 1.0.0)")

    # Author
    author = manifest.get("author", {})
    if not isinstance(author, dict) or "name" not in author:
        errors.append("author must be an object with a 'name' field")

    # Engine
    engine = manifest.get("engine", {})
    if not isinstance(engine, dict) or "minVersion" not in engine:
        errors.append("engine must be an object with a 'minVersion' field")
    elif not _SEMVER.match(engine["minVersion"]):
        errors.append(f"Invalid engine.minVersion: '{engine['minVersion']}'")

    # Platforms
    platforms = manifest.get("platforms", [])
    valid_platforms = {"windows-x64", "linux-x64"}
    for p in platforms:
        if p not in valid_platforms:
            errors.append(f"Unknown platform: '{p}'. Valid: {valid_platforms}")

    # Plugin type
    valid_types = {"editor", "nodes", "importer", "extension-pack"}
    plugin_type = manifest.get("pluginType")
    if plugin_type not in valid_types:
        errors.append(f"Invalid pluginType: '{plugin_type}'. Valid: {valid_types}")

    # abiTag format (optional)
    abi_tag = manifest.get("abiTag", "")
    if abi_tag:
        abi_pattern = re.compile(r"^[a-z]+-[a-z0-9]+-[a-z]+$")
        if not abi_pattern.match(abi_tag):
            errors.append(
                f"Invalid abiTag: '{abi_tag}'. "
                f"Expected format: {{compiler}}-{{os_arch}}-{{config}} "
                f"(e.g. msvc-win64-release)"
            )

    # plugInfo.json validation — relaxed for USD-only plugin types (importers, etc.)
    if plugin_type in _USD_ONLY_PLUGIN_TYPES:
        # USD SdfFileFormat plugins don't have a pluginName matching the manifest ID.
        # They declare Types like "UsdFbxFileFormat" with bases: ["SdfFileFormat"].
        # We only check that a plugInfo.json exists somewhere (project root or resources/).
        _validate_pluginfo_exists(manifest, project_dir, errors, strict=False)
    else:
        _validate_pluginfo_exists(manifest, project_dir, errors, strict=True)

    return errors


def _validate_pluginfo_exists(
    manifest: dict,
    project_dir: Path,
    errors: list[str],
    *,
    strict: bool,
) -> None:
    """Check plugInfo.json exists and optionally validate pluginName match."""
    cpp = is_cpp_project(project_dir)
    if cpp:
        plug_info = project_dir / "plugInfo.json"
    else:
        plug_info = project_dir / "resources" / "plugInfo.json"

    if not plug_info.exists():
        errors.append(f"Missing {'plugInfo.json' if cpp else 'resources/plugInfo.json'}")
        return

    if not strict:
        return

    # Strict mode: validate pluginName matches manifest ID
    ext_id = manifest["id"]
    try:
        with open(plug_info, "r", encoding="utf-8") as f:
            plug_data = json.load(f)
        for plugin in plug_data.get("Plugins", []):
            types = plugin.get("Info", {}).get("Types", {})
            for _type_name, type_info in types.items():
                pname = type_info.get("pluginName", "")
                if pname and pname != ext_id:
                    errors.append(
                        f"plugInfo.json pluginName '{pname}' does not match "
                        f"manifest id '{ext_id}'. They must be identical."
                    )
    except (json.JSONDecodeError, OSError) as e:
        errors.append(f"Failed to read plugInfo.json: {e}")