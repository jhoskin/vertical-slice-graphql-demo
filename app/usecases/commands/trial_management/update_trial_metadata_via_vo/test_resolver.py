"""
Tests for update_trial_metadata_via_vo resolver.

Verifies that the resolver exists and is properly configured.
"""
from app.usecases.commands.trial_management.update_trial_metadata_via_vo.resolver import (
    update_trial_metadata_via_vo,
)


def test_update_trial_metadata_via_vo_resolver_exists():
    """Test that the resolver function exists and is properly configured."""
    assert update_trial_metadata_via_vo is not None

    # Strawberry decorators wrap functions in StrawberryField objects
    # Check for Strawberry-specific attributes instead of __name__
    assert hasattr(update_trial_metadata_via_vo, "graphql_name") or hasattr(update_trial_metadata_via_vo, "python_name")
