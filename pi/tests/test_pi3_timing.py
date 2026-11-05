import unittest
from gesture_core import GestureState, PI3_TIMING, CommandPolicy, Observation
from test_gesture_core import TWO_HAND, SINGLE_FINGER_HEART


class Pi3TimingTests(unittest.TestCase):
    def make_active(self):
        state = GestureState(PI3_TIMING)
        state.observe(Observation(0., True, None, TWO_HAND, completed_at=.95))
        self.assertFalse(state.safe_heart(.95))
        state.observe(Observation(1., True, None, TWO_HAND, completed_at=1.95))
        self.assertTrue(state.safe_heart(1.95))
        return state

    def test_one_fps_continuous_hold_has_no_off_gaps(self):
        state, policy = GestureState(PI3_TIMING), None
        policy = CommandPolicy(state)
        for tick in range(0, 2095):
            now = tick / 100
            if tick >= 95 and (tick - 95) % 100 == 0:
                state.observe(Observation((tick-95)/100, True, None, TWO_HAND, completed_at=now))
            commands = policy.commands(now)
            if now >= 1.95:
                self.assertTrue(state.safe_heart(now), now)
                self.assertNotIn(5, commands)
                self.assertNotIn(6, commands)
        state.observe(Observation(20., True, None, [], completed_at=20.95))
        self.assertFalse(state.safe_heart(20.95))
        self.assertIn(5, policy.commands(20.95))

    def test_negative_frame_revokes_immediately_even_at_high_fps(self):
        state = GestureState(PI3_TIMING)
        for t in (0., .1):
            state.observe(Observation(t, True, None, TWO_HAND, completed_at=t+.1))
        self.assertTrue(state.safe_heart(.2))
        state.observe(Observation(.11, True, None, [], completed_at=.21))
        self.assertFalse(state.safe_heart(.21))
        state.observe(Observation(.12, True, None, TWO_HAND, completed_at=.22))
        self.assertFalse(state.safe_heart(.22))
        state.observe(Observation(.13, True, None, TWO_HAND, completed_at=.23))
        self.assertTrue(state.safe_heart(.23))

    def test_isolated_false_positive_and_single_hand_never_arm(self):
        state, commands = GestureState(PI3_TIMING), []
        policy = CommandPolicy(state)
        sequence = [[], TWO_HAND, [], [SINGLE_FINGER_HEART], TWO_HAND[:1], TWO_HAND, []]
        for i, hands in enumerate(sequence):
            state.observe(Observation(float(i), True, None, hands, completed_at=i+.95))
            commands.extend(policy.commands(i+.95))
        self.assertNotIn(4, commands)

    def test_stall_stops_and_reconnection_requires_two_new_frames(self):
        state = self.make_active()
        policy = CommandPolicy(state)
        self.assertIn(4, policy.commands(1.95))
        self.assertTrue(state.safe_heart(3.94))
        self.assertFalse(state.safe_heart(3.96))
        self.assertIn(5, policy.commands(3.96))
        self.assertTrue(state.safe_person(3.96))
        self.assertIn(6, policy.commands(4.46))
        state.observe(Observation(4., True, None, TWO_HAND, completed_at=4.95))
        self.assertFalse(state.safe_heart(4.95))
        state.observe(Observation(5., True, None, TWO_HAND, completed_at=5.95))
        self.assertTrue(state.safe_heart(5.95))

    def test_slow_old_or_replayed_frame_cannot_extend_lease(self):
        state = self.make_active()
        state.observe(Observation(1., True, None, TWO_HAND, completed_at=3.0))
        self.assertEqual(state.last_result, 1.95)
        self.assertFalse(state.safe_heart(3.96))
        state.observe(Observation(4., True, None, TWO_HAND, completed_at=6.1))
        self.assertFalse(state.safe_heart(6.1))
        self.assertTrue(state.safe_person(6.1))
        self.assertFalse(state.camera_stale(6.1))
        state.observe(Observation(7.2, True, None, TWO_HAND, completed_at=8.2))
        self.assertFalse(state.safe_heart(8.2))

    def test_out_of_order_positive_does_not_override_release(self):
        state = self.make_active()
        state.observe(Observation(2., True, None, [], completed_at=2.95))
        state.observe(Observation(1.5, True, None, TWO_HAND, completed_at=3.0))
        self.assertFalse(state.safe_heart(3.0))
        self.assertEqual(state.last_frame, 2.)

    def test_slow_presence_does_not_relax_pump_limits(self):
        state = self.make_active()
        policy = CommandPolicy(state)
        policy.commands(1.95)
        state.observe(Observation(2., True, None, TWO_HAND, completed_at=4.1))
        commands = policy.commands(4.1)
        self.assertTrue(state.safe_person(4.1))
        self.assertFalse(state.safe_heart(4.1))
        self.assertIn(5, commands)
        self.assertNotIn(0, commands)
        self.assertNotIn(6, commands)
        self.assertTrue(state.safe_person(6.59))
        self.assertFalse(state.safe_person(6.61))
        self.assertIn(6, policy.commands(6.61))

    def test_presence_negative_evidence_and_old_results_still_stop(self):
        state = self.make_active()
        state.observe(Observation(3., False, None, [], completed_at=5.1))
        self.assertFalse(state.safe_person(5.1))
        for t in (6., 9.):
            state.observe(Observation(t, True, None, [], completed_at=t+2.6))
            self.assertFalse(state.safe_person(t+2.6))

    def test_slow_candidate_needs_next_fresh_positive(self):
        state = GestureState(PI3_TIMING)
        state.observe(Observation(0., True, None, TWO_HAND, completed_at=1.31))
        self.assertFalse(state.safe_heart(1.31))
        state.observe(Observation(1.31, True, None, TWO_HAND, completed_at=2.31))
        self.assertTrue(state.safe_heart(2.31))
        state.observe(Observation(2.31, True, None, [], completed_at=3.31))
        self.assertFalse(state.safe_heart(3.31))

    def test_slow_candidates_never_hold_or_arm_and_negative_clears(self):
        state = self.make_active()
        for t in (2., 3.4, 4.8):
            state.observe(Observation(t, True, None, TWO_HAND, completed_at=t+2.1))
            self.assertFalse(state.safe_heart(t+2.1))
        state.observe(Observation(6.2, True, None, [], completed_at=7.2))
        state.observe(Observation(7.2, True, None, TWO_HAND, completed_at=8.2))
        self.assertFalse(state.safe_heart(8.2))

    def test_slow_candidate_expires_after_result_gap(self):
        state = GestureState(PI3_TIMING)
        state.observe(Observation(0., True, None, TWO_HAND, completed_at=2.2))
        state.observe(Observation(4.5, True, None, TWO_HAND, completed_at=5.5))
        self.assertFalse(state.safe_heart(5.5))

    def test_throttled_pi_1_3s_frames_hold_without_gaps(self):
        # Measured on a throttled Pi 3B+ (weak supply): 1.2-1.3 s per frame.
        state = GestureState(PI3_TIMING)
        policy = CommandPolicy(state)
        for i in range(12):
            t = i * 1.3
            state.observe(Observation(t, True, None, TWO_HAND, completed_at=t + 1.3))
            if i >= 1:
                for dt in (0., .65, 1.29):
                    self.assertTrue(state.safe_heart(t + 1.3 + dt))
                    self.assertNotIn(5, policy.commands(t + 1.3 + dt))
        state.observe(Observation(15.6, True, None, [], completed_at=16.9))
        self.assertFalse(state.safe_heart(16.9))
        self.assertIn(5, policy.commands(16.9))
