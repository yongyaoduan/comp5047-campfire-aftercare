"""Drain the USB camera continuously; inference consumes only the newest frame."""
from __future__ import annotations

import threading
import time


class LatestCamera:
    def __init__(self, capture):
        self.capture = capture
        self.condition = threading.Condition()
        self.stopping = threading.Event()
        self.sequence = self.consumed = 0
        self.latest = None
        self.error = None
        self.thread = threading.Thread(target=self._capture, name="usb-camera", daemon=True)
        self.thread.start()

    def _capture(self):
        try:
            while not self.stopping.is_set():
                ok, frame = self.capture.read()
                captured_at = time.monotonic()
                if not ok:
                    raise RuntimeError("USB camera stopped returning frames")
                with self.condition:
                    self.latest = (frame, captured_at)
                    self.sequence += 1
                    self.condition.notify_all()
        except Exception as exc:
            with self.condition:
                self.error = exc
                self.condition.notify_all()
        finally:
            self.capture.release()

    def read(self, timeout=3.):
        with self.condition:
            ready = self.condition.wait_for(
                lambda: self.sequence > self.consumed or self.error or self.stopping.is_set(), timeout)
            if self.error:
                raise RuntimeError(str(self.error)) from self.error
            if not ready or self.stopping.is_set():
                raise RuntimeError("USB camera has no fresh frame")
            self.consumed = self.sequence
            frame, captured_at = self.latest
            return frame, captured_at

    def close(self):
        self.stopping.set()
        with self.condition:
            self.condition.notify_all()
        self.thread.join(timeout=3.)
