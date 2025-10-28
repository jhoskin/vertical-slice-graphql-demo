"""
Audit logging decorator for commands.

Provides the @audited decorator to automatically write audit logs
when commands are executed successfully or fail.
"""
import functools
import json
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app.infrastructure.database.models import AuditLog


def audited(
    action: str,
    entity: str,
    entity_id_fn: Optional[Callable[[Any], str]] = None,
    user: str = "system",
) -> Callable:
    """
    Decorator to add audit logging to a command handler.

    Args:
        action: The action being performed (e.g., "create_trial", "update_trial_metadata")
        entity: The entity type being operated on (e.g., "trial", "site")
        entity_id_fn: Optional function to extract entity_id from the result.
                     If None, assumes result has an 'id' attribute.
        user: The user performing the action (default: "system")

    Usage:
        @audited(action="create_trial", entity="trial", entity_id_fn=lambda r: str(r.id))
        def create_trial_handler(session: Session, input_data: dict) -> TrialOutput:
            # ... handler logic
            return result
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Execute the handler
            try:
                result = func(*args, **kwargs)

                # Extract session from args (assume first arg is session)
                session = args[0] if args and isinstance(args[0], Session) else None

                if session is not None:
                    # Extract entity_id
                    if entity_id_fn:
                        entity_id = entity_id_fn(result)
                    elif hasattr(result, "id"):
                        entity_id = str(result.id)
                    else:
                        entity_id = "unknown"

                    # Create payload from result
                    if hasattr(result, "__dict__"):
                        # Handle dataclass or object with __dict__
                        payload = {
                            k: v
                            for k, v in result.__dict__.items()
                            if not k.startswith("_")
                        }
                    else:
                        payload = {"result": str(result)}

                    # Write audit log
                    audit_log = AuditLog(
                        user=user,
                        action=action,
                        entity=entity,
                        entity_id=entity_id,
                        payload_json=json.dumps(payload, default=str),
                    )
                    session.add(audit_log)
                    # Note: Don't commit here - let the caller commit

                return result

            except Exception as e:
                # Log failure
                session = args[0] if args and isinstance(args[0], Session) else None
                if session is not None:
                    error_log = AuditLog(
                        user=user,
                        action=f"{action}_failed",
                        entity=entity,
                        entity_id="error",
                        payload_json=json.dumps(
                            {"error": str(e), "error_type": type(e).__name__}
                        ),
                    )
                    session.add(error_log)
                    # Note: Don't commit here - let rollback happen

                # Re-raise the exception
                raise

        return wrapper

    return decorator
