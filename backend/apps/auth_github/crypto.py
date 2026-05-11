from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _fernet() -> Fernet:
    key = settings.GITHUB_TOKEN_ENC_KEY
    if not key:
        raise ImproperlyConfigured(
            "GITHUB_TOKEN_ENC_KEY is required. Generate with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt(enc: str) -> str:
    return _fernet().decrypt(enc.encode("utf-8")).decode("utf-8")
