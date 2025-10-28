"""
Shared validation logic for trial management commands.

This module demonstrates the principle: "things that change together, live together."
Both create_trial and update_trial_metadata need phase validation, so it lives
in their common parent folder rather than a root-level "shared" package.
"""

# Valid clinical trial phases
VALID_PHASES = {
    "Phase I",
    "Phase II",
    "Phase III",
    "Phase IV",
    "Preclinical",
    "terminated",
    "completed",
}

# Valid trial statuses
VALID_STATUSES = {
    "draft",
    "active",
    "paused",
    "completed",
    "terminated",
}

# Allowed phase transitions (from_phase -> set of allowed to_phases)
PHASE_TRANSITIONS = {
    "Preclinical": {"Phase I"},
    "Phase I": {"Phase II", "terminated"},
    "Phase II": {"Phase III", "terminated"},
    "Phase III": {"Phase IV", "terminated"},
    "Phase IV": {"completed", "terminated"},
}


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


def validate_phase(phase: str) -> None:
    """
    Validate that a phase is valid.

    Args:
        phase: The phase to validate

    Raises:
        ValidationError: If phase is invalid
    """
    if phase not in VALID_PHASES:
        raise ValidationError(
            f"Invalid phase: {phase}. Must be one of: {', '.join(sorted(VALID_PHASES))}"
        )


def validate_status(status: str) -> None:
    """
    Validate that a status is valid.

    Args:
        status: The status to validate

    Raises:
        ValidationError: If status is invalid
    """
    if status not in VALID_STATUSES:
        raise ValidationError(
            f"Invalid status: {status}. Must be one of: {', '.join(sorted(VALID_STATUSES))}"
        )


def validate_phase_transition(from_phase: str, to_phase: str) -> None:
    """
    Validate that a phase transition is allowed.

    Args:
        from_phase: The current phase
        to_phase: The desired new phase

    Raises:
        ValidationError: If transition is not allowed
    """
    # First validate both phases are valid
    validate_phase(from_phase)
    validate_phase(to_phase)

    # If same phase, no transition needed
    if from_phase == to_phase:
        return

    # Check if transition is allowed
    allowed_transitions = PHASE_TRANSITIONS.get(from_phase, set())
    if to_phase not in allowed_transitions:
        raise ValidationError(
            f"Invalid phase transition from {from_phase} to {to_phase}. "
            f"Allowed transitions: {', '.join(sorted(allowed_transitions)) if allowed_transitions else 'none'}"
        )
