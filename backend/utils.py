"""
Shared utility functions for the chess coaching backend.
"""

from datetime import datetime, timezone
from typing import Optional, Union


def parse_datetime(value: Union[str, datetime, None]) -> Optional[datetime]:
    """
    Parse a datetime value from various formats to a timezone-aware datetime.
    
    Handles:
    - ISO format strings with or without timezone
    - datetime objects (naive or aware)
    - None values
    
    Returns:
        Timezone-aware datetime in UTC, or None if parsing fails
    """
    if value is None:
        return None
    
    if isinstance(value, datetime):
        # Make sure it's timezone-aware
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    
    if isinstance(value, str):
        try:
            # Handle ISO format with 'Z' suffix
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None
    
    return None


def get_sortable_datetime(value: Union[str, datetime, None]) -> datetime:
    """
    Get a sortable datetime, returning a minimum datetime for None/invalid values.
    Useful for sorting lists of documents by date.
    """
    parsed = parse_datetime(value)
    if parsed is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return parsed
