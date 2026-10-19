from sqlalchemy import Dialect, String
from sqlalchemy.types import TypeDecorator

from mealie.core.encryption import decrypt_secret, encrypt_secret


class EncryptedString(TypeDecorator):
    """
    SQLAlchemy TypeDecorator that encrypts string values before storing in SQLite/PostgreSQL
    and decrypts them when read back into the application.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return encrypt_secret(value)

    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return decrypt_secret(value)
