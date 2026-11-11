"""Common frame contract and video-only readers. Native reads run in a supervised child."""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime


class SourceFailure(Exception):
    """Safe machine-readable reason; do not attach native errors or private source strings."""


@dataclass(repr=False)
class Frame:
    pixels: object = field(repr=False)
    sequence: int
    received_at: datetime
    received_monotonic: float
    media_seconds: float | None


class VideoSource(ABC):
    @abstractmethod
    def open(self): ...

    @abstractmethod
    def read(self) -> Frame | None: ...

    @abstractmethod
    def close(self): ...


class OpenCVSource(VideoSource):
    def __init__(self, definition, *, clock=None, sleep=None):
        self.definition = definition
        self.clock = clock or time.monotonic
        self.sleep = sleep or time.sleep
        self.capture = None
        self.sequence = 0
        self.started = 0.0
        self.fps = 0.0
        self.frames = 0
        self.gateway = None
        self.last_delivery = None

    def open(self):
        import cv2
        d = self.definition
        # This wheel rejects CAP_PROP_AUDIO_STREAM as an open parameter. Its
        # VideoCapture path is video-only; no microphone/audio reader is created.
        params = [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000]
        target, api = d.file, cv2.CAP_FFMPEG
        if d.kind == "webcam":
            target, api, params = d.device_index, cv2.CAP_MSMF, []
        elif d.kind == "rtsp":
            from restaurant_edge.rtsp_gateway import RestrictedRTSPGateway
            self.gateway = RestrictedRTSPGateway(d)
            target = self.gateway.start()
        cap = cv2.VideoCapture()
        self.capture = cap
        if not cap.open(target, api, params):
            self.close()
            raise SourceFailure("OPEN_FAILED")
        width, height = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        if not (1 <= width <= 4096 and 1 <= height <= 2160):
            self.close()
            raise SourceFailure("UNSUPPORTED_DIMENSIONS")
        self.fps = cap.get(cv2.CAP_PROP_FPS)
        self.frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.sequence = 0
        self.last_delivery = None
        self.started = self.clock()

    def read(self):
        import cv2
        success, image = self.capture.read()
        if not success:
            if self.definition.kind == "mp4" and self.frames > 0 and self.sequence >= self.frames:
                return None
            raise SourceFailure("READ_FAILED")
        if image is None or image.size == 0 or image.shape[0] * image.shape[1] > 4096 * 2160:
            raise SourceFailure("INVALID_FRAME")
        self.sequence += 1
        media = self.capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
        if self.definition.kind == "mp4":
            # A media timestamp is a recording position, never a camera's verified UTC capture time.
            if self.fps <= 0 or self.fps > 240:
                raise SourceFailure("UNSUPPORTED_FRAME_RATE")
            media = (self.sequence - 1) / self.fps if media <= 0 else media
            # Replay never compresses the next gap to catch up after a delayed
            # first decode/read. Live-camera sampling still drops old frames.
            if self.last_delivery is not None:
                deadline = self.last_delivery + 1 / self.fps
                while (delay := deadline - self.clock()) > 0:
                    self.sleep(min(delay, 1.0))
        delivered = self.clock()
        self.last_delivery = delivered
        return Frame(image, self.sequence, datetime.now(UTC), delivered, media if media >= 0 else None)

    def close(self):
        if self.capture is not None:
            self.capture.release()
            self.capture = None
        if self.gateway:
            self.gateway.close()
            self.gateway = None


def synthetic_mp4(path, seconds=90, fps=10):
    """Generate geometric DEMO footage; never open/overwrite an existing output."""
    from pathlib import Path

    import cv2
    import numpy as np
    path = Path(path)
    if path.exists():
        raise ValueError("Refusing to overwrite an existing video")
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (640, 360))
    if not writer.isOpened():
        raise SourceFailure("SYNTHETIC_ENCODER_UNAVAILABLE")
    try:
        for i in range(int(seconds * fps)):
            image = np.full((360, 640, 3), (28, 35, 46), dtype=np.uint8)
            cv2.rectangle(image, (80, 100), (270, 275), (70, 145, 190), -1)
            cv2.rectangle(image, (370, 100), (560, 275), (120, 175, 90), -1)
            cv2.putText(image, "DEMO - synthetic calibration", (40, 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (245, 245, 245), 2)
            cv2.putText(image, f"Frame {i:04d} | No person detection", (70, 325),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (245, 245, 245), 1)
            cv2.circle(image, (i % 600 + 20, 72), 6, (245, 190, 70), -1)
            writer.write(image)
    finally:
        writer.release()
    return path
