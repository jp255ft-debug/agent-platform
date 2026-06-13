"""Resource consumption endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db_session, get_redis
from app.api.v1.schemas.consume import ConsumeRequest, ConsumeResponse, BillingSessionResponse
from app.application.commands.consume_resource import ConsumeResourceCommand
from app.application.handlers.command_handlers import CommandHandlers
from app.application.services.idempotency import IdempotencyService
from app.application.services.rate_limiter import RateLimiter
from app.infrastructure.db.repositories.event_store import PostgresEventStore

router = APIRouter()


@router.post("", response_model=ConsumeResponse, status_code=status.HTTP_200_OK)
async def consume_resource(
    body: ConsumeRequest,
    db: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
):
    """Consume a resource with x402 payment verification."""
    idempotency = IdempotencyService(redis)
    rate_limiter = RateLimiter(redis)

    # Check idempotency
    if body.idempotency_key:
        if await idempotency.is_processed(body.idempotency_key):
            result = await idempotency.get_result(body.idempotency_key)
            if result:
                return ConsumeResponse(**eval(result))  # nosec
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request already processed")

    # Check rate limit
    allowed = await rate_limiter.check_rate_limit(body.agent_id, body.resource_type)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )

    remaining = await rate_limiter.get_remaining_tokens(body.agent_id, body.resource_type)

    # Process consumption
    handlers = _get_command_handlers(db)
    command = ConsumeResourceCommand(
        agent_id=body.agent_id,
        resource_type=body.resource_type,
        amount=body.amount,
        x402_payment=body.x402_payment,
        idempotency_key=body.idempotency_key,
    )
    try:
        session_id = await handlers.handle_consume_resource(command)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(e))

    response = ConsumeResponse(
        session_id=session_id,
        total_consumed=body.amount,
        remaining_tokens=remaining,
        status="consumed",
    )

    # Store idempotency result
    if body.idempotency_key:
        await idempotency.mark_processed(body.idempotency_key)

    return response


@router.get("/sessions/{session_id}", response_model=BillingSessionResponse)
async def get_billing_session(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Get billing session details."""
    event_store = PostgresEventStore(db)
    events = await event_store.load_stream(session_id)
    if not events:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    from app.domain.aggregates.billing_session import BillingSessionAggregate
    session = BillingSessionAggregate(session_id)
    for event in events:
        session._apply(event)

    return BillingSessionResponse(
        session_id=session.session_id,
        agent_id=session.agent_id or "",
        resource_type=session.resource_type or "",
        total_consumed=session.total_consumed,
        status=session.status,
        version=session.version,
    )


def _get_command_handlers(db: AsyncSession) -> CommandHandlers:
    event_store = PostgresEventStore(db)
    return CommandHandlers(event_store)
