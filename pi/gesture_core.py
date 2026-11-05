"""Pure gesture and command logic shared by the live app and offline tests.

Coordinates are normalized to 0..1, with Y increasing upward (like the Mac app).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import acos, degrees, hypot


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Hand:
    wrist: Point
    middle_mcp: Point
    index_tip: Point
    thumb_tip: Point
    index_mcp: Point | None = None
    index_pip: Point | None = None


@dataclass(frozen=True)
class Pose:
    left_shoulder: Point
    right_shoulder: Point
    left_wrist: Point
    right_wrist: Point


def heart_crop_boxes(pose: Pose) -> tuple[tuple[float, float, float, float],
                                          tuple[float, float, float, float]] | None:
    """Image-space (x0,y0,x1,y1) crops that separate two touching hands.

    Global hand detection often merges a heart into one hand. The pose wrists
    anchor overlapping left/right crops so each hand model sees one hand.
    """
    span = distance(pose.left_shoulder, pose.right_shoulder)
    if span <= .04:
        return None
    wrists = sorted((pose.left_wrist, pose.right_wrist), key=lambda p: p.x)
    left, right = wrists
    gap = right.x - left.x
    shoulder_mid = (pose.left_shoulder.x + pose.right_shoulder.x) / 2
    wrist_mid = (left.x + right.x) / 2
    if not (.25 * span <= gap <= 1.15 * span
            and abs(wrist_mid - shoulder_mid) <= .55 * span
            and abs(left.y - right.y) <= .6 * span):
        return None
    top = min(1 - left.y, 1 - right.y) - .45 * span
    bottom = max(1 - left.y, 1 - right.y) + .32 * span
    raw = ((left.x - .48 * span, top, wrist_mid + .24 * span, bottom),
           (wrist_mid - .24 * span, top, right.x + .48 * span, bottom))
    boxes = tuple(tuple(max(0.0, min(1.0, v)) for v in box) for box in raw)
    if any(x1 - x0 < .05 or y1 - y0 < .05 for x0, y0, x1, y1 in boxes):
        return None
    return boxes


def distance(a: Point, b: Point) -> float:
    return hypot(a.x - b.x, a.y - b.y)


def classify_heart(hands: list[Hand]) -> str | None:
    # A complete heart may belong to one person or two cooperating people.
    # Other people's visible hands must not mask an otherwise valid pair.
    for pair in combinations(hands, 2):
        if _two_hand_heart(*sorted(pair, key=lambda h: h.wrist.x)):
            return "two-hand"
    return None


def crop_candidate_poses(poses: list[Pose], maximum: int = 6) -> list[Pose]:
    """Try each person's hands, then nearby wrists from different people."""
    candidates = [pose for pose in poses if heart_crop_boxes(pose) is not None]
    wrists = [(index, wrist, distance(pose.left_shoulder, pose.right_shoulder))
              for index, pose in enumerate(poses)
              for wrist in (pose.left_wrist, pose.right_wrist)]
    cooperative = []
    for (owner_a, a, span_a), (owner_b, b, span_b) in combinations(wrists, 2):
        if owner_a == owner_b:
            continue
        span = (span_a + span_b) / 2
        gap = abs(a.x - b.x)
        if span <= .04 or not (.25 * span <= gap <= 2.0 * span
                               and abs(a.y - b.y) <= .45 * span):
            continue
        span = max(span, gap / 1.1)
        mid = Point((a.x + b.x) / 2, (a.y + b.y) / 2)
        proxy = Pose(Point(mid.x - span / 2, mid.y), Point(mid.x + span / 2, mid.y), a, b)
        cooperative.append((gap, proxy))
    candidates.extend(pose for _, pose in sorted(cooperative, key=lambda item: item[0]))
    return candidates[:maximum]


def index_bend_angle(hand: Hand) -> float | None:
    """Projected angle at the index PIP joint: a straight index is ~180°."""
    if hand.index_mcp is None or hand.index_pip is None:
        return None
    a, b, c = hand.index_mcp, hand.index_pip, hand.index_tip
    ab, cb = distance(a, b), distance(c, b)
    if ab <= .001 or cb <= .001:
        return None
    cosine = ((a.x - b.x) * (c.x - b.x) + (a.y - b.y) * (c.y - b.y)) / (ab * cb)
    return degrees(acos(max(-1.0, min(1.0, cosine))))


