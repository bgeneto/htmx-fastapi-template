"""Add User and LoginToken tables with bootstrap admin

Revision ID: 0002_add_auth_tables
Revises: 0001_create_contact
Create Date: 2025-11-19

"""

from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel

from alembic import op
from app.config import settings

# revision identifiers, used by Alembic.
revision: str = "0002_add_auth_tables"
down_revision: Union[str, None] = "0001_create_contact_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create user table
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "email", sqlmodel.sql.sqltypes.AutoString(length=320), nullable=False
        ),
        sa.Column(
            "full_name", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False
        ),
        sa.Column(
            "hashed_password",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=True,
        ),
        sa.Column(
            "role",
            sa.Enum("PENDING", "USER", "MODERATOR", "ADMIN", name="userrole"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_email"), "user", ["email"], unique=True)

    # Create login_token table
    op.create_table(
        "logintoken",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "token_hash", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_logintoken_expires_at"), "logintoken", ["expires_at"], unique=False
    )
    op.create_index(
        op.f("ix_logintoken_token_hash"), "logintoken", ["token_hash"], unique=False
    )
    op.create_index(
        op.f("ix_logintoken_user_id"), "logintoken", ["user_id"], unique=False
    )

    # Seed bootstrap admin user
    now = datetime.utcnow()
    password_to_hash = settings.BOOTSTRAP_ADMIN_PASSWORD.get_secret_value()

    # Use fastapi-users' PasswordHelper for hashing (pwdlib with Argon2/Bcrypt)
    try:
        from fastapi_users.password import PasswordHelper

        password_helper = PasswordHelper()
        hashed_password = password_helper.hash(password_to_hash)
    except Exception as e:
        # If hashing fails, use a placeholder hash
        # This should not happen in normal operation
        print(f"Warning: Failed to hash password during migration: {e}")
        hashed_password = "$2b$12$placeholder.placeholder.placeholder.placeholder"

    op.execute(
        sa.text(
            """
            INSERT INTO user (email, full_name, hashed_password, role, is_active, email_verified, created_at, updated_at)
            VALUES (:email, :full_name, :hashed_password, :role, :is_active, :email_verified, :created_at, :updated_at)
            """
        ).bindparams(
            email=settings.BOOTSTRAP_ADMIN_EMAIL.lower(),
            full_name="Admin Istrator",
            hashed_password=hashed_password,
            role="ADMIN",
            is_active=True,
            email_verified=True,
            created_at=now,
            updated_at=now,
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_logintoken_user_id"), table_name="logintoken")
    op.drop_index(op.f("ix_logintoken_token_hash"), table_name="logintoken")
    op.drop_index(op.f("ix_logintoken_expires_at"), table_name="logintoken")
    op.drop_table("logintoken")

    op.drop_index(op.f("ix_user_email"), table_name="user")
    op.drop_table("user")

    # Drop enum type (PostgreSQL)
    op.execute("DROP TYPE IF EXISTS userrole")
