"""
Handler for list_trials query.
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.infrastructure.database.models import Trial, TrialSite
from app.usecases.queries.list_trials.types import (
    ListTrialsInput,
    ListTrialsOutput,
    TrialSummary,
)


def list_trials_handler(session: Session, input_data: ListTrialsInput) -> ListTrialsOutput:
    """
    List trials with filtering and pagination.

    Args:
        session: Database session
        input_data: Filters and pagination parameters

    Returns:
        Paginated list of trial summaries with total count
    """
    # Build base query
    query = session.query(Trial)

    # Apply filters
    if input_data.phase:
        query = query.filter(Trial.phase == input_data.phase)

    if input_data.status:
        query = query.filter(Trial.status == input_data.status)

    if input_data.search:
        # Case-insensitive search in trial name
        search_pattern = f"%{input_data.search}%"
        query = query.filter(Trial.name.ilike(search_pattern))

    # Get total count before pagination
    total = query.count()

    # Apply pagination
    query = query.order_by(Trial.created_at.desc())
    query = query.limit(input_data.limit).offset(input_data.offset)

    # Execute query
    trials = query.all()

    # Build summaries with site counts
    summaries = []
    for trial in trials:
        # Count sites for this trial
        site_count = (
            session.query(func.count(TrialSite.site_id))
            .filter(TrialSite.trial_id == trial.id)
            .scalar()
        ) or 0

        summaries.append(
            TrialSummary(
                id=trial.id,
                name=trial.name,
                phase=trial.phase,
                status=trial.status,
                created_at=trial.created_at,
                site_count=site_count,
            )
        )

    return ListTrialsOutput(items=summaries, total=total)
