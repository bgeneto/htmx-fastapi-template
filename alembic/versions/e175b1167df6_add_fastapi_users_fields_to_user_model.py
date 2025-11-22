"""Add fastapi-users fields to User model

Revision ID: e175b1167df6
Revises: aa8369d40495
Create Date: 2025-11-22 19:31:11.610734

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e175b1167df6'
down_revision: Union[str, None] = 'aa8369d40495'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new fastapi-users fields with default values
    # Note: hashed_password was already VARCHAR(255), so we keep it as is
    # The model will handle empty strings for magic link users
    op.add_column('user', sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('user', sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='0'))
    
    # Update existing users: set is_verified based on email_verified
    op.execute("UPDATE user SET is_verified = email_verified WHERE email_verified = 1")
    
    # Update existing users: set is_superuser = True for ADMIN role  
    op.execute("UPDATE user SET is_superuser = 1 WHERE role = 'admin'")


def downgrade() -> None:
    op.drop_column('user', 'is_verified')
    op.drop_column('user', 'is_superuser')

