"""Custom exception hierarchy for the hotel generator."""


class HotelGeneratorError(Exception):
    """Base exception for all hotel generator errors."""


class InvalidParamsError(HotelGeneratorError):
    """Bad user input (maps to HTTP 400)."""


class GeometryError(HotelGeneratorError):
    """CSG or geometry construction failure (maps to HTTP 500)."""


class ValidationError(HotelGeneratorError):
    """Post-generation validation check failure (maps to HTTP 500)."""
