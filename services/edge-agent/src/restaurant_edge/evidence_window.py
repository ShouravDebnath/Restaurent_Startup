"""Bounded truthful evidence windows, including during protected manual states.

These summaries describe detector observations, never cleanliness or accuracy.
"""

import itertools
import math


class EvidenceWindows:
    def __init__(self):
        self.samples = {}

    def reset(self, table_id=None):
        if table_id is None:
            self.samples.clear()
        else:
            self.samples.pop(table_id, None)

    def add(self, observations, now, settings):
        for key, observation in observations.items():
            rows = self.samples.get(key, [])
            if (
                observation.kind == "UNCERTAIN"
                or not rows
                or rows[-1][1] != observation.kind
                or now - rows[-1][0] > settings.max_gap_seconds
                or now <= rows[-1][0]
            ):
                rows = []
            if observation.kind == "UNCERTAIN":
                self.samples[key] = []
                continue
            horizon = (
                max(settings.arrival_seconds, settings.departure_seconds)
                + settings.max_gap_seconds
                + settings.coverage_step_seconds
            )
            rows = [r for r in rows if now - r[0] <= horizon]
            rows.append(
                (
                    now,
                    observation.kind,
                    observation.score,
                    observation.association_quality,
                    observation.quality,
                )
            )
            self.samples[key] = rows[-10000:]

    def summary(self, key, region, settings, age):
        rows = self.samples.get(key, [])
        fresh = age is not None and math.isfinite(age) and 0 <= age <= settings.result_max_age
        if not rows or not fresh:
            return {
                "kind": "UNCERTAIN",
                "quality": "LOW",
                "detector_score": None,
                "association_score": None,
                "sample_count": 0,
                "window_seconds": 0.0,
                "covered_seconds": 0.0,
                "max_gap_seconds": 0.0,
                "frame_age_seconds": age
                if age is not None and math.isfinite(age) and 0 <= age <= 3600
                else None,
                "visibility_reviewed": region.visibility_reviewed,
            }
        gaps = [b[0] - a[0] for a, b in itertools.pairwise(rows)]
        positive = rows[-1][1] == "POSITIVE"
        scores = [r[2] for r in rows if r[2] is not None]
        association = [r[3] for r in rows if r[3] is not None]
        return {
            "kind": rows[-1][1],
            "quality": (
                "HIGH"
                if all(r[4] == "HIGH" for r in rows)
                else "MEDIUM"
                if not positive and all(r[4] in {"HIGH", "MEDIUM"} for r in rows)
                else "LOW"
            ),
            "detector_score": min(scores) if positive and scores else None,
            "association_score": min(association) if positive and association else None,
            "sample_count": len(rows),
            "window_seconds": rows[-1][0] - rows[0][0],
            "covered_seconds": sum(min(g, settings.coverage_step_seconds) for g in gaps),
            "max_gap_seconds": max(gaps, default=0.0),
            "frame_age_seconds": age,
            "visibility_reviewed": region.visibility_reviewed,
        }
