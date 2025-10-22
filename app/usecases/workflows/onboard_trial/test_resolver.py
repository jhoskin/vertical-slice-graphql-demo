"""
Unit tests for onboard_trial GraphQL resolvers.
"""


def test_start_onboarding_resolver_exists() -> None:
    """Test that resolver module is properly set up."""
    from app.usecases.workflows.onboard_trial import resolver

    # Verify the resolver functions exist
    assert hasattr(resolver, "start_onboarding")
    assert hasattr(resolver, "onboarding_status")

    # Verify imports work
    assert hasattr(resolver, "session_scope")
    assert hasattr(resolver, "onboard_trial_handler")
    assert hasattr(resolver, "get_onboarding_status_handler")
    assert hasattr(resolver, "OnboardTrialInput")
    assert hasattr(resolver, "OnboardTrialResponse")
    assert hasattr(resolver, "OnboardingStatusResponse")


# Note: The actual business logic is thoroughly tested in test_handler.py
# This test just verifies the GraphQL resolver module is properly wired up.
