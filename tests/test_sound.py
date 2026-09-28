import os

import pytest

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame = pytest.importorskip("pygame")


def test_synthesised_sounds_play_at_the_right_speed():
    """The device often runs at 44.1/48 kHz: sounds must be resampled, not played raw
    (which made the title tune run at double speed, an octave too high)."""
    pygame.init()
    from spfl_manager.ui.sound import MELODY, TUNE_EIGHTH, SoundBank

    bank = SoundBank()
    if not bank.enabled:
        pytest.skip("no audio device available")
    expected = sum(length for _, length in MELODY) * TUNE_EIGHTH
    assert bank.sounds["tune"].get_length() == pytest.approx(expected, rel=0.02)
    assert bank.sounds["whistle"].get_length() == pytest.approx(0.5, rel=0.02)
    pygame.quit()
