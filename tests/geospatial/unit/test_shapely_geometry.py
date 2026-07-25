"""Unit tests for Shapely geometry construction and WKT serialization.

Tests bbox geometry creation, WKT round-trip, MultiPolygon parsing,
and Polygon footprint construction.
"""

import pytest

# Shapely is a soft dependency for unit tests — skip if not installed
shapely = pytest.importorskip("shapely")

from shapely.geometry import MultiPolygon, Polygon, box
from shapely import wkt


class TestBboxGeometry:
    """Test bbox-to-Polygon conversion using shapely.geometry.box."""

    def test_box_creation(self):
        """Test shapely.geometry.box creates a valid Polygon."""
        polygon = box(-62.0, -28.0, -58.0, -25.0)
        assert isinstance(polygon, Polygon)
        assert polygon.is_valid

    def test_box_bounds(self):
        """Test box bounds match input."""
        minx, miny, maxx, maxy = -62.0, -28.0, -58.0, -25.0
        polygon = box(minx, miny, maxx, maxy)
        assert polygon.bounds == (minx, miny, maxx, maxy)

    def test_box_area(self):
        """Test box area calculation."""
        polygon = box(0, 0, 10, 10)
        assert polygon.area == 100.0


class TestWKTRoundTrip:
    """Test WKT serialization and deserialization."""

    def test_polygon_wkt_round_trip(self):
        """Test Polygon → WKT → Polygon preserves geometry."""
        original = box(-62.0, -28.0, -58.0, -25.0)
        wkt_str = wkt.dumps(original)
        restored = wkt.loads(wkt_str)
        assert isinstance(restored, Polygon)
        assert original.equals(restored)

    def test_multipolygon_wkt_round_trip(self):
        """Test MultiPolygon → WKT → MultiPolygon preserves geometry."""
        poly1 = box(0, 0, 5, 5)
        poly2 = box(10, 10, 15, 15)
        original = MultiPolygon([poly1, poly2])
        wkt_str = wkt.dumps(original)
        restored = wkt.loads(wkt_str)
        assert isinstance(restored, MultiPolygon)
        assert original.equals(restored)

    def test_wkt_string_contains_geometry_type(self):
        """Test WKT output contains expected geometry type."""
        polygon = box(0, 0, 1, 1)
        wkt_str = wkt.dumps(polygon)
        assert "POLYGON" in wkt_str

    def test_multipolygon_wkt_string(self):
        """Test MultiPolygon WKT output."""
        poly = box(0, 0, 1, 1)
        mp = MultiPolygon([poly])
        wkt_str = wkt.dumps(mp)
        assert "MULTIPOLYGON" in wkt_str


class TestMultiPolygonConstruction:
    """Test MultiPolygon construction from multiple polygons."""

    def test_single_polygon_multipolygon(self):
        """Test MultiPolygon with a single polygon."""
        poly = box(0, 0, 10, 10)
        mp = MultiPolygon([poly])
        assert len(list(mp.geoms)) == 1

    def test_multiple_polygons(self):
        """Test MultiPolygon with multiple non-overlapping polygons."""
        poly1 = box(0, 0, 5, 5)
        poly2 = box(10, 10, 15, 15)
        mp = MultiPolygon([poly1, poly2])
        assert len(list(mp.geoms)) == 2

    def test_multipolygon_area(self):
        """Test MultiPolygon total area."""
        poly1 = box(0, 0, 5, 5)
        poly2 = box(0, 0, 5, 5)  # same area
        mp = MultiPolygon([poly1, poly2])
        assert mp.area == 50.0  # 25 + 25


class TestPolygonFootprint:
    """Test Polygon construction for footprint_geometry field."""

    def test_simple_polygon(self):
        """Test simple rectangular polygon."""
        coords = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        polygon = Polygon(coords)
        assert polygon.is_valid
        assert polygon.area == 100.0

    def test_polygon_from_exterior(self):
        """Test Polygon created from exterior ring."""
        polygon = box(-58.5, -27.5, -58.0, -27.0)
        assert polygon.is_valid
        assert polygon.centroid.x == pytest.approx(-58.25, abs=0.01)

    def test_null_footprint(self):
        """Test that footprint_geometry can be None (nullable field)."""
        # This validates the Optional[Polygon] type in ProcessedLayer
        from src.geospatial.domain.models import ProcessedLayer

        layer = ProcessedLayer(
            raw_file_id=1,
            processing_job_id="job-1",
            source_code="SMAP",
            variable_name="sm_surface",
            file_path="/data/test.tif",
            crs="EPSG:4326",
            bbox=[-62.0, -28.0, -58.0, -25.0],
            resolution_x=0.1,
            resolution_y=0.1,
            width=10,
            height=10,
            nodata_value=-9999.0,
            min_value=0.0,
            max_value=1.0,
            mean_value=0.5,
            valid_pixel_count=100,
            nodata_pixel_count=0,
            acquisition_date="2024-01-01",
            processing_version="v1",
        )
        assert layer.footprint_geometry is None

    def test_polygon_as_footprint(self):
        """Test setting a Polygon as footprint_geometry."""
        from src.geospatial.domain.models import ProcessedLayer

        footprint = box(-62.0, -28.0, -58.0, -25.0)
        layer = ProcessedLayer(
            raw_file_id=1,
            processing_job_id="job-1",
            source_code="SMAP",
            variable_name="sm_surface",
            file_path="/data/test.tif",
            crs="EPSG:4326",
            bbox=[-62.0, -28.0, -58.0, -25.0],
            resolution_x=0.1,
            resolution_y=0.1,
            width=10,
            height=10,
            nodata_value=-9999.0,
            min_value=0.0,
            max_value=1.0,
            mean_value=0.5,
            valid_pixel_count=100,
            nodata_pixel_count=0,
            acquisition_date="2024-01-01",
            processing_version="v1",
            footprint_geometry=footprint,
        )
        assert layer.footprint_geometry is not None
        assert isinstance(layer.footprint_geometry, Polygon)
