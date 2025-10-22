"""
GraphQL resolver for get_trial query.
"""
import strawberry

from app.infrastructure.database.session import session_scope
from app.usecases.queries.get_trial.handler import get_trial_handler
from app.usecases.queries.get_trial.types import TrialDetail


@strawberry.field
def trial_by_id(id: int) -> TrialDetail:
    """
    GraphQL query to get trial by ID.

    Args:
        id: Trial ID

    Returns:
        Detailed trial information
    """
    with session_scope() as session:
        return get_trial_handler(session, id)
