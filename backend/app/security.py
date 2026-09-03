"""Symmetric encryption for the one secret we store ourselves: the owner's payout
card number in admin_settings. Everything else sensitive (passwords, OAuth tokens,
card details for charges) lives with Supabase Auth or Stripe and never touches our DB.
"""
import os

from cryptography.fernet import Fernet, InvalidToken


def _fernet() -> Fernet:
    key = os.getenv("CARD_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "CARD_ENCRYPTION_KEY is not configured. Generate one with:\n"
            "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str:
    """Returns "" instead of raising when the stored value can't be decrypted
    (e.g. CARD_ENCRYPTION_KEY was rotated) so the admin panel still loads."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return ""
