from auto_modules.adapters.windows.window_finder import _matches_window


def test_title_only_search_does_not_match_unrelated_window():
    assert _matches_window("Path of Exile 2", "GameWindow", "Path of Exile 2", "")
    assert not _matches_window("Program Manager", "Progman", "Path of Exile 2", "")


def test_class_only_search_does_not_match_unrelated_window():
    assert _matches_window("", "UnrealWindow", "", "UnrealWindow")
    assert not _matches_window("Other app", "OtherClass", "", "UnrealWindow")
