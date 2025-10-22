"""
GraphQL resolver for list_trials query.
"""
import strawberry

from app.infrastructure.database.session import session_scope
from app.usecases.queries.list_trials.handler import list_trials_handler
from app.usecases.queries.list_trials.types import (
    ListTrialsInput,
    ListTrialsOutput,
)


@strawberry.field
def list_trials(input: ListTrialsInput = ListTrialsInput()) -> ListTrialsOutput:
    """
    GraphQL query to list trials with filtering and pagination.

    Args:
        input: Filters and pagination parameters

    Returns:
        Paginated list of trial summaries
    """
    with session_scope() as session:
        return list_trials_handler(session, input)
