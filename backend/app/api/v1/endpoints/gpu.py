"""GPU leasing REST endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.schemas.gpu import (
    ExtendLeaseRequest,
    ExtendLeaseResponse,
    GPUHardwareResponse,
    GPULeaseRequest,
    GPULeaseResponse,
)
from app.application.commands.lease_gpu import (
    ExtendLeaseCommand,
    LeaseGPUCommand,
    TerminateLeaseCommand,
)
from app.application.handlers.gpu_handlers import GPUHandlers
from app.core.auth import validate_api_key
from app.core.dependencies import get_gpu_handlers

router = APIRouter(prefix="/api/v1/gpu", tags=["GPU Leasing"])


@router.get("/hardware", response_model=list[GPUHardwareResponse])
async def list_gpu_hardware(
    search: Optional[str] = None,
    min_vram: Optional[int] = None,
    max_price: Optional[float] = None,
    handlers: GPUHandlers = Depends(get_gpu_handlers),
    agent_id: Optional[str] = Depends(validate_api_key),
):
    """
    List available GPU hardware for leasing on io.net.

    Requires a valid API Key via X-API-Key header.

    Supports optional filters:
    - search: text search across GPU models
    - min_vram: minimum VRAM per card in GB
    - max_price: maximum price per hour in USDC
    """
    return await handlers.list_available_gpus(search=search, min_vram=min_vram, max_price=max_price)


@router.post("/lease", response_model=GPULeaseResponse, status_code=status.HTTP_202_ACCEPTED)
async def request_gpu_lease(
    request: GPULeaseRequest,
    handlers: GPUHandlers = Depends(get_gpu_handlers),
    agent_id: Optional[str] = Depends(validate_api_key),
):
    """
    Request a GPU lease.

    The request is sent to io.net and the lease is provisioned
    asynchronously. Status can be queried via GET /leases/{lease_id}.
    """
    command = LeaseGPUCommand(
        agent_id=agent_id,
        hardware_id=request.hardware_id,
        duration_hours=request.duration_hours,
        gpu_count=request.gpu_count or 1,
        max_budget_usdc=request.max_budget_usdc,
    )
    try:
        result = await handlers.request_lease(command)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/leases/{lease_id}", response_model=GPULeaseResponse)
async def get_lease_status(
    lease_id: str,
    handlers: GPUHandlers = Depends(get_gpu_handlers),
    agent_id: Optional[str] = Depends(validate_api_key),
):
    """Get the status of a GPU lease."""
    try:
        return await handlers.get_lease(lease_id, agent_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if "not found" in str(e) else status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.post("/leases/{lease_id}/extend", response_model=ExtendLeaseResponse)
async def extend_lease(
    lease_id: str,
    request: ExtendLeaseRequest,
    handlers: GPUHandlers = Depends(get_gpu_handlers),
    agent_id: Optional[str] = Depends(validate_api_key),
):
    """Extend the duration of an active GPU lease."""
    command = ExtendLeaseCommand(
        lease_id=lease_id,
        additional_hours=request.additional_hours,
        agent_id=agent_id,
    )
    try:
        return await handlers.extend_lease(command)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if "not found" in str(e) else status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/leases/{lease_id}", status_code=status.HTTP_204_NO_CONTENT)
async def terminate_lease(
    lease_id: str,
    handlers: GPUHandlers = Depends(get_gpu_handlers),
    agent_id: Optional[str] = Depends(validate_api_key),
):
    """Terminate a GPU lease early (kill-switch)."""
    command = TerminateLeaseCommand(lease_id=lease_id, agent_id=agent_id)
    try:
        await handlers.terminate_lease(command)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if "not found" in str(e) else status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
