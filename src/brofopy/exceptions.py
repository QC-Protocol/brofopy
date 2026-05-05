"""Custom exceptions for brofopy."""


class BronformatParseError(Exception):
    """Raised when a Bronformat file cannot be parsed.

    Parameters
    ----------
    message : str
        Human-readable description of the parse failure.
    """
