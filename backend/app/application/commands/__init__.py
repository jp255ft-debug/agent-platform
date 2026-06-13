"""Command definitions."""
from app.application.commands.register_agent import (
    RegisterAgentCommand, DelegateAgentCommand, RevokeDelegationCommand, UpdateReputationCommand,
)
from app.application.commands.consume_resource import ConsumeResourceCommand
from app.application.commands.settle_invoice import SettleInvoiceCommand

__all__ = [
    "RegisterAgentCommand", "DelegateAgentCommand", "RevokeDelegationCommand",
    "UpdateReputationCommand", "ConsumeResourceCommand", "SettleInvoiceCommand",
]
