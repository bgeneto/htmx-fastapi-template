"""Add OTP code table for authentication

Revision ID: 0007_add_otp_code_table
Revises: 0006_add_phone_and_profile_picture
Create Date: 2025-11-23

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_add_otp_code_table"
down_revision: Union[str, None] = "0006_add_phone_and_profile_picture"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create OTP code table
    op.create_table(
        "otpcode",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("code", sa.String(length=6), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_otpcode_email"), "otpcode", ["email"], unique=False)
    op.create_index(op.f("ix_otpcode_expires_at"), "otpcode", ["expires_at"], unique=False)


def downgrade() -> None:
    # Drop OTP code table
    op.drop_index(op.f("ix_otpcode_expires_at"), table_name="otpcode")
    op.drop_index(op.f("ix_otpcode_email"), table_name="otpcode")
    op.drop_table("otpcode")