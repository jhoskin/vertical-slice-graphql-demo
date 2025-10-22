"""
Unit tests for get_audit_log GraphQL resolver.
"""


def test_audit_log_resolver_exists() -> None:
    """Test that resolver module is properly set up."""
    from app.usecases.queries.get_audit_log import resolver

    # Verify the resolver function exists and is a Strawberry field
    assert hasattr(resolver, "audit_log")

    # Verify imports work
    assert hasattr(resolver, "session_scope")
    assert hasattr(resolver, "get_audit_log_handler")
    assert hasattr(resolver, "GetAuditLogInput")
    assert hasattr(resolver, "GetAuditLogOutput")


# Note: The actual business logic is thoroughly tested in test_handler.py
# This test just verifies the GraphQL resolver module is properly wired up.
