"""
Unit tests for asynchronous workflow resolver.
"""
import pytest


def test_onboard_trial_async_resolver_exists() -> None:
    """Test that resolver module is properly set up with workflow-specific subscription."""
    from app.usecases.workflows.onboard_trial_async import resolver

    # Verify the resolver functions exist
    assert hasattr(resolver, "start_onboard_trial_async")
    assert hasattr(resolver, "publish_onboard_trial_progress")
    assert hasattr(resolver, "onboard_trial_async_progress")

    # Verify imports work
    assert hasattr(resolver, "workflow_pubsub")
    assert hasattr(resolver, "OnboardTrialAsyncInput")
    assert hasattr(resolver, "OnboardTrialAsyncResponse")
    assert hasattr(resolver, "OnboardTrialProgressUpdate")
    assert hasattr(resolver, "OnboardTrialStatus")


# Note: Full integration tests require Restate runtime
# These are covered in E2E tests
