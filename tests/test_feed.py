"""The live feed: the camera is read on its own thread and every frame goes to
the stream; detection always takes the newest frame, skipping stale ones;
the stream sends each new frame once. Real engine, stubbed models."""
import threading
import time
import types

import numpy as np
import pytest

from tests.test_identity import load_real_engine


@pytest.fixture
def engine(monkeypatch):
    eng = load_real_engine(monkeypatch)
    eng.add_event = lambda *a, **k: None
    eng.announce_identifying = lambda tid: None
    eng.submit_recognition = lambda tid: None
    return eng


class FakeCamera:
    """Frames whose pixels hold their number; ends after `count` frames."""

    def __init__(self, count, delay=0.0):
        self.count, self.delay, self.sent = count, delay, 0

    def isOpened(self):
        return True

    def read(self):
        if self.sent >= self.count:
            return False, None
        time.sleep(self.delay)
        self.sent += 1
        return True, np.full((240, 320, 3), self.sent, dtype=np.uint8)

    def release(self):
        pass


def detection_result(boxes, ids):
    tensor = lambda values: types.SimpleNamespace(cpu=lambda: types.SimpleNamespace(numpy=lambda: np.array(values)))
    return [types.SimpleNamespace(boxes=types.SimpleNamespace(xyxy=tensor(boxes), id=tensor(ids) if ids else None))]


def test_the_stream_sends_each_new_frame_once(engine):
    assert engine.wait_for_frame(0, timeout=0.01) == (0, None)           # nothing yet: no resend, no blocking forever
    engine.update_latest_frame(np.zeros((8, 8, 3), dtype=np.uint8))
    seq, jpeg = engine.wait_for_frame(0, timeout=0.01)
    assert seq == 1 and jpeg.startswith(b"\xff\xd8")
    assert engine.wait_for_frame(seq, timeout=0.01) == (seq, None)       # same frame is not sent again


def test_detection_skips_stale_frames(engine):
    for n in range(1, 6):                                                # 5 frames arrive during one detection
        with engine.camera_frame_ready:
            engine.camera_frame, engine.camera_frame_seq = n, n
    assert engine.next_camera_frame(0) == (5, 5)                        # only the newest is processed
    with engine.camera_frame_ready:
        engine.camera_stopped = True
    assert engine.next_camera_frame(5) == (5, None)                     # camera gone: detection loop ends


def test_capture_and_detection_run_at_their_own_rates(engine, monkeypatch):
    """A slow detector no longer slows the picture: every camera frame is
    streamed, detection sees fewer (the newest each time), and the boxes are
    drawn from the latest detection in frame coordinates."""
    camera = FakeCamera(count=30, delay=0.005)
    monkeypatch.setattr(engine.cv2, "VideoCapture", lambda source: camera)
    streamed, detected = [], []
    real_update = engine.update_latest_frame
    monkeypatch.setattr(engine, "update_latest_frame", lambda frame: (streamed.append(frame.copy()), real_update(frame)))

    def slow_track(frame, **kwargs):
        detected.append((int(frame[0, 0, 0]), kwargs))
        time.sleep(0.03)
        return detection_result([[200.0, 100.0, 260.0, 200.0]], [1])

    engine.person_model = types.SimpleNamespace(track=slow_track)
    loop = threading.Thread(target=engine.run_tracking_loop)
    loop.start()
    loop.join(timeout=10)
    assert not loop.is_alive()

    assert len(streamed) == 30                                          # every camera frame reached the stream
    numbers = [n for n, _ in detected]
    assert 1 < len(numbers) < 30 and numbers == sorted(set(numbers))    # detection skipped frames, never went back
    assert detected[0][1]["imgsz"] == engine.DETECTION_IMAGE_SIZE and detected[0][1]["persist"] is True
    last = streamed[-1]
    assert (last[150, 199:202] != last[150, 20]).any()                  # box edge drawn on the streamed frame
    assert (last[:, 20] == last[0, 20]).all()                           # ...only where the box is
    assert 1 in engine.known_track_ids                                  # the tracked person was observed


def test_stream_generator_uses_new_frames_only(monkeypatch):
    from backend.api import auth, main

    frames = iter([(1, b"A"), (1, None), (2, b"B")])
    monkeypatch.setattr(main.engine, "wait_for_frame", lambda seq, timeout=1.0: next(frames))
    monkeypatch.setattr(auth, "get_session", lambda token: True)
    stream = main.mjpeg_generator("t")
    assert next(stream).endswith(b"A\r\n")
    assert next(stream).endswith(b"B\r\n")                              # the timeout (None) sent nothing
