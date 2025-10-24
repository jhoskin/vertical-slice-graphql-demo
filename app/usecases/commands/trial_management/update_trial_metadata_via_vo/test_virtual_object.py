"""
Tests for Trial Virtual Object.

These tests verify that the Virtual Object correctly delegates to the existing
handler and properly handles updates.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.usecases.commands.trial_management.update_trial_metadata_via_vo.virtual_object import update_metadata


@pytest.mark.asyncio
async def test_update_metadata_success():
    """Test successful trial metadata update via Virtual Object."""
    # Mock context
    ctx = MagicMock()
    ctx.key.return_value = "123"  # trial_id

    # Mock update data
    update_data = {
        "name": "Updated Trial Name",
        "phase": "Phase II",
    }

    # Mock the handler response
    mock_response = MagicMock()
    mock_response.id = 123
    mock_response.name = "Updated Trial Name"
    mock_response.phase = "Phase II"
    mock_response.status = "draft"
    mock_response.created_at = datetime(2025, 1, 1, 12, 0, 0)
    mock_response.changes = "name: 'Old Name' -> 'Updated Trial Name'; phase: 'Phase I' -> 'Phase II'"

    # Patch the handler and session
    with patch("app.usecases.commands.trial_management.update_trial_metadata_via_vo.virtual_object.session_scope") as mock_session_scope, \
         patch("app.usecases.commands.trial_management.update_trial_metadata_via_vo.virtual_object.update_trial_metadata_handler") as mock_handler:

        # Configure mocks
        mock_handler.return_value = mock_response
        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__.return_value = mock_session

        # Call the Virtual Object handler
        result = await update_metadata(ctx, update_data)

        # Verify handler was called with correct input
        mock_handler.assert_called_once()
        call_args = mock_handler.call_args[0]
        assert call_args[0] == mock_session
        assert call_args[1].trial_id == 123
        assert call_args[1].name == "Updated Trial Name"
        assert call_args[1].phase == "Phase II"

        # Verify response
        assert result["id"] == 123
        assert result["name"] == "Updated Trial Name"
        assert result["phase"] == "Phase II"
        assert result["status"] == "draft"
        assert result["created_at"] == "2025-01-01T12:00:00"
        assert "name" in result["changes"]
        assert "phase" in result["changes"]


@pytest.mark.asyncio
async def test_update_metadata_name_only():
    """Test updating only the trial name."""
    ctx = MagicMock()
    ctx.key.return_value = "456"

    update_data = {"name": "New Name Only"}

    mock_response = MagicMock()
    mock_response.id = 456
    mock_response.name = "New Name Only"
    mock_response.phase = "Phase I"
    mock_response.status = "active"
    mock_response.created_at = datetime(2025, 1, 1, 12, 0, 0)
    mock_response.changes = "name: 'Old Name' -> 'New Name Only'"

    with patch("app.usecases.commands.trial_management.update_trial_metadata_via_vo.virtual_object.session_scope") as mock_session_scope, \
         patch("app.usecases.commands.trial_management.update_trial_metadata_via_vo.virtual_object.update_trial_metadata_handler") as mock_handler:

        mock_handler.return_value = mock_response
        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__.return_value = mock_session

        result = await update_metadata(ctx, update_data)

        # Verify only name was passed to handler
        call_args = mock_handler.call_args[0]
        assert call_args[1].name == "New Name Only"
        assert call_args[1].phase is None

        assert result["name"] == "New Name Only"
        assert "name" in result["changes"]


@pytest.mark.asyncio
async def test_update_metadata_phase_only():
    """Test updating only the trial phase."""
    ctx = MagicMock()
    ctx.key.return_value = "789"

    update_data = {"phase": "Phase III"}

    mock_response = MagicMock()
    mock_response.id = 789
    mock_response.name = "Existing Name"
    mock_response.phase = "Phase III"
    mock_response.status = "active"
    mock_response.created_at = datetime(2025, 1, 1, 12, 0, 0)
    mock_response.changes = "phase: 'Phase II' -> 'Phase III'"

    with patch("app.usecases.commands.trial_management.update_trial_metadata_via_vo.virtual_object.session_scope") as mock_session_scope, \
         patch("app.usecases.commands.trial_management.update_trial_metadata_via_vo.virtual_object.update_trial_metadata_handler") as mock_handler:

        mock_handler.return_value = mock_response
        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__.return_value = mock_session

        result = await update_metadata(ctx, update_data)

        # Verify only phase was passed to handler
        call_args = mock_handler.call_args[0]
        assert call_args[1].name is None
        assert call_args[1].phase == "Phase III"

        assert result["phase"] == "Phase III"
        assert "phase" in result["changes"]


@pytest.mark.asyncio
async def test_update_metadata_propagates_validation_error():
    """Test that validation errors from handler are propagated."""
    ctx = MagicMock()
    ctx.key.return_value = "999"

    update_data = {"phase": "Invalid Phase"}

    with patch("app.usecases.commands.trial_management.update_trial_metadata_via_vo.virtual_object.session_scope") as mock_session_scope, \
         patch("app.usecases.commands.trial_management.update_trial_metadata_via_vo.virtual_object.update_trial_metadata_handler") as mock_handler:

        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__.return_value = mock_session

        # Handler raises validation error
        from app.usecases.commands.trial_management._validation import ValidationError
        mock_handler.side_effect = ValidationError("Invalid phase value")

        # Should propagate the error
        with pytest.raises(ValidationError, match="Invalid phase value"):
            await update_metadata(ctx, update_data)
