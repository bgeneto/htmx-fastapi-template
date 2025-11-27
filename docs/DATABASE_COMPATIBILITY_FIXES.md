# Database Compatibility Fixes for Alembic Migrations

## Summary

All Alembic migrations have been audited and fixed for **PostgreSQL**, **MySQL**, and **SQLite** compatibility.

## Issues Identified and Fixed

### 1. Migration 0002_add_auth_tables.py
**Issue**: PostgreSQL-specific ENUM type management
```python
# BEFORE: Would fail on MySQL/SQLite
op.execute("DROP TYPE IF EXISTS userrole")
```

**Fix**: Added dialect detection
```python
# AFTER: Works on all databases
bind = op.get_bind()
if bind.engine.name == "postgresql":
    op.execute("DROP TYPE IF EXISTS userrole")
```

**Why**:
- PostgreSQL: Has separate ENUM types that must be dropped
- MySQL: Stores ENUM values inline in column definition (no separate type)
- SQLite: Doesn't support ENUM at all (stored as TEXT)

---

### 2. Migration 0005_add_fastapi_users_fields_to_user_model.py

#### Issue A: Boolean Type Casting
```python
# BEFORE: PostgreSQL-specific syntax
op.execute('UPDATE "user" SET is_verified = CAST(email_verified AS BOOLEAN) WHERE email_verified = 1')
```

**Fix**: Dialect-aware implementations
```python
# AFTER: Works on all databases
bind = op.get_bind()
if bind.engine.name == "mysql":
    op.execute('UPDATE `user` SET is_verified = (email_verified = 1) WHERE email_verified = 1')
elif bind.engine.name == "postgresql":
    op.execute('UPDATE "user" SET is_verified = CAST(email_verified AS BOOLEAN) WHERE email_verified = true')
else:  # SQLite
    op.execute('UPDATE "user" SET is_verified = email_verified WHERE email_verified = 1')
```

**Why**:
- **PostgreSQL**: Requires `CAST(... AS BOOLEAN)` for strict type conversion
- **MySQL**: Doesn't support `CAST(... AS BOOLEAN)` - use boolean expression `(x = 1)` instead
- **SQLite**: Direct assignment works; treats integers as boolean-compatible

#### Issue B: Identifier Quoting
```python
# BEFORE: Mixed quoting styles
op.execute('UPDATE "user" SET is_superuser = 1 WHERE role = \'admin\'')
```

**Fix**: Dialect-appropriate quoting
```python
# AFTER: Correct quoting per database
bind = op.get_bind()
if bind.engine.name == "mysql":
    op.execute('UPDATE `user` SET is_superuser = true WHERE role = "admin"')  # Backticks
elif bind.engine.name == "postgresql":
    op.execute('UPDATE "user" SET is_superuser = true WHERE role = \'admin\'')  # Double quotes
else:  # SQLite
    op.execute('UPDATE "user" SET is_superuser = true WHERE role = \'admin\'')  # Double quotes
```

**Why**:
- **PostgreSQL**: Uses `"identifier"` for reserved words/case-sensitive names
- **MySQL**: Uses `` `identifier` `` (backticks) as standard
- **SQLite**: Accepts both `"identifier"` and `` `identifier` ``
- **String literals**: All databases use single quotes `'string'`

#### Issue C: Boolean Literal Values
```python
# BEFORE: Integer 1 for boolean
WHERE email_verified = 1
SET is_superuser = 1
```

**Fix**: Standard SQL boolean literals
```python
# AFTER: Platform-aware boolean values
if bind.engine.name == "mysql":
    WHERE email_verified = 1  # MySQL integer comparison
else:
    WHERE email_verified = true  # PostgreSQL/SQLite boolean literals
```

**Why**:
- **PostgreSQL**: Strict type checking; `boolean = integer` is an error
- **MySQL**: More lenient; accepts integer comparisons for boolean columns
- **SQLite**: Treats integers as boolean (1=true, 0=false)

---

## Cross-Database Compatibility Table

| Feature | PostgreSQL | MySQL | SQLite |
|---------|-----------|-------|--------|
| ENUM Types | Separate type objects | Inline in column | Not supported |
| Boolean Literals | `true`/`false` | `1`/`0` or `true`/`false` | `1`/`0` or `true`/`false` |
| CAST to BOOLEAN | ✅ Supported | ❌ Not supported | ✅ Supported |
| Identifier Quoting | `"identifier"` | `` `identifier` `` | Both accepted |
| Type Strictness | Strict (errors on mismatch) | Lenient | Very lenient |

---

## Testing Your Migrations

### PostgreSQL
```bash
export DATABASE_URL="postgresql://user:pass@localhost/dbname"
alembic upgrade head
```

### MySQL
```bash
export DATABASE_URL="mysql+pymysql://user:pass@localhost/dbname"
alembic upgrade head
```

### SQLite (Development)
```bash
export DATABASE_URL="sqlite:///./test.db"
alembic upgrade head
```

---

## Files Modified

1. `alembic/versions/0002_add_auth_tables.py` - Added PostgreSQL ENUM type check
2. `alembic/versions/0005_add_fastapi_users_fields_to_user_model.py` - Added dialect-aware UPDATE statements

---

## Best Practices for Future Migrations

1. **Avoid raw SQL when possible** - Use Alembic operations:
   ```python
   # Prefer this (handled by SQLAlchemy):
   op.add_column('table', sa.Column('col', sa.Boolean()))

   # Avoid raw SQL:
   op.execute("ALTER TABLE table ADD COLUMN col BOOLEAN")
   ```

2. **For necessary raw SQL, detect the dialect**:
   ```python
   bind = op.get_bind()
   if bind.engine.name == "postgresql":
       # PostgreSQL-specific SQL
   elif bind.engine.name == "mysql":
       # MySQL-specific SQL
   else:  # sqlite
       # SQLite SQL
   ```

3. **Use proper identifier quoting**:
   - PostgreSQL: `"identifier"` (when needed)
   - MySQL: `` `identifier` `` (when needed)
   - SQLite: Either style

4. **Use standard SQL boolean literals**:
   - Use `true`/`false` for PostgreSQL
   - Use `1`/`0` for MySQL
   - SQLite accepts both

5. **Test on all target databases** before deployment

---

## References

- [Alembic - The SQLAlchemy Migrations Tool](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Dialect-Specific Constructs](https://docs.sqlalchemy.org/en/20/faq/api.html)
- [PostgreSQL Data Types](https://www.postgresql.org/docs/current/datatype.html)
- [MySQL Data Types](https://dev.mysql.com/doc/refman/8.0/en/data-types.html)
- [SQLite Data Types](https://www.sqlite.org/datatype.html)
