"""Add usage_count column to logintoken table

Revision ID: 0008_add_usage_count_to_logintoken
Revises: 0007_add_otp_code_table
Create Date: 2025-11-23

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_add_usage_count_to_logintoken"
down_revision: Union[str, None] = "0007_add_otp_code_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add usage_count column to logintoken table with default value 0
    op.add_column(
        "logintoken",
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    # Remove usage_count column
    op.drop_column("logintoken", "usage_count")