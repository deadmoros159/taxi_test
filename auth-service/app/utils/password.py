from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

MAX_BCRYPT_PASSWORD_BYTES = 72


def _ensure_bcrypt_password_length(password: str) -> None:
    # bcrypt truncates at 72 bytes; passlib/bcrypt will raise for longer
    pw_bytes = password.encode("utf-8")
    if len(pw_bytes) > MAX_BCRYPT_PASSWORD_BYTES:
        raise ValueError(
            f"Password is too long for bcrypt (max {MAX_BCRYPT_PASSWORD_BYTES} bytes in UTF-8)"
        )


def hash_password(password: str) -> str:
    _ensure_bcrypt_password_length(password)
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    _ensure_bcrypt_password_length(password)
    return pwd_context.verify(password, password_hash)


