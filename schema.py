"""
Schema Mapper Module
Centralized column mapping for vacuum and personnel data
"""

import pandas as pd


class SchemaMapper:
    """
    Centralized schema mapping for finding columns in DataFrames.
    This eliminates duplicated column-finding logic across the codebase.
    """

    # Define all possible column name variations for each logical field
    COLUMN_ALIASES = {
        # Vacuum data columns
        'sensor_name': ['Sensor Name', 'sensor', 'mainline', 'location', 'name', 'Mainline'],
        'vacuum_reading': ['Vacuum Reading', 'vacuum', 'reading', 'Vacuum', 'Reading'],
        'timestamp': ['Last Communication', 'Timestamp', 'timestamp', 'time',
                     'datetime', 'Date', 'date', 'last_communication', 'last communication'],
        'latitude': ['Latitude', 'lat', 'Lat'],
        'longitude': ['Longitude', 'lon', 'long', 'Lon', 'Long', 'lng'],
        'site': ['Site', 'site', 'location_site'],

        # Personnel data columns
        'employee_name': ['Employee Name', 'employee', 'name', 'Name', 'Employee'],
        'employee_id': ['Employee ID', 'employee_id', 'id', 'ID', 'emp_id'],
        'date': ['Date', 'date', 'timestamp', 'Timestamp'],
        'job_type': ['Job Type', 'job_type', 'job', 'type', 'Job'],
        'hours': ['Hours', 'hours', 'Hours Worked', 'time'],
        'mainline': ['Mainline', 'mainline', 'line', 'Sensor Name', 'sensor'],

        # Tapping columns
        'taps_put_in': ['Taps Put In', 'taps_put_in', 'taps put in', 'Taps Installed', 'installed'],
        'taps_removed': ['Taps Removed', 'taps_removed', 'taps removed', 'removed'],
        'taps_capped': ['Taps Capped', 'taps_capped', 'taps capped', 'capped'],

        # Maintenance columns
        'repairs_needed': ['Repairs Needed', 'repairs_needed', 'repairs', 'Repairs'],
        'notes': ['Notes', 'notes', 'comments', 'Comments', 'description'],
    }

    def __init__(self, df=None):
        """
        Initialize schema mapper.

        Args:
            df: Optional DataFrame to bind to this mapper instance
        """
        self.df = df
        self._column_cache = {}

    @staticmethod
    def find_column(df, *possible_names):
        """
        Find a column by checking multiple possible names (case-insensitive).
        This is a static method for backward compatibility with existing code.

        Args:
            df: DataFrame to search
            *possible_names: Variable number of possible column names to check

        Returns:
            Actual column name if found, None otherwise
        """
        if df is None or df.empty:
            return None

        df_cols_lower = {col.lower(): col for col in df.columns}

        for name in possible_names:
            name_lower = name.lower()
            if name_lower in df_cols_lower:
                return df_cols_lower[name_lower]

        return None

    def get_column(self, field_name, df=None):
        """
        Get the actual column name for a logical field.
        Uses caching to improve performance on repeated calls.

        Args:
            field_name: Logical field name (e.g., 'sensor_name', 'employee_id')
            df: DataFrame to search (uses instance df if not provided)

        Returns:
            Actual column name if found, None otherwise

        Raises:
            ValueError: If field_name is not in COLUMN_ALIASES
        """
        if field_name not in self.COLUMN_ALIASES:
            raise ValueError(f"Unknown field name: {field_name}. Valid names: {list(self.COLUMN_ALIASES.keys())}")

        target_df = df if df is not None else self.df
        if target_df is None or target_df.empty:
            return None

        # Use cache if available (only for instance df)
        cache_key = field_name
        if df is None and cache_key in self._column_cache:
            return self._column_cache[cache_key]

        # Find column using aliases
        possible_names = self.COLUMN_ALIASES[field_name]
        result = self.find_column(target_df, *possible_names)

        # Cache result if using instance df
        if df is None and result is not None:
            self._column_cache[cache_key] = result

        return result

    def get_all_columns(self, df=None):
        """
        Get a dictionary mapping all logical field names to actual column names.
        Only includes fields that exist in the DataFrame.

        Args:
            df: DataFrame to search (uses instance df if not provided)

        Returns:
            Dictionary of {field_name: actual_column_name}
        """
        target_df = df if df is not None else self.df
        if target_df is None or target_df.empty:
            return {}

        result = {}
        for field_name in self.COLUMN_ALIASES.keys():
            col = self.get_column(field_name, target_df)
            if col is not None:
                result[field_name] = col

        return result

    def has_column(self, field_name, df=None):
        """
        Check if a logical field exists in the DataFrame.

        Args:
            field_name: Logical field name to check
            df: DataFrame to check (uses instance df if not provided)

        Returns:
            True if field exists, False otherwise
        """
        return self.get_column(field_name, df) is not None

    def validate_required_columns(self, required_fields, df=None):
        """
        Validate that all required fields exist in the DataFrame.

        Args:
            required_fields: List of logical field names that must exist
            df: DataFrame to validate (uses instance df if not provided)

        Returns:
            Tuple of (is_valid, missing_fields)
                is_valid: True if all required fields exist
                missing_fields: List of missing field names
        """
        missing = []
        for field in required_fields:
            if not self.has_column(field, df):
                missing.append(field)

        return (len(missing) == 0, missing)

    def clear_cache(self):
        """Clear the column name cache."""
        self._column_cache = {}


# Convenience function for backward compatibility
def find_column(df, *possible_names):
    """
    Find a column by checking multiple possible names (case-insensitive).

    This is a convenience function that maintains backward compatibility.
    For new code, consider using SchemaMapper class instead.

    Args:
        df: DataFrame to search
        *possible_names: Variable number of possible column names to check

    Returns:
        Actual column name if found, None otherwise
    """
    return SchemaMapper.find_column(df, *possible_names)
