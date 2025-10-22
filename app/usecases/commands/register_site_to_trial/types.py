"""
Type definitions for register_site_to_trial command.
"""
from dataclasses import dataclass

import strawberry


@strawberry.input
class RegisterSiteToTrialInput:
    """Input for registering a site to a trial."""
    trial_id: int
    site_name: str
    country: str


@strawberry.type
@dataclass
class RegisterSiteToTrialOutput:
    """Output from registering a site to a trial."""
    trial_id: int
    site_id: int
    site_name: str
    country: str
    link_status: str
