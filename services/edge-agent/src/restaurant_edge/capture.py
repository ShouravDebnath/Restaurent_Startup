"""One supervised reader with a single latest-frame mailbox and bounded shutdown."""

import contextlib
import multiprocessing
import os
import queue
import threading
import time
from uuid import uuid4

from restaurant_edge.process_guard import ReaderJob, watch_parent


def silence_native_output(kind):
    os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
    os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"
    os.environ["OPENCV_FFMPEG_DEBUG"] = "0"
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
        "rtsp_transport;tcp|protocol_whitelist;rtsp,tcp" if kind == "rtsp"
        else "protocol_whitelist;file")
    # Only in the reader child, before importing native video libraries.
    with open(os.devnull, "w") as sink:
        os.dup2(sink.fileno(), 1)
        os.dup2(sink.fileno(), 2)


def reader_worker(definition, mailbox, cancel, fps, loop, factory=None):
    silence_native_output(definition.kind)
    watch_parent()
    import cv2

    from restaurant_edge.video_sources import OpenCVSource, SourceFailure
    source = (factory or OpenCVSource)(definition)
    generation = uuid4().hex

    def publish(message):
        try:
            mailbox.put_nowait(message)
        except queue.Full:
            with contextlib.suppress(queue.Empty):
                mailbox.get_nowait()
            with contextlib.suppress(queue.Full):
                mailbox.put_nowait(message)
    try:
        source.open()
        last = -1e10
        while not cancel.is_set():
            frame = source.read()
            if frame is None:
                if loop and definition.kind == "mp4":
                    source.close()
                    source = (factory or OpenCVSource)(definition)
                    source.open()
                    generation = uuid4().hex
                    continue
                publish({"status": "FILE_ENDED", "reason": "NORMAL_COMPLETION"})
                return
            if frame.received_monotonic - last < 1 / fps:
                continue
            last = frame.received_monotonic
            image = frame.pixels
            height, width = image.shape[:2]
            if width > 960:
                image = cv2.resize(image, (960, max(1, round(height * 960 / width))))
            success, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if not success or len(encoded) > 2_000_000:
                raise SourceFailure("PREVIEW_ENCODING_FAILED")
            publish({"status": "ONLINE", "reason": None, "received_at": frame.received_at.isoformat(),
                     "received_monotonic": frame.received_monotonic, "sequence": frame.sequence,
                     "generation": generation, "media_seconds": frame.media_seconds,
                     "width": width, "height": height, "jpeg": encoded.tobytes()})
    except SourceFailure as error:
        # SourceFailure values are fixed reason codes, not decoder/URL messages.
        publish({"status": "ERROR", "reason": str(error)})
    except Exception:  # noqa: BLE001 - native worker boundary must never serialize private decoder errors
        publish({"status": "ERROR", "reason": "READER_FAILED"})
    finally:
        with contextlib.suppress(Exception):
            source.close()
        mailbox.close()
        mailbox.join_thread()


class Capture:
    def __init__(self, source, fps=2, loop=False, *, worker=reader_worker, watchdog=5, retries=3):
        if not 0.5 <= fps <= 10 or (loop and source.kind != "mp4"):
            raise ValueError("Invalid sampling/replay settings")
        self.source, self.fps, self.loop = source, fps, loop
        self.worker, self.watchdog, self.retries = worker, watchdog, retries
        self.lock = threading.RLock()
        self.stopped = threading.Event()
        self.process = self.cancel = self.mailbox = None
        self.job = None
        self.monitor = None
        self.latest = None
        self.metadata = {"status": "NOT_CONFIGURED", "reason": None, "synthetic": source.synthetic,
                         "kind": source.kind, "loop": loop, "sampling_fps": fps}
        self.last_progress = 0.0
        self.attempts = 0
        self.next_attempt = 0.0

    def start(self):
        with self.lock:
            self._spawn()
            self.monitor = threading.Thread(target=self._watch, daemon=True, name="edge-reader-watchdog")
            self.monitor.start()

    def _spawn(self):
        ctx = multiprocessing.get_context("spawn")
        self.mailbox = ctx.Queue(maxsize=1)
        self.cancel = ctx.Event()
        self.process = ctx.Process(target=self.worker,
            args=(self.source, self.mailbox, self.cancel, self.fps, self.loop), daemon=True)
        self.last_progress = time.monotonic()
        self.metadata.update(status="CONNECTING", reason=None)
        try:
            self.job = ReaderJob()
            self.process.start()
            self.job.attach(self.process.pid)
        except (RuntimeError, OSError):
            if self.process.pid is None:
                self.process = None
            self._dispose()
            self.metadata.update(status='ERROR',reason='READER_START_FAILED')

    def _dispose(self):
        if self.cancel:
            self.cancel.set()
        if self.process:
            self.process.join(timeout=0.25)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=1)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=1)
            self.process.close()
            self.process = None
        if self.mailbox:
            self.mailbox.cancel_join_thread()
            self.mailbox.close()
            self.mailbox = None
        if self.job:
            self.job.close()
            self.job = None
        self.latest = None

    def _watch(self):
        while not self.stopped.wait(0.05):
            with self.lock:
                if self.mailbox:
                    try:
                        item = self.mailbox.get_nowait()
                    except (queue.Empty, EOFError, OSError):
                        item = None
                    if item:
                        if item["status"] == "ONLINE":
                            self.latest = item.pop("jpeg")
                            self.last_progress = item["received_monotonic"]
                            self.metadata.update(item)
                        else:
                            self.metadata.update(item)
                            self._dispose()
                if self.process and time.monotonic() - self.last_progress > self.watchdog:
                    self.metadata.update(status="STALE", reason="NO_NEW_FRAMES")
                    self._dispose()
                if self.process and not self.process.is_alive() and time.monotonic() - self.last_progress > 0.5:
                    # Allow the final queued EOF/error to arrive before declaring a crash.
                    self.metadata.update(status="ERROR", reason="READER_EXITED")
                    self._dispose()
                if self.process is None and self.metadata["status"] not in {"FILE_ENDED", "STOPPED"}:
                    retryable = self.metadata.get("reason") not in {
                        "CAMERA_AUTHORIZATION_FAILED", "CAMERA_CREDENTIAL_UNAVAILABLE",
                        "DESTINATION_REJECTED", "UNSUPPORTED_DIMENSIONS"}
                    if self.source.kind != "mp4" and retryable and (self.next_attempt or self.attempts < self.retries):
                        if not self.next_attempt:
                            self.attempts += 1
                            self.next_attempt = time.monotonic() + min(30, 2 ** (self.attempts - 1))
                            self.metadata.update(status="RECONNECTING")
                        if time.monotonic() >= self.next_attempt:
                            self.next_attempt = 0
                            self._spawn()
                    elif self.metadata["status"] != "STALE":
                        self.metadata.update(status="ERROR")

    def health(self):
        with self.lock:
            result = dict(self.metadata)
            result.pop("received_monotonic", None)
            result["frame_age_seconds"] = (round(time.monotonic() - self.last_progress, 3)
                                            if self.metadata.get("received_at") else None)
            result["reconnect_attempts"] = self.attempts
            return result

    def frame(self):
        with self.lock:
            if self.metadata["status"] != "ONLINE" or time.monotonic() - self.last_progress > self.watchdog:
                return None
            return self.latest

    def stop(self):
        self.stopped.set()
        if self.monitor and self.monitor is not threading.current_thread():
            self.monitor.join(timeout=4)
        with self.lock:
            self._dispose()
            self.metadata.update(status="STOPPED", reason=None)
