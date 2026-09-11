import pytest

from core.events.follow_chain import button_mask


def test_single_and_chord_use_existing_masks():
    assert button_mask({'button': 'A'}) == 0x1000
    assert button_mask({'buttons': ['A', 'RB']}) == 0x1200
    assert button_mask({'buttons': ['A', 'A']}) == 0x1000


@pytest.mark.parametrize('step', [
    {}, {'buttons': []}, {'buttons': 'A'}, {'buttons': ['LT']},
    {'buttons': [None]}, {'button': 'A', 'buttons': ['B']},
])
def test_invalid_or_ambiguous_chord_is_rejected(step):
    with pytest.raises(ValueError):
        button_mask(step)
