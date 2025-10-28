"""
Unit tests for shared trial management validation logic.
"""
import pytest

from app.usecases.commands.trial_management._validation import (
    VALID_PHASES,
    VALID_STATUSES,
    ValidationError,
    validate_phase,
    validate_phase_transition,
    validate_status,
)


def test_validate_phase_success() -> None:
    """Test that valid phases pass validation."""
    for phase in VALID_PHASES:
        validate_phase(phase)  # Should not raise


def test_validate_phase_failure() -> None:
    """Test that invalid phases raise ValidationError."""
    with pytest.raises(ValidationError, match="Invalid phase"):
        validate_phase("Phase V")

    with pytest.raises(ValidationError, match="Invalid phase"):
        validate_phase("invalid")


def test_validate_status_success() -> None:
    """Test that valid statuses pass validation."""
    for status in VALID_STATUSES:
        validate_status(status)  # Should not raise


def test_validate_status_failure() -> None:
    """Test that invalid statuses raise ValidationError."""
    with pytest.raises(ValidationError, match="Invalid status"):
        validate_status("invalid_status")

    with pytest.raises(ValidationError, match="Invalid status"):
        validate_status("archived")


def test_validate_phase_transition_same_phase() -> None:
    """Test that staying in same phase is allowed."""
    validate_phase_transition("Phase I", "Phase I")  # Should not raise


def test_validate_phase_transition_valid() -> None:
    """Test valid phase transitions."""
    # Preclinical -> Phase I
    validate_phase_transition("Preclinical", "Phase I")

    # Phase I -> Phase II
    validate_phase_transition("Phase I", "Phase II")

    # Phase II -> Phase III
    validate_phase_transition("Phase II", "Phase III")

    # Phase III -> Phase IV
    validate_phase_transition("Phase III", "Phase IV")


def test_validate_phase_transition_to_terminated() -> None:
    """Test that trials can be terminated from most phases."""
    validate_phase_transition("Phase I", "terminated")
    validate_phase_transition("Phase II", "terminated")
    validate_phase_transition("Phase III", "terminated")


def test_validate_phase_transition_invalid() -> None:
    """Test that invalid phase transitions raise ValidationError."""
    # Can't skip phases
    with pytest.raises(ValidationError, match="Invalid phase transition"):
        validate_phase_transition("Phase I", "Phase III")

    # Can't go backwards
    with pytest.raises(ValidationError, match="Invalid phase transition"):
        validate_phase_transition("Phase II", "Phase I")

    # Can't complete from Phase II
    with pytest.raises(ValidationError, match="Invalid phase transition"):
        validate_phase_transition("Phase II", "completed")


def test_validate_phase_transition_invalid_phase() -> None:
    """Test that transitions with invalid phases raise ValidationError."""
    with pytest.raises(ValidationError, match="Invalid phase"):
        validate_phase_transition("Phase V", "Phase I")

    with pytest.raises(ValidationError, match="Invalid phase"):
        validate_phase_transition("Phase I", "Phase V")
