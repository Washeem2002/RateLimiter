import hashlib

from app.core.config import get_settings


def hash_ip(ip: str) -> str:
    salt = get_settings().ip_hash_salt
    return hashlib.sha256(f"{salt}{ip}".encode()).hexdigest()
