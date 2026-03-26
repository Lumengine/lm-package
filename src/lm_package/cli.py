"""CLI entry point for lm-package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lm_package.packager import create_package, PackageError
from lm_package.signing import sign_package, generate_keys
from lm_package.validator import validate_manifest, is_cpp_project


def main():
    parser = argparse.ArgumentParser(
        prog="lm-package",
        description="Package a Lumengine extension into a .lmext archive.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to the extension project directory (default: current dir)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate manifest without creating a package",
    )
    parser.add_argument(
        "--build-dir", "-b",
        default=None,
        help="Build output directory for C++ extensions (e.g. Release/Plugins/MyExt)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output directory for the .lmext file (default: project dir)",
    )
    parser.add_argument(
        "--abi-tag",
        default="",
        help=(
            "ABI tag to inject into the manifest (e.g. msvc-win64-release). "
            "Format: {compiler}-{os_arch}-{config}"
        ),
    )
    parser.add_argument(
        "--sign",
        default=None,
        metavar="PRIVATE_KEY_FILE",
        help="Sign the package with an Ed25519 private key file (32 bytes, hex or raw)",
    )
    parser.add_argument(
        "--genkeys",
        default=None,
        metavar="OUTPUT_PREFIX",
        help="Generate an Ed25519 key pair (prefix.pub and prefix.key files)",
    )
    args = parser.parse_args()

    # Key generation mode
    if args.genkeys:
        generate_keys(args.genkeys)
        sys.exit(0)

    project_dir = Path(args.path).resolve()
    if not project_dir.is_dir():
        print(f"Error: '{args.path}' is not a directory", file=sys.stderr)
        sys.exit(1)

    manifest_path = project_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"Error: No manifest.json found in {project_dir}", file=sys.stderr)
        sys.exit(1)

    # Read manifest
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Inject abi_tag for validation if provided
    if args.abi_tag:
        manifest["abiTag"] = args.abi_tag

    # Validate
    errors = validate_manifest(manifest, project_dir)

    if args.validate:
        if errors:
            print("Validation FAILED:")
            for e in errors:
                print(f"  - {e}")
            sys.exit(1)
        else:
            abi_suffix = f" [{args.abi_tag}]" if args.abi_tag else ""
            print(f"Manifest OK: {manifest['id']} v{manifest['version']}{abi_suffix}")
            sys.exit(0)

    if errors:
        print("Manifest validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    # C++ guard: warn if CMakeLists.txt detected but no --build-dir
    cpp = is_cpp_project(project_dir)
    if cpp and not args.build_dir:
        print(
            "Error: This looks like a C++ extension (CMakeLists.txt found).\n"
            "       You need to build it first, then use --build-dir:\n"
            "\n"
            "  cmake --preset default\n"
            "  cmake --build build --config Release\n"
            f"  lm-package {args.path} --build-dir Release/Plugins/<PluginName>\n",
            file=sys.stderr,
        )
        sys.exit(1)

    # Resolve build dir relative to project
    build_dir = None
    if args.build_dir:
        build_dir = Path(args.build_dir)
        if not build_dir.is_absolute():
            build_dir = project_dir / build_dir
        build_dir = build_dir.resolve()

    # Package
    output_dir = Path(args.output).resolve() if args.output else project_dir
    try:
        pkg_path, sha256, size, file_count = create_package(
            project_dir, output_dir, build_dir, abi_tag=args.abi_tag,
        )
    except PackageError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Sign if requested
    signature = ""
    if args.sign:
        signature = sign_package(pkg_path, args.sign)

    # Report
    size_kb = size / 1024
    print(f"Package created: {pkg_path}")
    print(f"  ID:       {manifest['id']}")
    print(f"  Version:  {manifest['version']}")
    if args.abi_tag:
        print(f"  ABI tag:  {args.abi_tag}")
    print(f"  Type:     {'C++' if cpp else 'Python'}")
    print(f"  Files:    {file_count}")
    print(f"  Size:     {size_kb:.1f} KB")
    print(f"  SHA-256:  {sha256}")
    if signature:
        print(f"  Signed:   YES")
    print()
    print("Registry entry values:")
    print(f'  "packageUrl": "<upload-url>/{pkg_path.name}",')
    print(f'  "packageSize": {size},')
    print(f'  "sha256": "{sha256}"')
    if args.abi_tag:
        print(f'  "abiTag": "{args.abi_tag}"')
    if signature:
        print(f'  "signature": "{signature}"')


if __name__ == "__main__":
    main()