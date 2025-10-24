"""
Type definitions for get_audit_log query.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import strawberry


@strawberry.input
class GetAuditLogInput:
    """Input for retrieving audit logs."""
    entity: str  # Entity type (e.g., "trial", "site")
    entity_id: str  # Entity ID
    limit: int = 50


@strawberry.type
@dataclass
class AuditEntry:
    """Audit log entry."""
    id: str
    user: str
    action: str
    entity: str
    entity_id: str
    payload_json: Optional[str]
    created_at: datetime
    updated_at: datetime


@strawberry.type
@dataclass
class AuditLogResponse:
    """List of audit log entries."""
    entries: list[AuditEntry]
