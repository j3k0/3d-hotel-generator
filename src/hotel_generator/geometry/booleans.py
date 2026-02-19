"""Boolean operations with empty-manifold guards.

All operations filter empty manifolds before processing to prevent
silent propagation and batch_boolean crashes.
"""

from manifold3d import Manifold, OpType

from hotel_generator.errors import GeometryError


def _filter_empty(parts: list[Manifold]) -> list[Manifold]:
    """Remove empty manifolds from a list."""
    return [p for p in parts if not p.is_empty()]


def union_all(parts: list[Manifold]) -> Manifold:
    """Union a list of manifolds. Filters empty manifolds first.

    Returns an empty Manifold if no valid parts remain.
    """
    valid = _filter_empty(parts)
    if not valid:
        return Manifold()
    if len(valid) == 1:
        return valid[0]
    return Manifold.batch_boolean(valid, OpType.Add)


def difference_all(base: Manifold, cutouts: list[Manifold]) -> Manifold:
    """Subtract all cutouts from base. Filters empty manifolds first.

    Raises GeometryError if base is empty.
    """
    if base.is_empty():
        raise GeometryError("Cannot subtract from an empty base manifold")
    valid_cutouts = _filter_empty(cutouts)
    if not valid_cutouts:
        return base
    # batch_boolean takes [base, cutout1, cutout2, ...] with OpType.Subtract
    # but that subtracts each sequentially. Use union of cutouts then single subtract.
    cutter = union_all(valid_cutouts)
    if cutter.is_empty():
        return base
    return base - cutter


def compose_disjoint(parts: list[Manifold]) -> Manifold:
    """Compose non-overlapping manifolds in O(1).

    Only valid for solids that do NOT overlap. Overlapping solids
    will produce invalid geometry. Use union_all for overlapping parts.
    """
    valid = _filter_empty(parts)
    if not valid:
        return Manifold()
    if len(valid) == 1:
        return valid[0]
    return Manifold.compose(valid)
