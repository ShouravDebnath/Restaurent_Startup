"""Normalized detector contract; scores are not occupancy probabilities."""

import math
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Person:
    box: tuple[float, float, float, float]
    score: float

    def __post_init__(self):
        x1, y1, x2, y2 = self.box
        if not all(math.isfinite(v) and 0 <= v <= 1 for v in (*self.box, self.score)):
            raise ValueError("Invalid normalized person result")
        if x1 >= x2 or y1 >= y2:
            raise ValueError("Invalid person box area")


class Detector(Protocol):
    def detect(self, bgr) -> tuple[Person, ...]: ...
    def close(self) -> None: ...
