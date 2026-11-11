"""Actual generated MP4s with injected elapsed time; original timing tests stay intact."""

from uuid import uuid4

import pytest

from restaurant_edge.source_config import SourceDefinition
from restaurant_edge.video_sources import OpenCVSource, synthetic_mp4


class Clock:
    def __init__(self):
        self.now = 100.0
        self.waits = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += seconds


@pytest.mark.parametrize('fps', [5, 20])
def test_delayed_first_frame_does_not_compress_following_gap(tmp_path, fps):
    path = synthetic_mp4(tmp_path / 'delayed.mp4', seconds=1, fps=fps)
    definition = SourceDefinition(reference='synthetic', organization_id=uuid4(),
        location_id=uuid4(), camera_id=uuid4(), kind='mp4', authorized=True,
        synthetic=True, file=str(path))
    clock = Clock()
    source = OpenCVSource(definition, clock=clock, sleep=clock.sleep)
    try:
        source.open()
        clock.now += .070
        first = source.read()
        second = source.read()
        assert second.received_monotonic - first.received_monotonic == pytest.approx(1 / fps)
        assert (first.sequence, second.sequence) == (1, 2)
        assert second.media_seconds == pytest.approx(1 / fps)
        # A later decoder/scheduler stall must not cause compressed catch-up either.
        clock.now += .8
        third = source.read()
        fourth = source.read()
        assert fourth.received_monotonic - third.received_monotonic == pytest.approx(1 / fps)
    finally:
        source.close()


def test_reopening_mp4_starts_a_fresh_delivery_schedule(tmp_path):
    path = synthetic_mp4(tmp_path / 'reopen.mp4', seconds=1, fps=5)
    definition = SourceDefinition(reference='synthetic', organization_id=uuid4(),
        location_id=uuid4(), camera_id=uuid4(), kind='mp4', authorized=True,
        synthetic=True, file=str(path))
    clock = Clock()
    source = OpenCVSource(definition, clock=clock, sleep=clock.sleep)
    try:
        source.open()
        source.read()
        source.read()
        source.close()
        clock.now += 1
        source.open()
        assert source.read().sequence == 1
        assert clock.waits == pytest.approx([.2])
    finally:
        source.close()
