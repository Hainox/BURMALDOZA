from __future__ import annotations

import asyncio
from uuid import UUID

from burmaldoza_contracts.common import GameType
from burmaldoza_contracts.rooms import (
    ActionRequest,
    RoomCreateRequest,
    RoomSnapshot,
    WebSocketAuthMessage,
)
from burmaldoza_domain.core import StateVersionConflictError
from burmaldoza_domain.games.slot_ruleset import SLOT_RULESET_VERSIONS
from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel, ConfigDict

from app.core.idempotency import InvalidIdempotencyKey, parse_idempotency_key
from app.dependencies import (
    CurrentUser,
    get_app_settings,
    get_current_user,
    get_event_bus,
    get_room_service,
)
from app.services.room_service import (
    MAX_BET,
    RoomAccessError,
    RoomNotFoundError,
    RoomService,
    RoomServiceError,
)
from app.services.wallet_service import WalletService

router = APIRouter(prefix="/api/v1", tags=["rooms"])

WEBSOCKET_AUTH_TIMEOUT_SECONDS = 5.0


@router.get("/rooms/{room_id}/opponent-avatar")
async def opponent_avatar(
    room_id: UUID,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    service: RoomService = Depends(get_room_service),
):
    from fastapi.responses import Response

    from app.db.models import User
    from app.services.holdem_service import HoldemService
    from app.services.opponent_avatar import AvatarError, AvatarService

    headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    try:
        # snapshot checks membership even on a cache hit. Release the DB
        # transaction before waiting on Telegram, without touching game state.
        snapshot = await service.snapshot(room_id, current_user.user_id)
        avatars = getattr(request.app.state, "opponent_avatars", None)
        if avatars is None:
            avatars = AvatarService(get_app_settings(request).bot_token)
            request.app.state.opponent_avatars = avatars
        avatars.check_viewer(current_user.user_id)
        if snapshot.game_type != GameType.HOLDEM or snapshot.mode != "pvp":
            return Response(status_code=204, headers=headers)
        async with service.session.begin():
            members = await HoldemService(service).members(room_id)
            opponent_id = next((value for value in members.values()
                                if value != current_user.user_id), None)
            if opponent_id is None:
                return Response(status_code=204, headers=headers)
            opponent = await service.session.get(User, opponent_id)
            telegram_id = opponent.telegram_user_id
    except RoomNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RoomAccessError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except AvatarError as error:
        return Response(status_code=error.status,
                        headers={**headers, "Retry-After": str(error.retry_after)})
    try:
        photo = await avatars.get(telegram_id)
    except AvatarError as error:
        return Response(status_code=error.status,
                        headers={**headers, "Retry-After": str(error.retry_after)})
    if photo is None:
        return Response(status_code=204, headers=headers)
    body, media_type = photo
    return Response(body, media_type=media_type, headers=headers)


class GameInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    game_type: GameType
    ruleset_version: str
    status: str = "available"


_RULESETS: dict[GameType, dict[str, object]] = {
    GameType.SLOT: {
        "game_type": GameType.SLOT,
        "version": "slot-siege-2",
        "columns": 3,
        "rows": 7,
        "min_bet": 10,
        "max_bet": MAX_BET,
    },
    GameType.BLACKJACK: {
        "game_type": GameType.BLACKJACK,
        "version": "blackjack-gfl-skeleton-1",
        "min_bet": 25,
        "max_bet": MAX_BET,
        "blackjack_payout": "3:2",
    },
    GameType.HOLDEM: {
        "game_type": GameType.HOLDEM,
        "version": "holdem-v1",
        "buy_ins": [100, 500, 1000],
        "modes": ["bot", "pvp"],
        "turn_timeout_seconds": 20,
        "search_timeout_seconds": 60,
        "max_players": 2,
    },
}


@router.get("/games", response_model=list[GameInfo])
async def games(current_user: CurrentUser = Depends(get_current_user)) -> list[GameInfo]:
    del current_user
    return [
        GameInfo(game_type=GameType.SLOT, ruleset_version="slot-siege-2"),
        GameInfo(game_type=GameType.BLACKJACK, ruleset_version="blackjack-gfl-skeleton-1"),
        GameInfo(game_type=GameType.HOLDEM, ruleset_version="holdem-v1"),
    ]


