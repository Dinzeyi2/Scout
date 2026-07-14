import hashlib
import hmac
import secrets
from dataclasses import dataclass

from scout_backend.core.config import get_settings


@dataclass(frozen=True)
class GeneratedApiKey:
    plain_text: str
    prefix: str
    hash: str


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def verify_secret(secret: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_secret(secret), expected_hash)


def generate_api_key() -> GeneratedApiKey:
    prefix = get_settings().api_key_prefix
    token = prefix + secrets.token_urlsafe(32)
    return GeneratedApiKey(plain_text=token, prefix=token[:18], hash=hash_secret(token))
