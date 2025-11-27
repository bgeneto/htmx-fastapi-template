"""Extend alembic_version column to support longer version names.

Revision ID: 0001_extend_alembic_version_column
Revises: None (this is the initial migration)
Create Date: 2025-11-26 12:00:00.000000

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '0000_extend_alembic_version_column'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Extend alembic_version.version_num from 32 to 128 characters."""
    # Get the database dialect
    dialect = op.get_context().dialect.name

    if dialect == 'postgresql':
        # PostgreSQL: use ALTER COLUMN TYPE
        op.alter_column(
            'alembic_version',
            'version_num',
            existing_type=sa.String(32),
            type_=sa.String(128),
            existing_nullable=False
        )
    elif dialect == 'sqlite':
        # SQLite doesn't support ALTER COLUMN, so we need a workaround
        # SQLite will recreate the table automatically via alembic
        op.alter_column(
            'alembic_version',
            'version_num',
            existing_type=sa.String(32),
            type_=sa.String(128),
            existing_nullable=False
        )
    elif dialect == 'mysql':
        # MySQL: use MODIFY COLUMN
        op.alter_column(
            'alembic_version',
            'version_num',
            existing_type=sa.String(32),
            type_=sa.String(128),
            existing_nullable=False
        )


def downgrade() -> None:
    """Revert alembic_version.version_num back to 32 characters."""
    dialect = op.get_context().dialect.name

    if dialect == 'postgresql':
        op.alter_column(
            'alembic_version',
            'version_num',
            existing_type=sa.String(128),
            type_=sa.String(32),
            existing_nullable=False
        )
    elif dialect == 'sqlite':
        op.alter_column(
            'alembic_version',
            'version_num',
            existing_type=sa.String(128),
            type_=sa.String(32),
            existing_nullable=False
        )
    elif dialect == 'mysql':
        op.alter_column(
            'alembic_version',
            'version_num',
            existing_type=sa.String(128),
            type_=sa.String(32),
            existing_nullable=False
        )
