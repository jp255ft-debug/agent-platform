# Agent Domain Model

## Properties
- agent_id: UUID
- owner_address: Address (EVM)
- delegation_status: Enum (Active, Revoked, Expired)
- reputation_score: uint256
- created_at: Timestamp

## Behaviors
- register()
- delegate()
- consume()
- settle()
