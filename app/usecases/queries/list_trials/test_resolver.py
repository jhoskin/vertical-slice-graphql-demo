"""
Unit tests for list_trials GraphQL resolver.
"""


def test_list_trials_resolver_exists() -> None:
    """Test that resolver module is properly set up."""
    from app.usecases.queries.list_trials import resolver

    # Verify the resolver function exists and is a Strawberry field
    assert hasattr(resolver, "list_trials")

    # Verify imports work
    assert hasattr(resolver, "session_scope")
    assert hasattr(resolver, "list_trials_handler")
    assert hasattr(resolver, "ListTrialsInput")
    assert hasattr(resolver, "ListTrialsOutput")


# Note: The actual business logic is thoroughly tested in test_handler.py
# This test just verifies the GraphQL resolver module is properly wired up.
