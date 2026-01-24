"""
Page Registry Module
Centralized page registration system for the dashboard
"""

from dataclasses import dataclass
from typing import Callable, Optional
import page_modules


@dataclass
class Page:
    """
    Represents a dashboard page.

    Attributes:
        name: Display name with emoji (e.g., "🏠 Overview")
        render_func: Function to call to render the page
        section: Section this page belongs to ("main" or "other")
        description: Optional tooltip/description for the page
    """
    name: str
    render_func: Callable
    section: str = "main"
    description: Optional[str] = None


class PageRegistry:
    """
    Registry for managing dashboard pages.
    Provides centralized page management and makes it easy to add/remove/reorder pages.
    """

    def __init__(self):
        self._pages = []
        self._register_default_pages()

    def _register_default_pages(self):
        """Register all default pages with proper parameter wrapping"""

        # Main pages
        self.register(
            "🏠 Overview",
            lambda vacuum_df, personnel_df: page_modules.overview.render(vacuum_df, personnel_df),
            section="main",
            description="System overview and key metrics"
        )

        self.register(
            "🔧 Vacuum Performance",
            lambda vacuum_df, personnel_df: page_modules.vacuum.render(vacuum_df, personnel_df),
            section="main",
            description="Vacuum pressure monitoring"
        )

        self.register(
            "🌳 Tapping Operations",
            lambda vacuum_df, personnel_df: page_modules.tapping.render(personnel_df, vacuum_df),
            section="main",
            description="Tapping productivity tracking"
        )

        self.register(
            "👷 Employee Performance",
            lambda vacuum_df, personnel_df: page_modules.employees.render(personnel_df),
            section="main",
            description="Employee metrics and hours worked"
        )

        self.register(
            "⭐ Employee Effectiveness",
            lambda vacuum_df, personnel_df: page_modules.employee_effectiveness.render(personnel_df, vacuum_df),
            section="main",
            description="Detailed effectiveness analysis"
        )

        self.register(
            "🔨 Maintenance Tracking",
            lambda vacuum_df, personnel_df: page_modules.maintenance.render(vacuum_df, personnel_df),
            section="main",
            description="Maintenance and leak detection"
        )

        # Other pages (⚠️ Needs Work)
        self.register(
            "🌍 Interactive Map",
            lambda vacuum_df, personnel_df: page_modules.sensor_map.render(vacuum_df, personnel_df),
            section="other",
            description="Geographic sensor visualization"
        )

        self.register(
            "📝 Daily Summary",
            lambda vacuum_df, personnel_df: page_modules.daily_summary.render(vacuum_df, personnel_df),
            section="other",
            description="Daily reports and trends"
        )

        self.register(
            "🗺️ Problem Clusters",
            lambda vacuum_df, personnel_df: page_modules.problem_clusters.render(vacuum_df),
            section="other",
            description="Geographic problem clustering"
        )

        self.register(
            "🔧 Repairs Analysis",
            lambda vacuum_df, personnel_df: page_modules.repairs_analysis.render(personnel_df, vacuum_df),
            section="other",
            description="Parse unstructured repair notes"
        )

        self.register(
            "⚠️ Alerts",
            lambda vacuum_df, personnel_df: page_modules.data_quality.render(personnel_df, vacuum_df),
            section="other",
            description="Data quality alerts"
        )

        self.register(
            "🌡️ Sap Flow Forecast",
            lambda vacuum_df, personnel_df: page_modules.sap_forecast.render(vacuum_df, personnel_df),
            section="other",
            description="SAP production forecasting"
        )

        self.register(
            "📊 Raw Data",
            lambda vacuum_df, personnel_df: page_modules.raw_data.render(vacuum_df, personnel_df),
            section="other",
            description="Raw data explorer"
        )

    def register(self, name: str, render_func: Callable, section: str = "main", description: Optional[str] = None):
        """
        Register a new page.

        Args:
            name: Display name with emoji
            render_func: Function to render the page
            section: "main" or "other"
            description: Optional description
        """
        page = Page(name=name, render_func=render_func, section=section, description=description)
        self._pages.append(page)

    def get_pages_by_section(self, section: str) -> list[Page]:
        """
        Get all pages in a specific section.

        Args:
            section: "main" or "other"

        Returns:
            List of Page objects in that section
        """
        return [p for p in self._pages if p.section == section]

    def get_page_names_by_section(self, section: str) -> list[str]:
        """
        Get page names for a specific section.

        Args:
            section: "main" or "other"

        Returns:
            List of page names
        """
        return [p.name for p in self.get_pages_by_section(section)]

    def get_all_page_names(self) -> list[str]:
        """Get all page names"""
        return [p.name for p in self._pages]

    def get_page(self, name: str) -> Optional[Page]:
        """
        Get a page by name.

        Args:
            name: Page name to find

        Returns:
            Page object or None if not found
        """
        for page in self._pages:
            if page.name == name:
                return page
        return None

    def render_page(self, name: str, *args, **kwargs):
        """
        Render a page by name.

        Args:
            name: Page name to render
            *args: Positional arguments to pass to render function
            **kwargs: Keyword arguments to pass to render function

        Raises:
            ValueError: If page not found
        """
        page = self.get_page(name)
        if page is None:
            raise ValueError(f"Page not found: {name}")

        # Call the render function with provided arguments
        page.render_func(*args, **kwargs)


# Create a global registry instance
_registry = PageRegistry()


def get_registry() -> PageRegistry:
    """Get the global page registry instance"""
    return _registry
