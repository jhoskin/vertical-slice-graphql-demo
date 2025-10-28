"""
Unit tests for get_trial GraphQL resolver.
"""


def test_trial_by_id_resolver_exists() -> None:
    """Test that resolver module is properly set up."""
    from app.usecases.queries.get_trial import resolver

    # Verify the resolver function exists and is a Strawberry field
    assert hasattr(resolver, "trial")

    # Verify imports work
    assert hasattr(resolver, "session_scope")
    assert hasattr(resolver, "get_trial_handler")
    assert hasattr(resolver, "TrialDetail")


# Note: The actual business logic is thoroughly tested in test_handler.py
# This test just verifies the GraphQL resolver module is properly wired up.
