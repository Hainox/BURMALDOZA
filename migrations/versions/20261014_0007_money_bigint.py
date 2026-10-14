"""Use bigint for balances and monetary amounts.

Revision ID: 20261014_0007
Revises: 20261013_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261014_0007"
down_revision: str | None = "20261013_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONEY_COLUMNS = {
    "wallets": ("balance",),
    "ledger_entries": ("amount_delta", "balance_after"),
    "game_players": ("stack",),
    "game_rounds": ("bet_amount", "payout_amount"),
}


def upgrade() -> None:
    for table, columns in MONEY_COLUMNS.items():
        for column in columns:
            op.alter_column(table, column, existing_type=sa.Integer(), type_=sa.BigInteger(),
                            existing_nullable=False)


def downgrade() -> None:
    # Block writers before checking: never truncate funds or partially narrow tables.
    op.execute("LOCK TABLE wallets, ledger_entries, game_players, game_rounds IN ACCESS EXCLUSIVE MODE")
    connection = op.get_bind()
    for table, columns in MONEY_COLUMNS.items():
        for column in columns:
            if connection.scalar(sa.text(
                f"SELECT EXISTS (SELECT 1 FROM {table} "
                f"WHERE {column} < -2147483648 OR {column} > 2147483647)"
            )):
                raise RuntimeError(f"cannot downgrade: {table}.{column} contains values outside int32")
    for table, columns in MONEY_COLUMNS.items():
        for column in columns:
            op.alter_column(table, column, existing_type=sa.BigInteger(), type_=sa.Integer(),
                            existing_nullable=False)
