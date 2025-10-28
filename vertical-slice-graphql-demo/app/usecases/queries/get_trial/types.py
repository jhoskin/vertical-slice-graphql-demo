"""
Type definitions for get_trial query.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import strawberry


@strawberry.type
@dataclass
class SiteInfo:
    """Site information for trial detail."""
    id: str
    name: str
    country: str
    link_status: str


@strawberry.type
@dataclass
class ProtocolInfo:
    """Protocol version information."""
    id: str
    version: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


@strawberry.type
@dataclass
class TrialDetail:
    """Detailed trial information with sites and protocol."""
    id: str
    name: str
    phase: str
    status: str
    created_at: datetime
    updated_at: datetime
    sites: list[SiteInfo]
    latest_protocol: Optional[ProtocolInfo]
