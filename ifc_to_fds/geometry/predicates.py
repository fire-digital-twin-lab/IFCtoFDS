"""Exact triangle predicates over finite binary64 vertex coordinates."""


def _subtract(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


class ExactTrianglePredicates:
    def __init__(self, vertices, faces):
        # A binary64 denominator is a power of two. One common denominator
        # per axis gives an exact positive diagonal transform. Plane signs
        # and segment/triangle barycentric ratios are invariant under it.
        ratios = [
            tuple(float(value).as_integer_ratio() for value in vertex)
            for vertex in vertices
        ]
        denominators = [max(den for _, den in axis) for axis in zip(*ratios)]
        self.vertices = [
            tuple(num * (scale // den) for (num, den), scale in zip(vertex, denominators))
            for vertex in ratios
        ]
        self.frames = []
        for i, j, k in faces:
            origin = self.vertices[i]
            edge_a = _subtract(self.vertices[j], origin)
            edge_b = _subtract(self.vertices[k], origin)
            self.frames.append((origin, edge_a, edge_b, _cross(edge_a, edge_b)))

    def plane_side(self, face, vertex):
        origin, _, _, normal = self.frames[face]
        value = _dot(normal, _subtract(self.vertices[vertex], origin))
        return (value > 0) - (value < 0)

    def segment_hit(self, start, end, face):
        """Return 0 for none, 1 for an endpoint, 2 for a side and 3 for interior."""
        origin, edge_a, edge_b, _ = self.frames[face]
        first = self.vertices[start]
        direction = _subtract(self.vertices[end], first)
        h = _cross(direction, edge_b)
        determinant = _dot(edge_a, h)
        if determinant == 0:
            return 0
        offset = _subtract(first, origin)
        q = _cross(offset, edge_a)
        u, v, t = _dot(offset, h), _dot(direction, q), _dot(edge_b, q)
        if determinant < 0:
            determinant, u, v, t = -determinant, -u, -v, -t
        margin = min(u, v, determinant - u - v)
        if margin < 0 or not 0 <= t <= determinant:
            return 0
        if t in (0, determinant):
            return 1
        return 2 + int(margin > 0)
