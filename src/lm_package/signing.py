"""Ed25519 package signing for Lumengine extensions."""

from __future__ import annotations

import sys
from pathlib import Path


def sign_package(pkg_path: Path, private_key_file: str) -> str:
    """Sign a .lmext package with Ed25519. Returns hex signature."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError:
        print("Error: 'cryptography' module required for signing.", file=sys.stderr)
        print("       Install with: pip install lm-package[signing]", file=sys.stderr)
        sys.exit(1)

    key_path = Path(private_key_file)
    key_data = key_path.read_bytes()

    # Support hex-encoded or raw 32-byte keys
    if len(key_data) == 64:
        key_bytes = bytes.fromhex(key_data.decode("ascii").strip())
    elif len(key_data) == 32:
        key_bytes = key_data
    else:
        try:
            key_bytes = bytes.fromhex(key_data.decode("ascii").strip())
        except (ValueError, UnicodeDecodeError):
            print("Error: Invalid private key file (expected 32 bytes or 64 hex chars)", file=sys.stderr)
            sys.exit(1)

    private_key = Ed25519PrivateKey.from_private_bytes(key_bytes)
    file_data = pkg_path.read_bytes()
    signature = private_key.sign(file_data)
    return signature.hex()


def generate_keys(prefix: str) -> None:
    """Generate an Ed25519 key pair for package signing."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError:
        print("Error: 'cryptography' module required for key generation.", file=sys.stderr)
        print("       Install with: pip install lm-package[signing]", file=sys.stderr)
        sys.exit(1)

    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes_raw()
    public_bytes = private_key.public_key().public_bytes_raw()

    priv_path = Path(f"{prefix}.key")
    pub_path = Path(f"{prefix}.pub")

    priv_path.write_text(private_bytes.hex(), encoding="ascii")
    pub_path.write_text(public_bytes.hex(), encoding="ascii")

    print(f"Key pair generated:")
    print(f"  Private key: {priv_path} (KEEP SECRET)")
    print(f"  Public key:  {pub_path}")
    print(f"  Public key (hex): {public_bytes.hex()}")
    print()
    print(f"Add the public key to your registry.json entry:")
    print(f'  "publicKey": "{public_bytes.hex()}"')