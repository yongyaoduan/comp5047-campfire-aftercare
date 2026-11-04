import queue
import time
import unittest
from latest_camera import LatestCamera


class FakeCapture:
    def __init__(self):
        self.frames = queue.Queue()
        self.released = False

    def read(self):
        return self.frames.get(timeout=2)

    def release(self):
        self.released = True


class LatestCameraTests(unittest.TestCase):
    def test_slow_consumer_receives_newest_frame_and_capture_time(self):
        cap = FakeCapture()
        reader = LatestCamera(cap)
        try:
            before = time.monotonic()
            for number in range(3):
                cap.frames.put((True, number))
            with reader.condition:
                self.assertTrue(reader.condition.wait_for(lambda: reader.sequence == 3, 2))
            frame, captured_at = reader.read()
            self.assertEqual(frame, 2)
            self.assertGreaterEqual(captured_at, before)
            self.assertLessEqual(captured_at, time.monotonic())
            with self.assertRaisesRegex(RuntimeError, 'fresh frame'):
                reader.read(timeout=.01)
        finally:
            cap.frames.put((False, None))
            reader.close()
        self.assertTrue(cap.released)

    def test_camera_failure_does_not_replay_last_success(self):
        cap = FakeCapture()
        reader = LatestCamera(cap)
        try:
            cap.frames.put((True, 'old'))
            cap.frames.put((False, None))
            with reader.condition:
                self.assertTrue(reader.condition.wait_for(lambda: reader.error is not None, 2))
            with self.assertRaisesRegex(RuntimeError, 'stopped returning'):
                reader.read()
        finally:
            reader.close()
