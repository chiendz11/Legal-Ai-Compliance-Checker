"""Local web users. Passwords are verified here; routes never see the stored hash."""

from dataclasses import dataclass

from legal_checker.core.postgres import connect_postgres
from legal_checker.core.security import Actor
from legal_checker.modules.accounts.security import hash_password, verify_password

ROLES = ("viewer", "uploader", "reviewer", "publisher")
# Spent on unknown users too, so response time does not reveal which user IDs exist.
_DUMMY_HASH = hash_password("timing-equaliser-not-a-password")


@dataclass(frozen=True)
class User:
    user_id: str
    tenant_id: str
    display_name: str
    roles: tuple[str, ...]
    disabled: bool

    def actor(self) -> Actor:
        return Actor(self.user_id, self.tenant_id, frozenset(self.roles))


def _user(row) -> User:
    return User(
        row["user_id"], row["tenant_id"], row["display_name"], tuple(row["roles"]), row["disabled"]
    )


class UserRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def create(
        self, user_id: str, tenant_id: str, display_name: str, roles: list[str], password: str
    ) -> User:
        unknown = set(roles) - set(ROLES)
        if unknown:
            raise ValueError(f"Unknown roles: {sorted(unknown)}")
        with connect_postgres(self.database_url) as connection:
            row = connection.execute(
                """INSERT INTO runtime.app_users
                   (user_id, tenant_id, display_name, roles, password_hash)
                   VALUES (%s, %s, %s, %s, %s) RETURNING *""",
                (user_id, tenant_id, display_name, sorted(set(roles)), hash_password(password)),
            ).fetchone()
        return _user(row)

    def set_password(self, user_id: str, password: str) -> None:
        with connect_postgres(self.database_url) as connection:
            connection.execute(
                "UPDATE runtime.app_users SET password_hash=%s WHERE user_id=%s",
                (hash_password(password), user_id),
            )

    def set_disabled(self, user_id: str, disabled: bool) -> None:
        with connect_postgres(self.database_url) as connection:
            connection.execute(
                "UPDATE runtime.app_users SET disabled=%s WHERE user_id=%s", (disabled, user_id)
            )

    def get(self, user_id: str) -> User | None:
        with connect_postgres(self.database_url) as connection:
            row = connection.execute(
                "SELECT * FROM runtime.app_users WHERE user_id=%s", (user_id,)
            ).fetchone()
        return _user(row) if row else None

    def list(self) -> list[User]:
        with connect_postgres(self.database_url) as connection:
            rows = connection.execute("SELECT * FROM runtime.app_users ORDER BY user_id").fetchall()
        return [_user(row) for row in rows]

    def authenticate(self, user_id: str, password: str) -> User | None:
        with connect_postgres(self.database_url) as connection:
            row = connection.execute(
                "SELECT * FROM runtime.app_users WHERE user_id=%s", (user_id,)
            ).fetchone()
        if row is None:
            verify_password(password, _DUMMY_HASH)
            return None
        if not verify_password(password, row["password_hash"]) or row["disabled"]:
            return None
        return _user(row)
