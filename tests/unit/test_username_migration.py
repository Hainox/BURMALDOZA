import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_username_migration_preserves_existing_users_and_is_reversible():
    path = (
        Path(__file__).resolve().parents[2] / "migrations/versions/20261013_0004_user_username.py"
    )
    spec = importlib.util.spec_from_file_location("username_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, display_name VARCHAR(255))"
        )
        connection.exec_driver_sql("INSERT INTO users VALUES (1, 'Existing')")
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert connection.exec_driver_sql(
                "SELECT id, display_name, username FROM users"
            ).all() == [(1, "Existing", None)]
            migration.downgrade()
            assert connection.exec_driver_sql("SELECT id, display_name FROM users").all() == [
                (1, "Existing")
            ]
    engine.dispose()
