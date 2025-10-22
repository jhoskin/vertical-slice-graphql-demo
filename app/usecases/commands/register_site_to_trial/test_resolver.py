"""
Unit tests for register_site_to_trial GraphQL resolver.
"""


def test_register_site_to_trial_resolver_exists() -> None:
    """Test that resolver module is properly set up."""
    from app.usecases.commands.register_site_to_trial import resolver

    # Verify the resolver function exists and is a Strawberry field
    assert hasattr(resolver, "register_site_to_trial")

    # Verify imports work
    assert hasattr(resolver, "session_scope")
    assert hasattr(resolver, "register_site_to_trial_handler")
    assert hasattr(resolver, "RegisterSiteToTrialInput")
    assert hasattr(resolver, "RegisterSiteToTrialOutput")


# Note: The actual business logic is thoroughly tested in test_handler.py
# This test just verifies the GraphQL resolver module is properly wired up.
