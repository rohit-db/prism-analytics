"""``apex_app_users`` CRUD against Lakebase Postgres.

This is the edge's *own* user directory — the customer-facing login layer,
deliberately separate from Databricks workspace identity. Each row maps a login
to a tenant and an ``external_value`` (the handle passed to the AI/BI embed
token so Unity Catalog row filters scope the dashboard per tenant).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from edge import db

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS apex_app_users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) UNIQUE NOT NULL,
    -- pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>
    password_hash   TEXT NOT NULL,
    display_name    VARCHAR(255) NOT NULL,
    tenant          VARCHAR(255) NOT NULL,
    external_value  VARCHAR(255) NOT NULL DEFAULT '*',
    role            VARCHAR(50)  NOT NULL DEFAULT 'user',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_apex_app_users_email ON apex_app_users(email);
"""

_COLS = "email, password_hash, display_name, tenant, external_value, role, last_login_at"


@dataclass(frozen=True)
class UserRow:
    email: str
    password_hash: str
    display_name: str
    tenant: str
    external_value: str
    role: str
    last_login_at: Optional[datetime]


def _row(r) -> UserRow:
    return UserRow(
        email=r[0], password_hash=r[1], display_name=r[2],
        tenant=r[3], external_value=r[4], role=r[5], last_login_at=r[6],
    )


def ensure_schema() -> None:
    with db.get_connection() as conn:
        conn.execute(SCHEMA_SQL)
        conn.commit()


def get_by_email(email: str) -> Optional[UserRow]:
    with db.get_connection() as conn:
        cur = conn.execute(
            f"SELECT {_COLS} FROM apex_app_users WHERE LOWER(email) = LOWER(%s)",
            (email,),
        )
        row = cur.fetchone()
        return _row(row) if row else None


def list_all() -> list[UserRow]:
    with db.get_connection() as conn:
        cur = conn.execute(f"SELECT {_COLS} FROM apex_app_users ORDER BY email")
        return [_row(r) for r in cur.fetchall()]


def upsert(*, email: str, password_hash: str, display_name: str,
           tenant: str, external_value: str, role: str = "user") -> None:
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO apex_app_users "
            "(email, password_hash, display_name, tenant, external_value, role) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (email) DO UPDATE SET "
            "  password_hash = EXCLUDED.password_hash, "
            "  display_name  = EXCLUDED.display_name, "
            "  tenant        = EXCLUDED.tenant, "
            "  external_value = EXCLUDED.external_value, "
            "  role          = EXCLUDED.role",
            (email.lower(), password_hash, display_name, tenant, external_value, role),
        )
        conn.commit()


def touch_login(email: str) -> None:
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE apex_app_users SET last_login_at = NOW() "
            "WHERE LOWER(email) = LOWER(%s)",
            (email,),
        )
        conn.commit()
