"""Finogrid B2B Payout flow — simplified for demo.

Simulates the v1 payout pipeline: Batch intake → Routing → Compliance → Execution.
In production, this uses GCP Pub/Sub + Bridge API + Chainalysis.
"""

from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from demo.finogrid.models import Client, Batch, PayoutTask, _new_uuid, _utcnow
from demo.finogrid.corridors import route_payout, validate_beneficiary


async def create_batch(db: AsyncSession, client_id: str, reference: str,
                       tasks: list[dict]) -> dict:
    """Create and process a B2B payout batch."""
    client = await db.get(Client, client_id)
    if not client:
        raise ValueError(f"Client {client_id} not found")
    if client.status != "active":
        raise ValueError(f"Client is {client.status}")

    batch = Batch(
        id=_new_uuid(),
        client_id=client_id,
        reference=reference,
        status="processing",
        task_count=len(tasks),
    )
    db.add(batch)
    await db.flush()

    total_amount = 0.0
    created_tasks = []

    for i, task_data in enumerate(tasks):
        corridor_code = task_data.get("corridor_code", "").upper()
        amount = float(task_data.get("amount_usd", 0))
        total_amount += amount

        # Validate beneficiary
        beneficiary_data = task_data.get("beneficiary_data", {})

        # Route payout
        routing = route_payout(
            corridor_code=corridor_code,
            amount_usd=amount,
            preferred_asset=task_data.get("preferred_asset", "USDC"),
            preferred_mode=task_data.get("preferred_mode", "wallet"),
        )

        if "error" in routing:
            status = "failed"
            failure_reason = routing["error"]
            partner = None
        else:
            # Simulate compliance check (always passes in demo)
            status = "completed"
            failure_reason = None
            partner = routing["partner"]

        task = PayoutTask(
            id=_new_uuid(),
            batch_id=batch.id,
            corridor_code=corridor_code,
            recipient_name=task_data.get("recipient_name", "Unknown"),
            amount_usd=amount,
            preferred_asset=task_data.get("preferred_asset", "USDC"),
            preferred_mode=task_data.get("preferred_mode", "wallet"),
            status=status,
            partner_tx_id=f"bridge_{_new_uuid()[:8]}" if status == "completed" else None,
            failure_reason=failure_reason,
            beneficiary_data=beneficiary_data,
        )
        db.add(task)
        created_tasks.append({
            "task_id": task.id,
            "corridor_code": corridor_code,
            "recipient_name": task.recipient_name,
            "amount_usd": task.amount_usd,
            "status": task.status,
            "failure_reason": task.failure_reason,
        })

    # Update batch
    batch.total_amount_usd = total_amount
    batch.completed_count = sum(1 for t in created_tasks if t["status"] == "completed")
    batch.failed_count = sum(1 for t in created_tasks if t["status"] == "failed")
    if batch.failed_count == batch.task_count:
        batch.status = "failed"
    elif batch.completed_count == batch.task_count:
        batch.status = "completed"
    else:
        batch.status = "partially_completed"

    await db.commit()
    await db.refresh(batch)

    return {
        "batch_id": batch.id,
        "client_id": client_id,
        "reference": batch.reference,
        "status": batch.status,
        "total_amount_usd": batch.total_amount_usd,
        "task_count": batch.task_count,
        "completed_count": batch.completed_count,
        "failed_count": batch.failed_count,
        "tasks": created_tasks,
        "created_at": batch.created_at,
    }
