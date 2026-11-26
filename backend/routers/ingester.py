"""
Ingester router aggregator for LedgerBridge statements and financial transactions.

Modular routers:
- statements.py: File parsing (PDF/Excel), sample loading, statement queries, deletion.
- rules.py: Word-regex rule management (list, create, delete).
- transactions.py: Review queue updates, human overrides, dynamic rule creation.
- categories.py: Standard and custom accounting category management.
"""

from .statements import (
    router,
    upload_statement,
    list_statements,
    get_statement,
    delete_statement,
    load_sample_statement,
    process_statement_bytes,
)
from .rules import list_rules, create_rule, delete_rule
from .transactions import update_transaction
from .categories import list_categories, create_category, delete_category

# Alias for backwards compatibility
_process_statement_bytes = process_statement_bytes

__all__ = [
    "router",
    "upload_statement",
    "list_statements",
    "get_statement",
    "delete_statement",
    "load_sample_statement",
    "process_statement_bytes",
    "_process_statement_bytes",
    "list_rules",
    "create_rule",
    "delete_rule",
    "update_transaction",
    "list_categories",
    "create_category",
    "delete_category",
]
