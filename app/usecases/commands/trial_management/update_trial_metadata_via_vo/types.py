"""
Type definitions for update_trial_metadata_via_vo command.

Reuses types from the original update_trial_metadata command.
"""
from app.usecases.commands.trial_management.update_trial_metadata.types import (
    UpdateTrialMetadataInput,
    UpdateTrialMetadataResponse,
)

__all__ = ["UpdateTrialMetadataInput", "UpdateTrialMetadataResponse"]
