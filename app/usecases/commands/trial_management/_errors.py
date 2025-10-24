"""
Common error classes for trial management commands.
"""
from restate import TerminalError


class StaleDataError(TerminalError):
    """
    Raised when an update is attempted with stale data.

    This indicates the client's version of the data is outdated
    and they should refresh before attempting the update again.

    Inherits from TerminalError to prevent Restate from retrying
    the operation, as stale data is a client error that won't be
    resolved by retrying.
    """
    pass
