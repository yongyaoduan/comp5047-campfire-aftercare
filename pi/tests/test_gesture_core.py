import sys
import unittest
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gesture_core import (CommandPolicy, GestureState, Hand, HeartDetector,
                          Observation, Point, Pose, classify_heart, crop_candidate_poses,
                          heart_crop_boxes)


# Coordinates from the original Mac photo and the new MediaPipe photo check.
TWO_HAND = [
    Hand(Point(.337, .401), Point(.420, .460), Point(.507, .428), Point(.506, .344),
         Point(.420, .460), Point(.485, .480)),
    Hand(Point(.674, .384), Point(.604, .463), Point(.528, .422), Point(.508, .340),
         Point(.604, .463), Point(.545, .480)),
]
MEDIA_TWO_HAND = [
    Hand(Point(.333, .477), Point(.434, .526), Point(.506, .516), Point(.488, .436),
         Point(.434, .526), Point(.480, .570)),
    Hand(Point(.642, .479), Point(.562, .534), Point(.510, .527), Point(.504, .439),
         Point(.562, .534), Point(.540, .580)),
]
SINGLE_FINGER_HEART = Hand(Point(.355, .415), Point(.304, .456),
                           Point(.397, .613), Point(.320, .627))


class GestureTests(unittest.TestCase):
    def test_model_landmark_regressions_including_previous_diamond_misfire(self):
        path = Path(__file__).parent / "synthetic/landmark_regressions.json"
        for fixture in json.loads(path.read_text()):
            hands = [Hand(**{key: None if value is None else Point(**value)
                             for key, value in hand.items()}) for hand in fixture["hands"]]
            self.assertEqual(classify_heart(hands), fixture["expected"], fixture["id"])

    def test_only_two_hand_heart_matches(self):
        self.assertEqual(classify_heart(TWO_HAND), "two-hand")
        self.assertEqual(classify_heart(MEDIA_TWO_HAND), "two-hand")
        self.assertIsNone(classify_heart(TWO_HAND[:1]))
        self.assertIsNone(classify_heart([SINGLE_FINGER_HEART]))
        flat = [
            Hand(TWO_HAND[0].wrist, TWO_HAND[0].middle_mcp,
                 Point(.47, .35), TWO_HAND[0].thumb_tip,
                 TWO_HAND[0].index_mcp, TWO_HAND[0].index_pip),
            Hand(TWO_HAND[1].wrist, TWO_HAND[1].middle_mcp,
                 Point(.53, .35), TWO_HAND[1].thumb_tip,
                 TWO_HAND[1].index_mcp, TWO_HAND[1].index_pip),
        ]
        self.assertIsNone(classify_heart(flat))

    def test_pose_guided_crops_cover_two_hands(self):
        pose = Pose(Point(.675, .473), Point(.299, .476),
                    Point(.630, .490), Point(.356, .494))
        boxes = heart_crop_boxes(pose)
        self.assertIsNotNone(boxes)
        self.assertLess(boxes[0][0], .333)
        self.assertGreater(boxes[0][2], .506)
        self.assertLess(boxes[1][0], .510)
        self.assertGreater(boxes[1][2], .642)

    def test_heart_among_other_hands_and_cooperative_halves(self):
        self.assertEqual(classify_heart([SINGLE_FINGER_HEART, *TWO_HAND]), "two-hand")
        self.assertIsNone(classify_heart([TWO_HAND[0]]))
        self.assertEqual(classify_heart([TWO_HAND[0], TWO_HAND[1]]), "two-hand")

    def test_cooperative_wrist_crops(self):
        poses = [Pose(Point(.15, .65), Point(.35, .65), Point(.20, .3), Point(.43, .6)),
                 Pose(Point(.65, .65), Point(.85, .65), Point(.57, .6), Point(.8, .3))]
        candidates = crop_candidate_poses(poses)
        self.assertTrue(any({p.left_wrist, p.right_wrist} == {Point(.43, .6), Point(.57, .6)}
                            for p in candidates))

    def test_regular_slow_inference_stays_on_but_stalls_and_old_results_stop(self):
        state = GestureState()
        state.observe(Observation(0, True, None, TWO_HAND, completed_at=.45))
        self.assertTrue(state.safe_heart(.95))
        self.assertFalse(state.safe_heart(1.11))
        state.observe(Observation(2, True, None, TWO_HAND, completed_at=2.8))
        self.assertFalse(state.safe_heart(2.81))

    def test_heart_release_grace_and_immediate_restart(self):
        detector = HeartDetector()
        self.assertEqual(detector.observe(TWO_HAND, 0), "two-hand")
        self.assertEqual(detector.observe([], .2), "two-hand")
        self.assertIsNone(detector.observe([], .31))
        self.assertEqual(detector.observe(MEDIA_TWO_HAND, .32), "two-hand")
        self.assertIsNone(detector.observe([], .63))

    def test_heartbeat_release_and_stale_camera(self):
        state = GestureState()
        policy = CommandPolicy(state)
        state.observe(Observation(0, True, None, TWO_HAND))
        state.observe(Observation(.1, True, None, TWO_HAND))
        self.assertEqual(policy.commands(.1), [1, 4])
        self.assertEqual(policy.commands(.2), [])
        self.assertEqual(policy.commands(.31), [4])
        state.observe(Observation(.39, True, None, []))
        self.assertEqual(policy.commands(.51), [4])
        state.observe(Observation(.71, True, None, []))
        self.assertEqual(policy.commands(.72), [5])
        state.observe(Observation(.73, True, None, MEDIA_TWO_HAND))
        self.assertEqual(policy.commands(.73), [4])
        # Unknown/stale camera must not masquerade as an empty campsite.
        # Repeated STOP keeps the firmware disarmed until fresh frames arrive.
        self.assertEqual(policy.commands(1.8), [6])

    def test_single_finger_heart_never_starts_pump(self):
        state = GestureState()
        policy = CommandPolicy(state)
        for now in (0, .1, .2, .3, .4, .5):
            state.observe(Observation(now, True, None, [SINGLE_FINGER_HEART]))
            commands = policy.commands(now)
            self.assertNotIn(4, commands)
            self.assertNotIn(2, commands)
        self.assertTrue(state.person)
        self.assertIsNone(state.heart_kind)

    def test_presence_hysteresis_and_refresh(self):
        state = GestureState()
        policy = CommandPolicy(state)
        state.observe(Observation(0, True, None, []))
        self.assertEqual(policy.commands(0), [0, 5])
        state.observe(Observation(.1, True, None, []))
        self.assertEqual(policy.commands(.1), [1])
        state.observe(Observation(5.1, True, None, []))
        self.assertEqual(policy.commands(5.1)[0], 1)
        state.observe(Observation(5.2, False, None, []))
        self.assertTrue(state.person)
        state.observe(Observation(6.7, False, None, []))
        self.assertFalse(state.person)
        self.assertIn(0, policy.commands(6.7))

    def test_command_set_excludes_wave(self):
        state = GestureState()
        policy = CommandPolicy(state)
        commands = []
        xs = [0, .05, .18, .38, .62, .78, .82, .72, .52, .28, .05, -.03]
        for i, x in enumerate(xs):
            now = i * .1
            pose = Pose(Point(.4, .65), Point(.6, .65),
                        Point(.45, .8), Point(.5 + x * .2, .8))
            state.observe(Observation(now, True, pose, []))
            commands.extend(policy.commands(now))
        self.assertNotIn(4, commands)
        self.assertTrue(set(commands).issubset({0, 1, 4, 5, 6}))


if __name__ == "__main__":
    unittest.main()
