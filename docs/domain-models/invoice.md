# Invoice Domain Model

## Properties
- invoice_id: UUID
- agent_id: UUID
- session_ids: List[UUID]
- total_amount: uint256
- status: Enum (Pending, Paid, Overdue, Disputed)
- due_date: Timestamp

## Behaviors
- generate()
- pay()
- dispute()
- settle()
