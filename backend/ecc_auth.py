# ecc_auth.py — ECC (P-256 / ES256) JWT authentication layer for SmartRAG
#
# HOW IT WORKS
# ─────────────────────────────────────────────────────────────────────────────
# HS256 (old): one shared secret signs AND verifies.
#   → If the secret leaks, anyone can forge tokens forever.
#
# ES256 (new): asymmetric P-256 elliptic curve key pair.
#   PRIVATE KEY  → signs new JWTs at login/signup (server only, never exposed)
#   PUBLIC  KEY  → verifies incoming JWTs (can be published safely)
#   → A DB breach or env-var leak of the PUBLIC key cannot forge tokens.
#   → Only the private key can produce valid signatures.
#
# SETUP (one-time, run once then paste output into Render env vars)
# ─────────────────────────────────────────────────────────────────────────────
#   python ecc_auth.py
#
# This prints:
#   ECC_PRIVATE_KEY=<PEM>
#   ECC_PUBLIC_KEY=<PEM>
#
# Add both to your Render environment variables.
# ─────────────────────────────────────────────────────────────────────────────

import os
import json
import base64
import datetime

import jwt                                      # pip install PyJWT[crypto]
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


# ── Key loading ───────────────────────────────────────────────────────────────

def _load_private_key():
    """Load P-256 private key from ECC_PRIVATE_KEY env var (PEM string)."""
    pem = os.environ.get("ECC_PRIVATE_KEY", "").strip()
    if not pem:
        raise RuntimeError(
            "ECC_PRIVATE_KEY env var is not set. "
            "Run `python ecc_auth.py` once to generate keys, "
            "then add them to your Render environment variables."
        )
    # Env vars flatten newlines; restore them
    pem = pem.replace("\\n", "\n")
    return serialization.load_pem_private_key(
        pem.encode(), password=None, backend=default_backend()
    )


def _load_public_key():
    """Load P-256 public key from ECC_PUBLIC_KEY env var (PEM string)."""
    pem = os.environ.get("ECC_PUBLIC_KEY", "").strip()
    if not pem:
        raise RuntimeError(
            "ECC_PUBLIC_KEY env var is not set. "
            "Run `python ecc_auth.py` once to generate keys."
        )
    pem = pem.replace("\\n", "\n")
    return serialization.load_pem_public_key(pem.encode(), backend=default_backend())


# ── Token operations ──────────────────────────────────────────────────────────

def create_ecc_token(user_id: str, email: str, expiry_days: int = 7) -> str:
    """
    Sign a JWT with the P-256 private key using ES256 algorithm.

    Payload claims:
      sub   — user UUID
      email — user email
      iat   — issued-at timestamp
      exp   — expiry (default 7 days)
      alg   — echoed in payload for readability (actual alg in header)
    """
    private_key = _load_private_key()
    now = datetime.datetime.utcnow()
    payload = {
        "sub":   str(user_id),
        "email": email,
        "iat":   now,
        "exp":   now + datetime.timedelta(days=expiry_days),
    }
    token = jwt.encode(payload, private_key, algorithm="ES256")
    return token


def verify_ecc_token(token: str) -> dict | None:
    """
    Verify a JWT using the P-256 public key.

    Returns the decoded payload dict on success,
    or None if the signature is invalid, expired, or malformed.
    """
    try:
        public_key = _load_public_key()
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["ES256"],    # explicitly whitelist — never allow "none" or HS256
            options={"verify_exp": True},
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None   # token expired — user must log in again
    except jwt.InvalidTokenError:
        return None   # bad signature, tampered, wrong algorithm, etc.


# ── JWK export (public key as JSON Web Key) ───────────────────────────────────

def get_public_jwk() -> dict:
    """
    Export the public key as a JSON Web Key (JWK) object.

    This can be served at GET /auth/public-key so any client or auditor
    can verify tokens independently without server access.

    JWK fields for EC P-256:
      kty  — "EC"
      crv  — "P-256"
      x, y — base64url-encoded public key coordinates
      use  — "sig" (signature verification only)
      alg  — "ES256"
    """
    public_key = _load_public_key()
    pub_numbers = public_key.public_key().public_numbers() \
        if hasattr(public_key, "public_key") \
        else public_key.public_numbers()

    def _b64url(n: int, byte_len: int = 32) -> str:
        return base64.urlsafe_b64encode(
            n.to_bytes(byte_len, byteorder="big")
        ).rstrip(b"=").decode()

    return {
        "kty": "EC",
        "crv": "P-256",
        "x":   _b64url(pub_numbers.x),
        "y":   _b64url(pub_numbers.y),
        "use": "sig",
        "alg": "ES256",
    }


def get_public_key_pem() -> str:
    """Return the public key as a PEM string (for display at /auth/public-key)."""
    public_key = _load_public_key()
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()


# ── Key generation (run once) ─────────────────────────────────────────────────

def generate_and_print_keys():
    """
    Generate a fresh P-256 key pair and print both as PEM env var strings.
    Run this once:  python ecc_auth.py
    Then copy the output into Render → Environment Variables.
    """
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    public_key  = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ).decode().replace("\n", "\\n")

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode().replace("\n", "\\n")

    print("=" * 70)
    print("Copy these two lines into your Render environment variables:")
    print("=" * 70)
    print(f"ECC_PRIVATE_KEY={private_pem}")
    print(f"ECC_PUBLIC_KEY={public_pem}")
    print("=" * 70)
    print("Remove JWT_SECRET after confirming ES256 tokens work correctly.")


if __name__ == "__main__":
    generate_and_print_keys()