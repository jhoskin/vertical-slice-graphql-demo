"""
Unit tests for synchronous onboard trial saga resolver.
"""


def test_onboard_trial_sync_resolver_exists() -> None:
    """Test that resolver module is properly set up."""
    from app.usecases.workflows.onboard_trial_sync import resolver

    # Verify the resolver function exists
    assert hasattr(resolver, "onboard_trial_sync")

    # Verify imports work
    assert hasattr(resolver, "session_scope")
    assert hasattr(resolver, "onboard_trial_sync_handler")
    assert hasattr(resolver, "OnboardTrialSyncInput")
    assert hasattr(resolver, "OnboardTrialSyncResponse")


# Note: The actual business logic is tested in test_handler.py
# This test just verifies the GraphQL resolver module is properly wired up.
