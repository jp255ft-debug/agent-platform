"""Agent management endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.agents import (
    AgentCreate,
    AgentDelegateRequest,
    AgentReputationUpdate,
    AgentResponse,
)
from app.application.commands.register_agent import RegisterAgentCommand
from app.application.handlers.command_handlers import CommandHandlers
from app.core.dependencies import get_db_session
from app.core.exceptions import (
    AgentAlreadyExistsError,
    AgentNotFoundError,
    DomainError,
)
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
    except AgentAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.to_dict())
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.to_dict())

    return AgentResponse(
        agent_id=body.agent_id,
        owner_address=body.owner_address,
        delegation_address=body.delegation_address,
    )


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    owner_address: Optional[str] = Query(None, description="Filter by owner Ethereum address"),
    db: AsyncSession = Depends(get_db_session),
):
    """List agents, optionally filtered by owner_address."""
    event_store = PostgresEventStore(db)

    if owner_address:
        # Busca no banco por owner_address nos eventos AgentRegistered
        owner_lower = owner_address.lower()
        query = text("""
            SELECT DISTINCT aggregate_id
            FROM events
            WHERE event_type = 'AgentRegistered'
              AND LOWER(data->>'owner_address') = :owner_address
            ORDER BY aggregate_id
        """)
        result = await db.execute(query, {"owner_address": owner_lower})
        rows = result.fetchall()

        agents = []
        for (agg_id,) in rows:
            events = await event_store.load_stream(agg_id)
            if events:
                from app.domain.aggregates.agent import AgentAggregate
                agent = AgentAggregate(agg_id)
                for event in events:
                    agent._apply(event)
                agents.append(AgentResponse(
                    agent_id=agent.agent_id,
                    owner_address=agent.owner_address or "",
                    delegation_address=agent.delegation_address,
                    delegation_active=agent.delegation_active,
                    reputation_score=agent.reputation_score,
                    version=agent.version,
                ))
        return agents

    # Sem filtro: retorna todos os agentes (limitado)
    query = text("""
        SELECT DISTINCT aggregate_id
        FROM events
        WHERE event_type = 'AgentRegistered'
        ORDER BY aggregate_id
        LIMIT 100
    """)
    result = await db.execute(query)
    rows = result.fetchall()

    agents = []
    for (agg_id,) in rows:
        events = await event_store.load_stream(agg_id)
        if events:
            from app.domain.aggregates.agent import AgentAggregate
            agent = AgentAggregate(agg_id)
            for event in events:
                agent._apply(event)
            agents.append(AgentResponse(
                agent_id=agent.agent_id,
                owner_address=agent.owner_address or "",
                delegation_address=agent.delegation_address,
                delegation_active=agent.delegation_active,
                reputation_score=agent.reputation_score,
                version=agent.version,
            ))
    return agents


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
    except AgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.to_dict())
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.to_dict())

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
    except AgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.to_dict())
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.to_dict())

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
    except AgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.to_dict())
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.to_dict())

    return await get_agent(agent_id, db)
