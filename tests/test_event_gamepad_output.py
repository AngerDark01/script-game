import unittest

from auto_modules.core.events.gamepad_output import state_from_inputs


class EventGamepadOutputTests(unittest.TestCase):
    def test_movement_input_emits_left_stick_axis_and_button_together(self):
        state = state_from_inputs({"LS_UP", "A"})
        self.assertEqual(state["buttons"], 0x1000)
        self.assertEqual(state["leftStickX"], 0)
        self.assertEqual(state["leftStickY"], 32767)

    def test_diagonal_movement_is_normalized_to_xinput_range(self):
        state = state_from_inputs({"LS_UP", "LS_RIGHT"})
        self.assertTrue(23160 <= state["leftStickX"] <= 23180)
        self.assertTrue(23160 <= state["leftStickY"] <= 23180)

    def test_opposite_movement_inputs_cancel_to_neutral(self):
        state = state_from_inputs({"LS_LEFT", "LS_RIGHT", "LS_UP", "LS_DOWN"})
        self.assertEqual(state["leftStickX"], 0)
        self.assertEqual(state["leftStickY"], 0)


if __name__ == "__main__":
    unittest.main()