@router.get("/rulesets/{game_type}/{version}")
async def ruleset(
    game_type: GameType,
    version: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, object]:
    del current_user
    definition = _RULESETS.get(game_type)
    if game_type is GameType.SLOT and version in SLOT_RULESET_VERSIONS:
        return {**_RULESETS[GameType.SLOT], "version": version}
    if definition is None or definition["version"] != version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ruleset not found")
    return definition


@router.get("/holdem/history")
async def holdem_history(
    limit: int = Query(default=15, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    service: RoomService = Depends(get_room_service),
) -> dict[str, object]:
    from app.services.holdem_service import HoldemService

    return {
        "items": await HoldemService(service).history(current_user.user_id, limit, offset),
        "limit": limit,
        "offset": offset,
    }


@router.post("/rooms", response_model=RoomSnapshot)
async def create_room(
    payload: RoomCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: RoomService = Depends(get_room_service),
) -> RoomSnapshot:
    try:
        return await service.create_room(
            current_user.user_id,
            payload.game_type,
            payload.mode,
            buy_in=payload.buy_in,
            action_id=payload.action_id,
        )
    except RoomServiceError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/rooms/{room_id}", response_model=RoomSnapshot)
async def room_snapshot(
    room_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: RoomService = Depends(get_room_service),
) -> RoomSnapshot:
    try:
        return await service.snapshot(room_id, current_user.user_id)
    except RoomNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except RoomAccessError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@router.post("/rooms/{room_id}/actions", response_model=None)
async def room_action(
    room_id: UUID,
    payload: ActionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: RoomService = Depends(get_room_service),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> dict[str, object]:
    if x_request_id is not None:
        try:
            request_id = parse_idempotency_key(x_request_id)
        except InvalidIdempotencyKey as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
            ) from error
        if request_id != payload.action_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="request ID must equal action_id"
            )
    try:
        event = await service.apply_action(room_id, current_user.user_id, payload)
    except RoomNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except RoomAccessError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except StateVersionConflictError as error:
        snapshot = await service.snapshot(room_id, current_user.user_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(error), "snapshot": snapshot.model_dump(mode="json")},
        ) from error
    except RoomServiceError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return {"event": event.model_dump(mode="json")}


@router.websocket("/rooms/{room_id}/events")
async def room_events(websocket: WebSocket, room_id: UUID) -> None:
    await websocket.accept()
    app_settings = websocket.app.state.settings
    session = websocket.app.state.session_factory()
    service = RoomService(
        session=session,
        event_bus=get_event_bus(websocket),
        wallet_service=WalletService(session=session),
        bot_token=app_settings.bot_token,
        max_auth_age_seconds=app_settings.telegram_init_data_max_age_seconds,
    )
    try:
        # The socket is accepted before auth, so an idle client must not hold it
        # (and its DB session) open indefinitely.
        async with asyncio.timeout(WEBSOCKET_AUTH_TIMEOUT_SECONDS):
            raw_auth = await websocket.receive_json()
        first_message = WebSocketAuthMessage.model_validate(raw_auth)
        current_user = await service.authenticate_websocket(first_message)
        async with service.event_bus.subscribe(room_id) as events:
            snapshot = await service.snapshot(room_id, current_user.user_id)
            await websocket.send_json(
                {"type": "snapshot", "snapshot": snapshot.model_dump(mode="json")}
            )
            while True:
                event = await events.get()
                event = await service.personalize_event(event, current_user.user_id)
                await websocket.send_json({"type": "event", "event": event.model_dump(mode="json")})
    except TimeoutError:
        await websocket.close(code=4401, reason="authentication timeout")
    except (RoomNotFoundError, RoomAccessError, RoomServiceError, ValueError) as error:
        await websocket.close(code=4401, reason=str(error))
    except WebSocketDisconnect:
        pass
    finally:
        await service.session.close()
