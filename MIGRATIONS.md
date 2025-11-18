# Using Alembic with this scaffold

This project uses SQLModel (SQLAlchemy underneath). For development the helper `app.create_db` runs `SQLModel.metadata.create_all`.
For production you should use Alembic migrations.

Quick steps to configure alembic:
- Update `alembic.ini` -> set `sqlalchemy.url = <your database url>` or use env vars.
- Run `alembic revision --autogenerate -m "init"` then `alembic upgrade head`.

If using async drivers, Alembic still runs sync migrations against DB URL; consult SQLAlchemy/Alembic docs for async patterns.
