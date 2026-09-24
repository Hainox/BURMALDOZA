from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from burmaldoza_contracts.wallet import WalletSnapshot
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.idempotency import InvalidIdempotencyKey, parse_idempotency_key
from app.db.models import LedgerEntry
from app.db.session import get_session
from app.dependencies import CurrentUser, get_current_user
from app.services.wallet_service import LedgerResult, WalletService

router = APIRouter(prefix="/api/v1/wallet", tags=["wallet"])


def _ledger_result(result: LedgerResult) -> dict[str, object]:
    return {
        "operation_id": result.operation_id,
        "idempotency_key": result.idempotency_key,
        "user_id": result.user_id,
        "delta": result.delta,
        "balance_after": result.balance_after,
        "reason": result.reason,
        "reference_id": result.reference_id,
        "entries": [
            {
                "id": entry.id,
                "operation_id": entry.operation_id,
                "amount_delta": entry.amount_delta,
                "balance_after": entry.balance_after,
                "reason": entry.reason,
                "reference_id": entry.reference_id,
            }
            for entry in result.entries
        ],
    }


@router.get("", response_model=WalletSnapshot)
async def wallet(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WalletSnapshot:
    return await WalletService(session).get_or_create(current_user.user_id)


@router.get("/ledger")
async def ledger(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    entries = (
        await session.execute(
            select(LedgerEntry)
            .where(LedgerEntry.wallet_id == current_user.user_id)
            .order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc())
            .limit(100)
        )
    ).scalars()
    return [
        {
            "id": entry.id,
            "operation_id": entry.operation_id,
            "amount_delta": entry.amount_delta,
            "balance_after": entry.balance_after,
            "reason": entry.reason,
            "reference_type": entry.reference_type,
            "reference_id": entry.reference_id,
            "created_at": entry.created_at,
        }
        for entry in entries
    ]


def _request_key(x_request_id: str | None) -> UUID:
    try:
        return parse_idempotency_key(x_request_id)
    except InvalidIdempotencyKey as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/daily-bonus/claim")
async def claim_daily_bonus(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> dict[str, object]:
    key = _request_key(x_request_id)
    try:
        result = await WalletService(session).claim_daily_bonus(
            current_user.user_id, datetime.now(UTC), key
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _ledger_result(result)


@router.post("/relief/claim")
async def claim_relief_grant(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> dict[str, object]:
    key = _request_key(x_request_id)
    try:
        result = await WalletService(session).claim_relief_grant(
            current_user.user_id, datetime.now(UTC), key
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _ledger_result(result)
