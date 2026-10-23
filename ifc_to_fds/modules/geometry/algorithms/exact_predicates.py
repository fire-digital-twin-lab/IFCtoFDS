"""Exact predicates over binary64 coordinates using a common dyadic scale.

Every finite binary64 value is an integer divided by a power of two. Scaling
all coordinates by the same power preserves determinant signs and segment
ratios without Fraction normalization or division. No geometric tolerance is
introduced. The integer table is built when a general triangle proof needs it.
"""


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


class Binary64Predicates:
    def __init__(self, vertices):
        self.vertices = vertices
        self._coordinates = None

    def vector(self, point):
        if self._coordinates is None:
            ratios = {
                float(x): float(x).as_integer_ratio() for p in self.vertices for x in p
            }
            exponent = max((d.bit_length() - 1 for _, d in ratios.values()), default=0)
            self._coordinates = {
                x: n << (exponent - (d.bit_length() - 1))
                for x, (n, d) in ratios.items()
            }
        return tuple(self._coordinates[float(x)] for x in point)

    def plane_side(self, triangle, point):
        determinant = self.side_prepared(
            self.prepare_triangle(triangle), self.vector(point)
        )
        return (determinant > 0) - (determinant < 0)

    def prepare_triangle(self, triangle):
        p0, p1, p2 = map(self.vector, triangle)
        edge1, edge2 = _sub(p1, p0), _sub(p2, p0)
        return p0, edge1, edge2, _cross(edge1, edge2)

    @staticmethod
    def side_prepared(triangle, point):
        p0, _, _, normal = triangle
        return _dot(normal, _sub(point, p0))

    def segment_hit(self, start, end, triangle):
        return self.segment_prepared(
            self.vector(start), self.vector(end), self.prepare_triangle(triangle)
        )

    @staticmethod
    def segment_prepared(start, end, triangle):
        p0, edge1, edge2, _ = triangle
        direction, offset = _sub(end, start), _sub(start, p0)
        h, q = _cross(direction, edge2), _cross(offset, edge1)
        determinant = _dot(edge1, h)
        if not determinant:
            return False
        u, v, t = _dot(offset, h), _dot(direction, q), _dot(edge2, q)
        if determinant < 0:
            determinant, u, v, t = -determinant, -u, -v, -t
        # Strict segment endpoints; triangle edges remain included.
        return 0 < t < determinant and u >= 0 and v >= 0 and u + v <= determinant
