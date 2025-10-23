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
from app.usecases.workflows.onboard_trial_async.resolver import (
    start_onboard_trial_async,
    workflow_progress,
)
from app.usecases.workflows.onboard_trial_sync.resolver import onboard_trial_sync


@strawberry.type
class Mutation:
    """Root mutation type - one resolver per command."""

    create_trial = create_trial
    register_site_to_trial = register_site_to_trial
    update_trial_metadata = update_trial_metadata

    # Workflow mutations
    onboard_trial_sync = onboard_trial_sync
    start_onboard_trial_async = start_onboard_trial_async


@strawberry.type
class Query:
    """Root query type - one resolver per query."""

    trial = trial
    trials = trials
    audit_log = audit_log

    @strawberry.field
    def health(self) -> str:
        """Health check endpoint."""
        return "ok"


@strawberry.type
class Subscription:
    """Root subscription type - real-time updates."""

    workflow_progress = workflow_progress


# Build the schema
schema = strawberry.Schema(query=Query, mutation=Mutation, subscription=Subscription)
