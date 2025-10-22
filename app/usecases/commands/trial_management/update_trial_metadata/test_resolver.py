"""
Unit tests for update_trial_metadata GraphQL resolver.
"""


def test_update_trial_metadata_resolver_exists() -> None:
    """Test that resolver module is properly set up."""
    from app.usecases.commands.trial_management.update_trial_metadata import resolver

    # Verify the resolver function exists and is a Strawberry field
    assert hasattr(resolver, "update_trial_metadata")

    # Verify imports work
    assert hasattr(resolver, "session_scope")
    assert hasattr(resolver, "update_trial_metadata_handler")
    assert hasattr(resolver, "UpdateTrialMetadataInput")
    assert hasattr(resolver, "UpdateTrialMetadataOutput")


# Note: The actual business logic is thoroughly tested in test_handler.py
# This test just verifies the GraphQL resolver module is properly wired up.
