from auto_modules.adapters.windows.hotkeys import HotkeyTriggerSource


def test_hotkey_source_emits_once_until_key_is_released():
    pressed = set()
    source = HotkeyTriggerSource(key_state=lambda code: code in pressed)

    pressed.add(0x75)  # F6
    assert source.poll(("F6",)) == ("F6",)
    assert source.poll(("F6",)) == ()
    pressed.clear()
    assert source.poll(("F6",)) == ()
    pressed.add(0x75)
    assert source.poll(("F6",)) == ("F6",)


def test_hotkey_source_supports_every_name_offered_by_the_workbench():
    observed = []

    def key_state(code):
        observed.append(code)
        return True

    source = HotkeyTriggerSource(key_state=key_state)
    keys = ("F1", "F12", "W", "A", "SPACE", "UP", "DOWN", "LEFT", "RIGHT")

    assert source.poll(keys) == keys
    assert observed == [0x70, 0x7B, ord("W"), ord("A"), 0x20, 0x26, 0x28, 0x25, 0x27]


def test_hotkey_source_ignores_unknown_names_without_reading_platform_state():
    source = HotkeyTriggerSource(key_state=lambda code: (_ for _ in ()).throw(AssertionError(code)))

    assert source.poll(("NOT-A-KEY", "")) == ()
