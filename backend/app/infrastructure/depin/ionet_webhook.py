"""
Webhook handler for io.net deployment events.

Receives asynchronous notifications from io.net about deployment state changes:
- deployment_ready: GPU cluster is provisioned and ready
- deployment_terminated: Cluster was terminated (kill-switch or manual)
- deployment_expired: Cluster duration expired
- deployment_error: Provisioning failed

This eliminates the need for polling and keeps the GPULeaseAggregate in sync.
"""
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.core.config import settings
from app.core.dependencies import get_event_store
from app.domain.aggregates.gpu_lease import GPULeaseAggregate
from app.domain.repositories.event_store import EventStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/gpu/webhook", tags=["GPU Webhook"])

# io.net webhook secret for signature verification
# In production, this should be a shared secret configured in io.net dashboard
WEBHOOK_SECRET = settings.IO_NET_WEBHOOK_SECRET or ""


async def verify_webhook_signature(
    request: Request,
    x_webhook_signature: str | None = Header(None),
) -> None:
    """Verify the webhook signature from io.net.

    In production, implement HMAC-SHA256 verification using WEBHOOK_SECRET.
    For now, we accept requests without signature for development.
    """
    if not WEBHOOK_SECRET:
        logger.warning("IO_NET_WEBHOOK_SECRET not configured, skipping signature verification")
        return

    if not x_webhook_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Webhook-Signature header",
        )

    body = await request.body()
    # TODO: Implement HMAC-SHA256 verification
    # expected_sig = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    # if not hmac.compare_digest(expected_sig, x_webhook_signature):
    #     raise HTTPException(status_code=401, detail="Invalid signature")


@router.post("/deployment", status_code=status.HTTP_200_OK)
async def handle_deployment_event(
    request: Request,
    event_store: EventStore = Depends(get_event_store),
    _=Depends(verify_webhook_signature),
):
    """
    Handle deployment lifecycle events from io.net.

    Expected payload:
    ```json
    {
        "event": "deployment_ready | deployment_terminated | deployment_expired | deployment_error",
        "deployment_id": "dep-123",
        "lease_id": "lease-456",
        "timestamp": "2026-06-21T12:00:00Z",
        "message": "Optional human-readable message"
    }
    ```
    """
    payload = await request.json()
    event_type = payload.get("event")
    deployment_id = payload.get("deployment_id")
    lease_id = payload.get("lease_id")
    message = payload.get("message", "")

    logger.info(
        "Received io.net webhook event: %s for deployment %s (lease: %s)",
        event_type, deployment_id, lease_id,
    )

    if not event_type or not deployment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required fields: event, deployment_id",
        )

    if not lease_id:
        logger.warning("No lease_id in webhook payload, attempting to find by deployment_id")
        # TODO: Implement lookup by deployment_id if needed
        return {"status": "accepted", "note": "lease_id required for state update"}

    # Load the lease aggregate from event store
    events = await event_store.load_stream(lease_id)
    if not events:
        logger.error("Lease %s not found for deployment event", lease_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lease {lease_id} not found",
        )

    lease = GPULeaseAggregate.rebuild(lease_id, events)

    # Apply the event based on type
    if event_type == "deployment_ready":
        if lease.deployment_id == deployment_id:
            lease.activate()
            logger.info("Lease %s activated (deployment %s ready)", lease_id, deployment_id)
        else:
            logger.warning(
                "Deployment ID mismatch: lease has %s, event has %s",
                lease.deployment_id, deployment_id,
            )
            return {"status": "ignored", "reason": "deployment_id mismatch"}

    elif event_type == "deployment_terminated":
        lease.terminate(reason=message or "io.net_terminated")
        logger.info("Lease %s terminated (deployment %s)", lease_id, deployment_id)

    elif event_type == "deployment_expired":
        lease.expire()
        logger.info("Lease %s expired (deployment %s)", lease_id, deployment_id)

    elif event_type == "deployment_error":
        lease.terminate(reason=f"provisioning_error: {message}")
        logger.error("Lease %s failed (deployment %s): %s", lease_id, deployment_id, message)

    else:
        logger.warning("Unknown webhook event type: %s", event_type)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown event type: {event_type}",
        )

    # Persist the changes
    changes = lease.get_changes()
    if changes:
        await event_store.append_events(lease_id, changes, expected_version=lease.version - 1)
        lease.clear_changes()

    return {
        "status": "processed",
        "lease_id": lease_id,
        "new_status": lease.status.value,
    }
