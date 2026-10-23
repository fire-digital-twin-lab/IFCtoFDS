"""A Fraction oracle checks exact predicates independently of integer scaling."""

from fractions import Fraction
import random

import pytest

from ifc_to_fds.modules.geometry.algorithms.exact_predicates import Binary64Predicates


def vector(point):
    return tuple(Fraction(float(x)) for x in point)


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def oracle_plane(triangle, point):
    origin, second, third = map(vector, triangle)
    value = dot(
        sub(second, origin), cross(sub(third, origin), sub(vector(point), origin))
    )
    return (value > 0) - (value < 0)


def oracle_segment(start, end, triangle):
    p0, p1, p2 = map(vector, triangle)
    origin = vector(start)
    direction = sub(vector(end), origin)
    edge1, edge2, offset = sub(p1, p0), sub(p2, p0), sub(origin, p0)
    h, q = cross(direction, edge2), cross(offset, edge1)
    determinant = dot(edge1, h)
    if not determinant:
        return False
    u, v, t = (
        dot(offset, h) / determinant,
        dot(direction, q) / determinant,
        dot(edge2, q) / determinant,
    )
    return 0 < t < 1 and u >= 0 and v >= 0 and u + v <= 1


@pytest.mark.parametrize("scale", [2**-500, 2**-42, 1.0, 2**40, 2**500])
def test_dyadic_predicates_match_fraction_oracle(scale):
    rng = random.Random(1729)
    for _ in range(60):
        points = [[rng.uniform(-3, 3) * scale for _ in range(3)] for _ in range(5)]
        predicate = Binary64Predicates(points)
        assert predicate.plane_side(points[:3], points[3]) == oracle_plane(
            points[:3], points[3]
        )
        assert predicate.segment_hit(
            points[3], points[4], points[:3]
        ) == oracle_segment(points[3], points[4], points[:3])


@pytest.mark.parametrize(
    "start,end,hit",
    [
        ([0.25, 0.25, -1], [0.25, 0.25, 1], True),
        ([0, 0, -1], [0, 0, 1], True),
        ([0.25, 0.25, 0], [0.25, 0.25, 1], False),
        ([0.25, 0.25, -1], [0.25, 0.25, 0], False),
        ([0.25, 0.25, 2**-1074], [0.25, 0.25, 2**-1073], False),
        ([0.25, 0.25, -(2**-1074)], [0.25, 0.25, 2**-1074], True),
        ([0.25, 0.25, 0], [0.5, 0.25, 0], False),
    ],
)
def test_segment_boundary_and_subnormal_coordinates(start, end, hit):
    triangle = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
    predicate = Binary64Predicates([*triangle, start, end])
    assert predicate.segment_hit(start, end, triangle) is hit
    assert oracle_segment(start, end, triangle) is hit
