import unittest
from gesture_core import CommandPolicy, GestureState, Observation


class CameraStopTests(unittest.TestCase):
    def test_unknown_camera_sends_only_stop_and_cannot_start_absence_timer(self):
        state = GestureState()
        policy = CommandPolicy(state)
        self.assertEqual(policy.commands(0), [6])
        self.assertEqual(policy.commands(.1), [])
        self.assertEqual(policy.commands(.31), [6])
        self.assertEqual(policy.commands(10), [6])
        # Recovery sends a fresh presence state so the board can explicitly arm.
        state.observe(Observation(10.1, False, None, []))
        commands = policy.commands(10.1)
        self.assertIn(0, commands)
        self.assertNotIn(6, commands)


if __name__ == '__main__':
    unittest.main()