def _two_hand_heart(left: Hand, right: Hand) -> bool:
    # A straight index/thumb diamond shares the same fingertip outline as a
    # heart. Both curved upper lobes must also have a bent index finger.
    angles = (index_bend_angle(left), index_bend_angle(right))
    if any(angle is None or angle > 150 for angle in angles):
        return False
    palm = (distance(left.wrist, left.middle_mcp) + distance(right.wrist, right.middle_mcp)) / 2
    if palm < 0.012 or not 1.5 * palm <= right.wrist.x - left.wrist.x <= 6 * palm:
        return False
    im = Point((left.index_tip.x + right.index_tip.x) / 2, (left.index_tip.y + right.index_tip.y) / 2)
    tm = Point((left.thumb_tip.x + right.thumb_tip.x) / 2, (left.thumb_tip.y + right.thumb_tip.y) / 2)
    wm = (left.wrist.x + right.wrist.x) / 2
    if not (distance(left.index_tip, right.index_tip) <= .6 * palm
            and distance(left.thumb_tip, right.thumb_tip) <= .6 * palm
            and .45 * palm <= im.y - tm.y <= 1.8 * palm
            and abs(im.x - tm.x) <= 1.2 * palm
            and abs(im.x - wm) <= 1.5 * palm
            and abs(tm.x - wm) <= 1.5 * palm):
        return False
    for hand in (left, right):
        opening = distance(hand.index_tip, hand.thumb_tip)
        # A small but open heart is valid too. Preserve fingertip proximity,
        # bent-index checks and two distinct wrists; these reject ordinary
        # hands and the straight-finger diamond independently of hole size.
        if not (.45 * palm <= opening <= 1.8 * palm
                and hand.index_tip.y - hand.thumb_tip.y >= .4 * palm
                and abs(hand.index_tip.x - hand.thumb_tip.x) <= .8 * palm
                and left.wrist.x - .5 * palm <= hand.thumb_tip.x <= right.wrist.x + .5 * palm):
            return False
    return True


class HeartDetector:
    def __init__(self, release_grace: float = .30):
        self.release_grace = release_grace
        self.active: str | None = None
        self.last_match = -100.0

    def observe(self, hands: list[Hand], now: float) -> str | None:
        match = classify_heart(hands)
        if match:
            self.active = match
            self.last_match = now
        elif now - self.last_match >= self.release_grace:
            self.active = None
        return self.active


@dataclass(frozen=True)
class Observation:
    time: float
    person: bool
    pose: Pose | None
    hands: list[Hand]
    completed_at: float | None = None
    people_count: int = 0


@dataclass(frozen=True)
class ControlTiming:
    max_inference_age: float = .65
    max_result_gap: float = .65
    max_frame_age: float = 1.3
    person_result_gap: float = 1.0
    person_inference_age: float | None = None
    person_frame_age: float | None = None
    candidate_inference_age: float | None = None
    confirm_frames: int = 1
    release_grace: float = .30


# At ~1 FPS a good result takes ~1s to compute, and the next one arrives
# ~1s later; a throttled Pi 3B+ (weak supply) measured 1.2-1.3 s per frame.
# Bound both intervals at 2 s; never give an old result an unlimited lease.
# Two consecutive heart frames are still required, and one negative frame
# still revokes the heart at once.
PI3_TIMING = ControlTiming(max_inference_age=2.0, max_result_gap=2.0,
                          max_frame_age=3.0, person_result_gap=2.5,
                          person_inference_age=2.5, person_frame_age=5.0,
                          candidate_inference_age=2.4, confirm_frames=2, release_grace=0.)


