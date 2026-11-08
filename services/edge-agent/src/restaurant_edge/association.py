"""Deterministic original-image geometry; no identity or staff classification."""

import math
from dataclasses import dataclass


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def on_segment(p, a, b):
    return abs(cross(a, b, p)) < 1e-9 and all(
        min(a[i], b[i]) - 1e-9 <= p[i] <= max(a[i], b[i]) + 1e-9 for i in (0, 1))


def inside(point, polygon):
    result = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if on_segment(point, a, b):
            return True
        if (a[1] > point[1]) != (b[1] > point[1]) and point[0] < (
                (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]) + a[0]):
            result = not result
    return result


def valid_polygon(points):
    if not 3 <= len(points) <= 64 or len(set(points)) != len(points):
        return False
    if any(len(p) != 2 or any(not math.isfinite(v) or not 0 <= v <= 1 for v in p) for p in points):
        return False
    edges = list(zip(points, points[1:] + points[:1]))
    if abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in edges)) < 1e-8:
        return False
    for i, (a, b) in enumerate(edges):
        for j, (c, d) in enumerate(edges):
            if j <= i or j == i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            if (cross(a, b, c) * cross(a, b, d) <= 0 and cross(c, d, a) * cross(c, d, b) <= 0
                and all(max(min(a[k], b[k]), min(c[k], d[k])) <=
                        min(max(a[k], b[k]), max(c[k], d[k])) for k in (0, 1))):
                return False
    return True


def boundary_distance(point, polygon):
    distances = []
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        t = max(0, min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (dx * dx + dy * dy)))
        distances.append(math.hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy))
    return min(distances)


def box_overlap(box, polygon):
    """Clipped area relative to the smaller shape; supports concave polygons."""
    points = list(polygon)
    for axis, value, lower in [(0, box[0], True), (0, box[2], False),
                               (1, box[1], True), (1, box[3], False)]:
        output = []
        for a, b in zip(points, points[1:] + points[:1]):
            a_in = a[axis] >= value if lower else a[axis] <= value
            b_in = b[axis] >= value if lower else b[axis] <= value
            if a_in:
                output.append(a)
            if a_in != b_in:
                t = (value - a[axis]) / (b[axis] - a[axis])
                output.append(tuple(a[k] + t * (b[k] - a[k]) for k in (0, 1)))
        points = output
    def area(shape):
        return abs(sum(a[0] * b[1] - a[1] * b[0] for a, b in zip(shape, shape[1:] + shape[:1]))) / 2
    denominator = min((box[2] - box[0]) * (box[3] - box[1]), area(polygon))
    return area(points) / denominator if denominator > 0 else 0


@dataclass(frozen=True)
class Observation:
    kind: str  # POSITIVE, VACANT or UNCERTAIN; not an operational command.
    count: int | None
    score: float | None
    quality: str
    reason: str
    association_quality: float | None = None


def associate(people, config, occupied=()):
    """Shared/near boundaries abstain. Empty output needs reviewed visibility."""
    regions = config.regions
    counts = {str(r.table_id): [] for r in regions}
    uncertain = set()
    for person in people:
        x1, y1, x2, y2 = person.box
        hits, near = [], []
        for region in regions:
            key = str(region.table_id)
            anchor = ((x1 + x2) / 2, y2 if region.anchor == 'feet' else y1 + .55 * (y2 - y1))
            if any(inside(anchor, p) for p in region.exclusions):
                if inside(anchor, region.seating) or box_overlap(person.box, region.seating) > .05:
                    uncertain.add(key)
                continue
            if inside(anchor, region.seating):
                hits.append(key)
                if boundary_distance(anchor, region.seating) <= config.settings.border_margin:
                    near.append(key)
            elif (boundary_distance(anchor, region.seating) <= config.settings.border_margin
                  or box_overlap(person.box, region.seating) > .05):
                near.append(key)
        if len(hits) != 1 or near:
            uncertain.update(hits + near)
            continue
        key = hits[0]
        threshold = config.settings.retention_score if key in occupied else config.settings.entry_score
        if person.score < threshold:
            uncertain.add(key)
        else:
            counts[key].append(person.score)
    result = {}
    for region in regions:
        key = str(region.table_id)
        scores = counts[key]
        if not region.visibility_reviewed:
            result[key] = Observation('UNCERTAIN', None, None, 'LOW', 'VIEW_NOT_REVIEWED')
        elif key in uncertain:
            result[key] = Observation('UNCERTAIN', None, None, 'LOW', 'AMBIGUOUS_PERSON')
        elif scores:
            result[key] = Observation('POSITIVE', len(scores), max(scores), 'HIGH', 'SEATING_EVIDENCE', 1.0)
        else:
            result[key] = Observation('VACANT', 0, None, 'MEDIUM', 'REVIEWED_VIEW_NO_PERSON')
    return result
