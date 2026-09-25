"""Tracks that aren't identified at first are re-checked; each visit gets
exactly one ENTRY (named, Unknown after the re-checks, or when the person
leaves); swallowed recognition errors are logged, rate-limited.

Uses the real engine module with the camera/model libraries stubbed and
controllable "good face" / "no face" samples."""
import numpy as np
import pytest

from tests.test_identity import load_real_engine

GOOD, BLURRY, NO_FACE = "good", "blurry", "no-face"


class Sync:
    """Runs submitted recognition immediately (instead of a thread pool)."""

    def submit(self, fn, *args):
        fn(*args)


@pytest.fixture
def engine(monkeypatch):
    eng = load_real_engine(monkeypatch)
    eng.VOTE_SAMPLE_INTERVAL = 0
    eng.recognition_executor = Sync()
    monkeypatch.setattr(eng.time, "time", lambda: 100.0)             # the re-check schedule uses the clock
    eng.lookup_person = lambda folder: {"person_type": "student", "person_id": 1, "label": "Aziz Ahmad (CS-001)"}
    eng.events = []
    eng.add_event = lambda kind, tid, label, person=None, confidence=None: eng.events.append((kind, tid, label))
    eng.announced = []
    eng.announce_identifying = lambda tid: eng.announced.append(tid)
    # A "crop" is just a marker: good -> clear match, blurry -> face but below
    # the threshold, no-face -> the face detector finds nothing.
    eng.get_tight_face_crop = lambda crop: None if crop == NO_FACE else crop
    eng.match_single_frame = lambda crop: ("AzizAhmad", 0.81) if crop == GOOD else (None, 0.52)
    return eng


def entries(eng):
    return [e for e in eng.events if e[0] == "ENTRY"]


def test_identified_on_the_first_round_writes_the_entry_immediately(engine):
    info = engine.observe_track(1, GOOD, now=100.0)
    assert info["status"] == "done"
    assert entries(engine) == [("ENTRY", 1, "Aziz Ahmad (CS-001)")]
    assert engine.announced == [1]                                   # dashboard showed "Identifying..." first


def test_a_bad_start_is_rechecked_and_identified_later(engine):
    """The live bug: turning away during the first seconds locked the track as Unknown."""
    engine.observe_track(1, NO_FACE, now=100.0)                      # walking in, face not visible
    assert entries(engine) == []                                     # no premature "Unknown" ENTRY
    info = engine.known_track_ids[1]
    assert info["label"] == engine.IDENTIFYING and info["status"] == "identifying"
    assert info["next_check"] == 100.0 + engine.RECHECK_INTERVAL_SECONDS

    engine.observe_track(1, BLURRY, now=101.0)                       # before the re-check is due: nothing
    assert info["attempts"] == 1
    engine.observe_track(1, GOOD, now=info["next_check"] + 0.1)      # now facing the camera
    assert info["status"] == "done"
    assert entries(engine) == [("ENTRY", 1, "Aziz Ahmad (CS-001)")]  # exactly one, named


def test_never_identified_becomes_unknown_after_the_rechecks(engine):
    now = 100.0
    engine.observe_track(1, BLURRY, now=now)
    for _ in range(engine.MAX_RECHECKS + 3):                         # keeps being seen, never matches
        now = engine.known_track_ids[1]["next_check"] + 0.1
        engine.observe_track(1, BLURRY, now=now)
    info = engine.known_track_ids[1]
    assert info["attempts"] == 1 + engine.MAX_RECHECKS              # first round + 5 re-checks, then stop
    assert info["label"] == "Unknown" and info["status"] == "done"
    assert entries(engine) == [("ENTRY", 1, "Unknown")]


def test_leaving_before_identification_still_records_the_visit(engine):
    engine.observe_track(1, NO_FACE, now=100.0)
    gone = engine.end_tracks(set(), now=100.0 + engine.EXIT_TIMEOUT_SECONDS + 1)
    assert gone == [1]
    assert engine.events == [("ENTRY", 1, "Unknown"), ("EXIT", 1, "Unknown")]


def test_a_vote_finishing_after_the_person_left_adds_nothing(engine):
    engine.observe_track(1, NO_FACE, now=100.0)
    engine.pending_samples[1] = GOOD
    engine.known_track_ids[1]["status"] = "checking"
    engine.end_tracks(set(), now=200.0)                              # left while a vote was running
    engine.run_voting_recognition(1)                                 # ...which then finishes
    assert entries(engine) == [("ENTRY", 1, "Unknown")]              # still exactly one ENTRY


