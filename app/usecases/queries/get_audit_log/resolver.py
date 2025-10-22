"""
GraphQL resolver for get_audit_log query.
"""
import strawberry

from app.infrastructure.database.session import session_scope
from app.usecases.queries.get_audit_log.handler import get_audit_log_handler
from app.usecases.queries.get_audit_log.types import (
    GetAuditLogInput,
    AuditLogResponse,
)


@strawberry.field
def audit_log(input: GetAuditLogInput) -> AuditLogResponse:
    """
    GraphQL query to get audit log entries for an entity.

    Args:
        input: Entity type and ID

    Returns:
        List of audit log entries
    """
    with session_scope() as session:
        return get_audit_log_handler(session, input)
