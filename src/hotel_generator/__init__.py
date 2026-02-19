"""Procedural 3D hotel generator for Monopoly-scale game pieces."""

import logging

import manifold3d

# Prevent 4-segment circles for small radii
manifold3d.set_circular_segments(16)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
