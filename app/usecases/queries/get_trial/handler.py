"""
Handler for get_trial query.
"""
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.infrastructure.database.models import ProtocolVersion, Trial, TrialSite, Site
from app.usecases.queries.get_trial.types import (
    ProtocolInfo,
    SiteInfo,
    TrialDetail,
)


class TrialNotFoundError(Exception):
    """Raised when trial is not found."""
    pass


def get_trial_handler(session: Session, trial_id: int) -> TrialDetail:
    """
    Get detailed trial information.

    Uses eager loading (joinedload) for optimal query performance,
    loading trial, sites, and latest protocol in a single query.

    Args:
        session: Database session
        trial_id: ID of trial to retrieve

    Returns:
        Detailed trial information

    Raises:
        TrialNotFoundError: If trial doesn't exist
    """
    # Eager load trial with sites and trial_sites for link status
    trial = (
        session.query(Trial)
        .options(
            joinedload(Trial.trial_sites).joinedload(TrialSite.site),
        )
        .filter_by(id=trial_id)
        .first()
    )

    if not trial:
        raise TrialNotFoundError(f"Trial with id {trial_id} not found")

    # Get latest protocol version
    latest_protocol = (
        session.query(ProtocolVersion)
        .filter_by(trial_id=trial_id)
        .order_by(ProtocolVersion.created_at.desc())
        .first()
    )

    # Build site info from trial_sites relationships
    sites = [
        SiteInfo(
            id=ts.site.id,
            name=ts.site.name,
            country=ts.site.country,
            link_status=ts.status,
        )
        for ts in trial.trial_sites
    ]

    # Build protocol info if exists
    protocol_info: Optional[ProtocolInfo] = None
    if latest_protocol:
        protocol_info = ProtocolInfo(
            id=latest_protocol.id,
            version=latest_protocol.version,
            notes=latest_protocol.notes,
            created_at=latest_protocol.created_at,
        )

    return TrialDetail(
        id=trial.id,
        name=trial.name,
        phase=trial.phase,
        status=trial.status,
        created_at=trial.created_at,
        sites=sites,
        latest_protocol=protocol_info,
    )
