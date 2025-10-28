"""
Handler for get_audit_log query.
"""
from sqlalchemy.orm import Session

from app.infrastructure.database.models import AuditLog
from app.usecases.queries.get_audit_log.types import (
    AuditEntry,
    GetAuditLogInput,
    AuditLogResponse,
)


def get_audit_log_handler(
    session: Session, input_data: GetAuditLogInput
) -> AuditLogResponse:
    """
    Get audit log entries for a specific entity.

    Args:
        session: Database session
        input_data: Entity type and ID to retrieve audit logs for

    Returns:
        List of audit log entries, ordered by created_at descending
    """
    # Query audit logs for entity
    logs = (
        session.query(AuditLog)
        .filter(
            AuditLog.entity == input_data.entity,
            AuditLog.entity_id == input_data.entity_id,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(input_data.limit)
        .all()
    )

    # Convert to output format
    entries = [
        AuditEntry(
            id=log.id,
            user=log.user,
            action=log.action,
            entity=log.entity,
            entity_id=log.entity_id,
            payload_json=log.payload_json,
            created_at=log.created_at,
            updated_at=log.updated_at,
        )
        for log in logs
    ]

    return AuditLogResponse(entries=entries)
