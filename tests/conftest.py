"""Shared pytest fixtures for hotel generator tests."""

import pytest

from hotel_generator.settings import Settings


@pytest.fixture
def settings():
    """Default settings instance."""
    return Settings()


@pytest.fixture
def fdm_params():
    """Default FDM building parameters (available after Step 4)."""
    try:
        from hotel_generator.config import BuildingParams

        return BuildingParams(
            style_name="modern",
            width=30.0,
            depth=25.0,
            num_floors=4,
            floor_height=5.0,
            printer_type="fdm",
        )
    except ImportError:
        pytest.skip("BuildingParams not yet implemented")


@pytest.fixture
def resin_params():
    """Default resin building parameters (available after Step 4)."""
    try:
        from hotel_generator.config import BuildingParams

        return BuildingParams(
            style_name="modern",
            width=30.0,
            depth=25.0,
            num_floors=4,
            floor_height=5.0,
            printer_type="resin",
        )
    except ImportError:
        pytest.skip("BuildingParams not yet implemented")


@pytest.fixture
def builder(settings):
    """HotelBuilder instance (available after Step 5)."""
    try:
        from hotel_generator.assembly.building import HotelBuilder

        return HotelBuilder(settings)
    except ImportError:
        pytest.skip("HotelBuilder not yet implemented")
