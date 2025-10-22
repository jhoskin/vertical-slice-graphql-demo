"""
GraphQL schema composition.

This module imports all resolvers from use case slices and composes them
into a single Strawberry schema.
"""
import strawberry

# Import command resolvers (mutations)
from app.usecases.commands.register_site_to_trial.resolver import (
    register_site_to_trial,
)
from app.usecases.commands.trial_management.create_trial.resolver import create_trial
from app.usecases.commands.trial_management.update_trial_metadata.resolver import (
    update_trial_metadata,
)

# Import query resolvers
from app.usecases.queries.get_audit_log.resolver import audit_log
from app.usecases.queries.get_trial.resolver import trial
from app.usecases.queries.list_trials.resolver import trials

# Import workflow resolvers
from app.usecases.workflows.onboard_trial.resolver import (
    onboarding_status,
    start_onboarding,
)


@strawberry.type
class Mutation:
    """Root mutation type - one resolver per command/workflow."""

    create_trial = create_trial
    register_site_to_trial = register_site_to_trial
    update_trial_metadata = update_trial_metadata
    start_onboarding = start_onboarding


@strawberry.type
class Query:
    """Root query type - one resolver per query."""

    trial = trial
    trials = trials
    audit_log = audit_log
    onboarding_status = onboarding_status

    @strawberry.field
    def health(self) -> str:
        """Health check endpoint."""
        return "ok"


# Build the schema
schema = strawberry.Schema(query=Query, mutation=Mutation)