class GestureState:
    """CV state only. The BLE sender below applies transport timeouts."""

    def __init__(self, timing: ControlTiming | None = None):
        self.timing = timing or ControlTiming()
        self.heart = HeartDetector(release_grace=self.timing.release_grace)
        self.person = False
        self.heart_kind: str | None = None
        self.last_frame = -100.0
        self.last_result = -100.0
        self.last_person_seen = -100.0
        self.positive_person_frames = 0
        self.positive_heart_frames = 0

    def observe(self, obs: Observation) -> None:
        # Replaying an image/result must not renew its lease or count twice
        # toward confirmation, even if a caller supplies a new completion time.
        if obs.time <= self.last_frame:
            return
        completed = obs.time if obs.completed_at is None else obs.completed_at
        valid = 0 <= completed - obs.time <= self.timing.max_inference_age
        # After a stalled/missing result, require a new confirmation sequence.
        if completed - self.last_result > self.timing.max_result_gap:
            self.positive_heart_frames = 0
            self.heart.active = None
            self.heart_kind = None
        self.last_frame, self.last_result = obs.time, completed
        person_valid = 0 <= completed - obs.time <= (self.timing.person_inference_age
                                                         or self.timing.max_inference_age)
        if person_valid:
            if obs.person:
                self.last_person_seen = obs.time
                self.positive_person_frames += 1
                if self.positive_person_frames >= 2:
                    self.person = True
            else:
                self.positive_person_frames = 0
                if obs.time - self.last_person_seen >= 1.5:
                    self.person = False
        else:
            self.positive_person_frames = 0
        if not valid:
            # A slightly slow positive may seed ONE startup confirmation only.
            # It can never authorize or prolong output. The very next result
            # must pass the normal freshness limit and independently match.
            candidate_limit = self.timing.candidate_inference_age or self.timing.max_inference_age
            candidate = (0 <= completed - obs.time <= candidate_limit
                         and classify_heart(obs.hands) is not None)
            self.positive_heart_frames = 1 if candidate else 0
            self.heart.active = None
            self.heart_kind = None
            return
        was_active = self.heart_kind is not None
        match = classify_heart(obs.hands)
        detected = self.heart.observe(obs.hands, obs.time)
        if match:
            self.positive_heart_frames += 1
            self.heart_kind = detected if self.positive_heart_frames >= self.timing.confirm_frames else None
        else:
            self.positive_heart_frames = 0
            # Pi3 has zero negative-frame grace: a new non-heart observation
            # revokes the lease immediately, even if it arrived very quickly.
            self.heart_kind = detected if was_active else None

    def presence_fresh(self, now: float) -> bool:
        return (0 <= now - self.last_result <= self.timing.person_result_gap
                and 0 <= now - self.last_frame <= (self.timing.person_frame_age or self.timing.max_frame_age)
                and 0 <= self.last_result - self.last_frame <= (self.timing.person_inference_age or self.timing.max_inference_age))

    def camera_stale(self, now: float) -> bool:
        heart_fresh = (0 <= now - self.last_result <= max(1., self.timing.max_result_gap)
                       and 0 <= now - self.last_frame <= self.timing.max_frame_age
                       and 0 <= self.last_result - self.last_frame <= self.timing.max_inference_age)
        # A pump timeout sends HEART OFF. STOP ALL is only for a stale camera;
        # otherwise it would extinguish a valid, independent presence light.
        return not heart_fresh and not self.presence_fresh(now)

    def safe_person(self, now: float) -> bool:
        return self.presence_fresh(now) and self.person

    def safe_heart(self, now: float) -> bool:
        return (0 <= now - self.last_result <= self.timing.max_result_gap
                and 0 <= self.last_result - self.last_frame <= self.timing.max_inference_age
                and 0 <= now - self.last_frame <= self.timing.max_frame_age
                and self.heart_kind is not None)

class CommandPolicy:
    """Choose raw BLE bytes. Presence/heart are refreshed even with no new CV events."""

    def __init__(self, state: GestureState):
        self.state = state
        self.last_person: bool | None = None
        self.last_heart: bool | None = None
        self.last_person_sent = -100.0
        self.last_heart_sent = -100.0
        self.was_camera_stale = True
        self.last_stop_sent = -100.0

    def reset_transport(self) -> None:
        self.last_person = None
        self.last_heart = None
        self.last_person_sent = -100.0
        self.last_heart_sent = -100.0
        self.was_camera_stale = True
        self.last_stop_sent = -100.0

    def commands(self, now: float) -> list[int]:
        commands: list[int] = []
        camera_stale = self.state.camera_stale(now)
        if camera_stale:
            self.last_person = self.last_heart = None
            self.was_camera_stale = True
            if now - self.last_stop_sent >= .3:
                self.last_stop_sent = now
                return [6]
            return []
        if camera_stale and not self.was_camera_stale:
            commands.append(6)
        self.was_camera_stale = camera_stale
        person = self.state.safe_person(now)
        heart = self.state.safe_heart(now)
        if person != self.last_person or (person and now - self.last_person_sent >= 5.0):
            commands.append(1 if person else 0)
            self.last_person, self.last_person_sent = person, now
        if heart != self.last_heart or now - self.last_heart_sent >= (.2 if heart else .3):
            commands.append(4 if heart else 5)
            self.last_heart, self.last_heart_sent = heart, now
        return commands
