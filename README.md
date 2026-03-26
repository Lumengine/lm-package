# lm-package

Package Lumengine extensions into `.lmext` archives.

Lightweight CLI tool (stdlib only) that validates, packages, and optionally signs Lumengine extensions for distribution via the Extension Manager.

## Installation

```bash
pip install lm-package          # base (stdlib only)
pip install lm-package[signing] # with Ed25519 signing (cryptography)
```

## Usage

```bash
# Package a Python extension
lm-package .

# Package a C++ extension from build output
lm-package . --build-dir Release/Plugins/MyExt

# Package with ABI tag (for native C++ extensions)
lm-package . --build-dir build/install --abi-tag msvc-win64-release

# Validate manifest without packaging
lm-package . --validate

# Generate Ed25519 key pair for signing
lm-package --genkeys my-publisher

# Package and sign
lm-package . --sign my-publisher.key
```

Also accessible via module:

```bash
python -m lm_package .
```

## ABI Tags

Native C++ extensions must specify an ABI tag to differentiate platform/config variants:

| Tag | Platform |
|-----|----------|
| `msvc-win64-release` | Windows x64 Release |
| `msvc-win64-debug` | Windows x64 Debug |
| `gcc-linux64-release` | Linux x64 Release |
| `gcc-linux64-debug` | Linux x64 Debug |

The `--abi-tag` flag injects the tag into the manifest embedded in the `.lmext` archive and appends it to the output filename.

## Manifest

Every extension requires a `manifest.json` at its root:

```json
{
    "formatVersion": 1,
    "id": "com.author.my-extension",
    "name": "My Extension",
    "version": "1.0.0",
    "description": "What it does",
    "author": { "name": "Author Name" },
    "engine": { "minVersion": "26.0.0" },
    "platforms": ["windows-x64", "linux-x64"],
    "pluginType": "editor"
}
```

Supported `pluginType` values: `editor`, `nodes`, `importer`, `extension-pack`.

## License

Apache-2.0