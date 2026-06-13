# Billing Session Domain Model

## Properties
- session_id: UUID
- agent_id: UUID
- resource_type: Enum (LLM, Compute, Storage)
- tokens_consumed: uint256
- start_time: Timestamp
- end_time: Timestamp
- status: Enum (Active, Pending, Settled)

## Behaviors
- start()
- record_consumption()
- close()
- settle()
