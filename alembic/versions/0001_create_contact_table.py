"""create contact table

Revision ID: 0001_create_contact
Revises:
Create Date: 2025-11-18 00:00:00.000000

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '0001_create_contact_table'
down_revision = '0000_extend_alembic_version_column'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "contact",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False, index=True),
        sa.Column("email", sa.String(length=320), nullable=False, index=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

def downgrade() -> None:
    op.drop_table("contact")