def test_an_identified_track_is_not_rechecked(engine):
    engine.observe_track(1, GOOD, now=100.0)
    engine.match_single_frame = lambda crop: pytest.fail("identified tracks must not be re-checked")
    for t in range(101, 130, 3):
        engine.observe_track(1, GOOD, now=float(t))
    assert entries(engine) == [("ENTRY", 1, "Aziz Ahmad (CS-001)")]


def test_one_agreeing_vote_is_not_enough(engine):
    samples = iter([GOOD, BLURRY, BLURRY])
    engine.get_tight_face_crop = lambda crop: next(samples, None)
    engine.observe_track(1, GOOD, now=100.0)
    assert entries(engine) == [] and engine.known_track_ids[1]["status"] == "identifying"


def test_swallowed_errors_are_logged_but_rate_limited(monkeypatch, capsys):
    eng = load_real_engine(monkeypatch)

    def broken(*args, **kwargs):
        raise RuntimeError("model exploded")

    eng.face_model = broken
    clock = [1000.0]
    monkeypatch.setattr(eng.time, "time", lambda: clock[0])
    for _ in range(5):
        assert eng.get_tight_face_crop(object.__new__(type("Crop", (), {"size": 1}))) is None
    first = capsys.readouterr().out
    assert first.count("face detection failed: RuntimeError: model exploded") == 1   # not 5 times
    clock[0] += eng.ERROR_LOG_INTERVAL + 1
    eng.get_tight_face_crop(object.__new__(type("Crop", (), {"size": 1})))
    assert "(4 more since the last report)" in capsys.readouterr().out


# ---- real models: re-checking a stranger many times must never name them ----

def test_rechecks_never_match_a_stranger(monkeypatch):
    """1 + MAX_RECHECKS vote rounds per stranger photo, through the real
    YOLO face crop and Facenet512 references, with the photo varied each round
    (webcam size, JPEG, brightness, mirror) the way a live feed varies. More
    tries must not turn into a false acceptance. Skipped where the vision
    stack, the reference photos or the stranger photos aren't available (CI)."""
    pytest.importorskip("deepface")
    pytest.importorskip("ultralytics")
    cv2 = pytest.importorskip("cv2")
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    strangers = sorted((root / "data" / "test_images" / "unknown_person").glob("*.jp*g"))
    if not strangers or not any((root / "data" / "known_faces").glob("*/*.jp*g")):
        pytest.skip("reference or stranger photos not present")
    monkeypatch.chdir(root)
    spec = importlib.util.spec_from_file_location("live_engine", root / "backend" / "tracking" / "engine.py")
    eng = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(eng)
    eng.build_reference_embeddings()
    assert eng.reference_embeddings
    eng.VOTE_SAMPLE_INTERVAL = 0
    eng.recognition_executor = Sync()
    eng.lookup_person = lambda folder: {"person_type": "student", "person_id": 1, "label": folder}
    events = []
    eng.add_event = lambda kind, tid, label, person=None, confidence=None: events.append((kind, tid, label))
    eng.announce_identifying = lambda tid: None

    def variants(img):
        for i in range(1 + eng.MAX_RECHECKS):
            v = cv2.resize(img, None, fx=640 / max(img.shape[:2]), fy=640 / max(img.shape[:2]))
            if i % 2:
                v = cv2.flip(v, 1)
            v = cv2.convertScaleAbs(v, alpha=1.0, beta=(-30, 0, 30)[i % 3])
            yield cv2.imdecode(cv2.imencode(".jpg", v, [cv2.IMWRITE_JPEG_QUALITY, 70])[1], cv2.IMREAD_COLOR)

    for tid, path in enumerate(strangers, start=1):
        img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
        for frame in variants(img):
            boxes = eng.person_model(frame, classes=[0], verbose=False)[0].boxes.xyxy.cpu().numpy()
            x1, y1, x2, y2 = map(int, max(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))) if len(boxes) else (0, 0, frame.shape[1], frame.shape[0])
            info = eng.observe_track(tid, frame[max(0, y1):y2, max(0, x1):x2].copy(), now=eng.time.time())
            if info["status"] != "done":
                info["next_check"] = 0                                 # re-check now instead of waiting 3 s
        eng.end_tracks(set(), now=eng.time.time() + eng.EXIT_TIMEOUT_SECONDS + 1)
    assert [e for e in events if e[0] == "ENTRY"] == [("ENTRY", tid, "Unknown") for tid in range(1, len(strangers) + 1)]
