"""
Unit tests for create_trial GraphQL resolver.
"""


def test_create_trial_resolver_exists() -> None:
    """Test that resolver module is properly set up."""
    from app.usecases.commands.trial_management.create_trial import resolver

    # Verify the resolver function exists and is a Strawberry field
    assert hasattr(resolver, "create_trial")

    # Verify imports work
    assert hasattr(resolver, "session_scope")
    assert hasattr(resolver, "create_trial_handler")
    assert hasattr(resolver, "CreateTrialInput")
    assert hasattr(resolver, "CreateTrialResponse")


# Note: The actual business logic is thoroughly tested in test_handler.py
# This test just verifies the GraphQL resolver module is properly wired up.
