"""The one exception tools may raise — stable error codes from tool-registry.md.

Code-standards.md error handling: tools raise only ``ToolError(message_code)``
with the stable code string from tool-registry.md; nodes catch it at their
boundary and translate to state per their failure spec — a failing tool never
crashes the turn.
"""


class ToolError(Exception):
    """Tool contract failure carrying the stable registry code (e.g. ``invalid_profile``)."""
