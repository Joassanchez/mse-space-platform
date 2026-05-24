"""Repository interfaces for weather data."""

from abc import ABC, abstractmethod
from typing import Optional

from src.weather.domain.models import WeatherSnapshot


class WeatherSnapshotRepository(ABC):
    """Persistence interface for weather_snapshots."""

    @abstractmethod
    def save(self, snapshot: WeatherSnapshot) -> int:
        """Persist a weather snapshot.

        Args:
            snapshot: The snapshot to save.

        Returns:
            Database-assigned ID.
        """
        pass

    @abstractmethod
    def find_by_region_and_date(
        self, region_id: int, date_from: str, date_to: str
    ) -> list[WeatherSnapshot]:
        """Find weather snapshots for a region within a date range.

        Args:
            region_id: The regions.id value.
            date_from: ISO start date (inclusive).
            date_to: ISO end date (inclusive).

        Returns:
            List of matching WeatherSnapshot objects, newest first.
        """
        pass

    @abstractmethod
    def find_latest_by_region(
        self, region_id: int
    ) -> Optional[WeatherSnapshot]:
        """Find the most recent weather snapshot for a region.

        Args:
            region_id: The regions.id value.

        Returns:
            The latest WeatherSnapshot or None.
        """
        pass
