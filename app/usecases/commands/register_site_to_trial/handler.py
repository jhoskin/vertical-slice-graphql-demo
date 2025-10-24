"""
Handler for register_site_to_trial command.

Demonstrates atomic multi-table transaction: upsert site and link to trial.
"""
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.audit import audited
from app.infrastructure.database.models import Site, Trial, TrialSite
from app.usecases.commands.register_site_to_trial.types import (
    RegisterSiteToTrialInputModel,
    RegisterSiteToTrialResponse,
)


class TrialNotFoundError(Exception):
    """Raised when trial is not found."""
    pass


class DuplicateSiteLinkError(Exception):
    """Raised when site is already linked to trial."""
    pass


@audited(
    action="register_site_to_trial",
    entity="trial_site",
    entity_id_fn=lambda r: f"{r.trial_id}_{r.site_id}",
)
def register_site_to_trial_handler(
    session: Session, input_data: RegisterSiteToTrialInputModel
) -> RegisterSiteToTrialResponse:
    """
    Register a site to a trial.

    This performs an atomic multi-table transaction:
    1. Upsert site (find existing or create new)
    2. Insert trial_sites link with status='pending'

    Args:
        session: Database session
        input_data: Site and trial information

    Returns:
        Registration result with site and link information

    Raises:
        TrialNotFoundError: If trial doesn't exist
        DuplicateSiteLinkError: If site is already linked to trial
    """
    # Verify trial exists
    trial = session.query(Trial).filter_by(id=input_data.trial_id).first()
    if not trial:
        raise TrialNotFoundError(f"Trial with id {input_data.trial_id} not found")

    # Upsert site: find existing by name+country or create new
    site = (
        session.query(Site)
        .filter_by(name=input_data.site_name, country=input_data.country)
        .first()
    )

    if not site:
        # Create new site
        site = Site(name=input_data.site_name, country=input_data.country)
        session.add(site)
        session.flush()  # Get site ID

    # Capture IDs before potential error
    site_id = site.id
    trial_id = input_data.trial_id

    # Insert trial_sites link
    trial_site = TrialSite(
        trial_id=trial_id, site_id=site_id, status="pending"
    )
    session.add(trial_site)

    try:
        session.flush()  # Will raise IntegrityError if duplicate
    except IntegrityError:
        raise DuplicateSiteLinkError(
            f"Site {site_id} is already linked to trial {trial_id}"
        )

    return RegisterSiteToTrialResponse(
        trial_id=trial_id,
        site_id=site_id,
        site_name=input_data.site_name,
        country=input_data.country,
        link_status="pending",
    )
