"""Agent management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db_session
from app.api.v1.schemas.agents import (
    AgentCreate, AgentResponse, AgentDelegateRequest, AgentReputationUpdate,
)
from app.application.commands.register_agent import RegisterAgentCommand
from app.application.handlers.command_handlers import CommandHandlers
from app.infrastructure.db.repositories.event_store import PostgresEventStore

router = APIRouter()


def _get_command_handlers(db: AsyncSession) -> CommandHandlers:
    event_store = PostgresEventStore(db)
    return CommandHandlers(event_store)


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def register_agent(
    body: AgentCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """Register a new agent."""
    handlers = _get_command_handlers(db)
    command = RegisterAgentCommand(
        agent_id=body.agent_id,
        owner_address=body.owner_address,
        delegation_address=body.delegation_address,
    )
    try:
        await handlers.handle_register_agent(command)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return AgentResponse(
        agent_id=body.agent_id,
        owner_address=body.owner_address,
        delegation_address=body.delegation_address,
    )


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Get agent details by ID."""
    event_store = PostgresEventStore(db)
    events = await event_store.load_stream(agent_id)
    if not events:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    from app.domain.aggregates.agent import AgentAggregate
    agent = AgentAggregate(agent_id)
    for event in events:
        agent._apply(event)

    return AgentResponse(
        agent_id=agent.agent_id,
        owner_address=agent.owner_address or "",
        delegation_address=agent.delegation_address,
        delegation_active=agent.delegation_active,
        reputation_score=agent.reputation_score,
        version=agent.version,
    )


@router.post("/{agent_id}/delegate", response_model=AgentResponse)
async def delegate_agent(
    agent_id: str,
    body: AgentDelegateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Delegate agent capabilities to another address (EIP-7702)."""
    handlers = _get_command_handlers(db)
    from app.application.commands.register_agent import DelegateAgentCommand
    command = DelegateAgentCommand(
        agent_id=agent_id,
        delegate_address=body.delegate_address,
        expires_at=body.expires_at,
    )
    try:
        await handlers.handle_delegate_agent(command)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return await get_agent(agent_id, db)


@router.post("/{agent_id}/revoke-delegation", response_model=AgentResponse)
async def revoke_delegation(
    agent_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Revoke agent delegation."""
    handlers = _get_command_handlers(db)
    from app.application.commands.register_agent import RevokeDelegationCommand
    command = RevokeDelegationCommand(agent_id=agent_id)
    try:
        await handlers.handle_revoke_delegation(command)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return await get_agent(agent_id, db)


@router.post("/{agent_id}/reputation", response_model=AgentResponse)
async def update_reputation(
    agent_id: str,
    body: AgentReputationUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Update agent reputation score."""
    handlers = _get_command_handlers(db)
    from app.application.commands.register_agent import UpdateReputationCommand
    command = UpdateReputationCommand(
        agent_id=agent_id,
        new_score=body.new_score,
        reason=body.reason,
    )
    try:
        await handlers.handle_update_reputation(command)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return await get_agent(agent_id, db)
