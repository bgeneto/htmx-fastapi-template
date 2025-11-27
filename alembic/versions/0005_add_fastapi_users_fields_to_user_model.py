"""Add fastapi-users fields to User model

Revision ID: e175b1167df6
Revises: aa8369d40495
Create Date: 2025-11-22 19:31:11.610734

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0005_add_fastapi_users_fields_to_user_model'
down_revision: Union[str, None] = '0004_create_book_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new fastapi-users fields with default values
    # Note: hashed_password was already VARCHAR(255), so we keep it as is
    # The model will handle empty strings for magic link users
    op.add_column('user', sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('user', sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.false()))

    # Update existing users: set is_verified based on email_verified
    # Use dialect-aware SQL for cross-database compatibility (PostgreSQL, MySQL, SQLite)
    bind = op.get_bind()
    if bind.engine.name == "mysql":
        # MySQL: Use backticks for identifiers, convert integer comparison to boolean
        op.execute('UPDATE `user` SET is_verified = (email_verified = 1) WHERE email_verified = 1')
    elif bind.engine.name == "postgresql":
        # PostgreSQL: Use double quotes for identifiers and explicit CAST
        op.execute('UPDATE "user" SET is_verified = CAST(email_verified AS BOOLEAN) WHERE email_verified = true')
    else:
        # SQLite: Direct assignment works (SQLite treats 1 as true for boolean columns)
        op.execute('UPDATE "user" SET is_verified = email_verified WHERE email_verified = 1')

    # Update existing users: set is_superuser = True for ADMIN role
    # Use dialect-aware SQL for cross-database compatibility
    if bind.engine.name == "mysql":
        # MySQL: Use backticks for identifiers
        op.execute('UPDATE `user` SET is_superuser = true WHERE role = "admin"')
    elif bind.engine.name == "postgresql":
        # PostgreSQL: Use double quotes for identifiers
        op.execute('UPDATE "user" SET is_superuser = true WHERE role = \'admin\'')
    else:
        # SQLite: Standard SQL syntax
        op.execute('UPDATE "user" SET is_superuser = true WHERE role = \'admin\'')


def downgrade() -> None:
    op.drop_column('user', 'is_verified')
    op.drop_column('user', 'is_superuser')
