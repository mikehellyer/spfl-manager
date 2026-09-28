"""Tiny SID-flavoured sound generator - no audio files needed.

All sounds are synthesised at start-up. If audio isn't available the
game simply runs silently.
"""

from __future__ import annotations

import math
import random
from array import array
from pathlib import Path

import pygame

SR = 22050
ASSETS = Path(__file__).resolve().parents[1] / "assets" / "sounds"
# crowd samples made by tools/make_sounds.py: file name -> sound name
CROWD_FILES = {"cheer": "goal", "ooh": "ooh", "boo": "boo", "murmur": "crowd"}


def _square(freq, n, vol, duty=0.5):
    out = []
    period = SR / freq if freq else 0
    for i in range(n):
        if not period:
            out.append(0.0)
            continue
        out.append(vol if (i % period) / period < duty else -vol)
    return out


def _tri(freq, n, vol):
    period = SR / freq
    return [vol * (4 * abs((i / period) % 1 - 0.5) - 1) for i in range(n)]


def _env(samples, attack=0.005, release=0.03):
    n = len(samples)
    a, r = int(attack * SR), int(release * SR)
    for i in range(min(a, n)):
        samples[i] *= i / a
    for i in range(min(r, n)):
        samples[n - 1 - i] *= i / r
    return samples


def _midi(note):
    return 440 * 2 ** ((note - 69) / 12)


def _to_sound(samples):
    init = pygame.mixer.get_init()
    if not init:
        return None
    channels = init[2]
    data = array("h")
    for s in samples:
        v = int(max(-1, min(1, s)) * 32000)
        data.extend([v] * channels)
    return pygame.mixer.Sound(buffer=data.tobytes())


# An original little jig for the title screen: (midi note or 0 for rest, eighths)
MELODY = [
    (69, 1), (72, 1), (74, 2), (76, 1), (74, 1), (72, 2),
    (69, 1), (67, 1), (69, 2), (72, 2), (74, 2),
    (76, 1), (79, 1), (81, 2), (79, 1), (76, 1), (74, 2),
    (72, 1), (74, 1), (76, 2), (74, 2), (69, 2),
    (69, 1), (72, 1), (74, 2), (76, 1), (74, 1), (72, 2),
    (69, 1), (67, 1), (69, 2), (72, 2), (74, 2),
    (76, 1), (79, 1), (81, 1), (79, 1), (76, 1), (74, 1), (72, 1), (74, 1),
    (69, 4), (0, 2), (57, 2),
]
BASS = [45, 45, 43, 43, 41, 41, 43, 45]  # one note per bar (8 eighths)


class SoundBank:
    def __init__(self):
        self.enabled = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        try:
            pygame.mixer.pre_init(SR, -16, 1, 512)
            pygame.mixer.init(SR, -16, 1, 512)
            if pygame.mixer.get_init()[1] != -16:
                return
            self._build()
            self._load_crowd()
            self.enabled = True
        except Exception:
            self.enabled = False

    def _build(self):
        rng = random.Random(64)
        eighth = int(SR * 0.125)

        lead = []
        for note, length in MELODY:
            n = eighth * length
            seg = _square(_midi(note), n, 0.18, 0.25) if note else [0.0] * n
            lead += _env(seg, 0.003, 0.02)
        bass = []
        for note in BASS:
            for k in range(4):  # octave-bounce bass line, two eighths each
                f = _midi(note + (12 if k % 2 else 0))
                bass += _env(_tri(f, eighth * 2, 0.22), 0.002, 0.01)
        n = max(len(lead), len(bass))
        lead += [0.0] * (n - len(lead))
        bass += [0.0] * (n - len(bass))
        self.sounds["tune"] = _to_sound([a + b for a, b in zip(lead, bass)])

        self.sounds["blip"] = _to_sound(_env(_square(880, int(SR * 0.03), 0.15), 0.001, 0.01))
        self.sounds["select"] = _to_sound(
            _env(_square(660, int(SR * 0.04), 0.15) + _square(990, int(SR * 0.06), 0.15), 0.001, 0.02)
        )
        self.sounds["kick"] = _to_sound(_env(_tri(110, int(SR * 0.05), 0.5), 0.001, 0.03))

        whistle = []
        for i in range(int(SR * 0.5)):
            f = 2900 + 250 * math.sin(i / SR * 2 * math.pi * 30)
            whistle.append(0.18 * math.sin(2 * math.pi * f * i / SR))
        self.sounds["whistle"] = _to_sound(_env(whistle, 0.01, 0.05))

        roar, n = [], int(SR * 2.2)
        last = 0.0
        for i in range(n):
            last = last * 0.85 + rng.uniform(-1, 1) * 0.15  # low-passed noise = crowd
            env = min(1, i / (SR * 0.25)) * min(1, (n - i) / (SR * 0.8))
            roar.append(last * 2.2 * env)
        self.sounds["goal"] = _to_sound(roar)

        ooh, n = [], int(SR * 0.9)
        for i in range(n):
            last = last * 0.9 + rng.uniform(-1, 1) * 0.1
            env = math.sin(math.pi * i / n)
            ooh.append(last * 1.8 * env)
        self.sounds["ooh"] = _to_sound(ooh)

    def _load_crowd(self):
        """Replace the simple noise effects with the recorded-style crowd samples."""
        for file, name in CROWD_FILES.items():
            path = ASSETS / f"{file}.wav"
            try:
                self.sounds[name] = pygame.mixer.Sound(str(path))
            except (pygame.error, FileNotFoundError):
                pass  # keep the synthesised fallback (or silence for boo/crowd)

    def play(self, name, loops=0, volume=1.0):
        if self.enabled and self.sounds.get(name):
            channel = self.sounds[name].play(loops=loops)
            if channel is not None:
                channel.set_volume(volume)

    def stop(self, name, fade_ms=0):
        if self.enabled and self.sounds.get(name):
            if fade_ms:
                self.sounds[name].fadeout(fade_ms)
            else:
                self.sounds[name].stop()
