import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

INDEX = "ix_ledger_entries_created_at_reason"


def test_ledger_week_index_migration_is_reversible():
    path = (
        Path(__file__).resolve().parents[2]
        / "migrations/versions/20261013_0006_ledger_week_index.py"
    )
    spec = importlib.util.spec_from_file_location("ledger_week_index", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "20261013_0005"
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE ledger_entries (id INTEGER PRIMARY KEY, reason VARCHAR(64), created_at DATETIME)"
        )
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            names = {index["name"] for index in sa.inspect(connection).get_indexes("ledger_entries")}
            assert INDEX in names
            migration.downgrade()
            names = {index["name"] for index in sa.inspect(connection).get_indexes("ledger_entries")}
            assert INDEX not in names
    engine.dispose()
