"""Add phone and profile_picture columns to user table

Revision ID: 0006_add_phone_and_profile_picture
Revises: 0005_add_fastapi_users_fields_to_user_model
Create Date: 2025-11-23

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_add_phone_and_profile_picture"
down_revision: Union[str, None] = "0005_add_fastapi_users_fields_to_user_model"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add phone column
    op.add_column(
        "user",
        sa.Column("phone", sa.String(length=20), nullable=True),
    )

    # Add profile_picture column
    op.add_column(
        "user",
        sa.Column("profile_picture", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    # Remove columns in reverse order
    op.drop_column("user", "profile_picture")
    op.drop_column("user", "phone")
