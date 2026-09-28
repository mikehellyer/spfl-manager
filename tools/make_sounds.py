"""Generate the crowd sound effects used in match highlights.

    .venv/bin/python tools/make_sounds.py

Writes WAV files to src/spfl_manager/assets/sounds/. Run it again after
tweaking anything here. The game only loads the WAVs, so numpy is needed
for this script and not at runtime.

How it works: a crowd is lots of individual voices. Each voice is a buzzy
sawtooth at its own pitch, with its own wobble, start time and loudness.
The voices are summed, then shaped with vocal-tract "formants" (resonant
peaks) so the mix sounds like people shouting a vowel - "aah" for a cheer,
"oo" for an ooh or a boo. Filtered noise and applause claps are layered on top.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 22050
OUT = Path(__file__).resolve().parents[1] / "src" / "spfl_manager" / "assets" / "sounds"
rng = np.random.default_rng(1872)  # Scotland v England, the first international

# formant frequencies (Hz) and bandwidths for the vowels we need
VOWELS = {
    "ah": [(750, 130), (1200, 150), (2600, 250)],
    "eh": [(550, 110), (1800, 160), (2500, 250)],
    "oh": [(480, 100), (900, 120), (2500, 250)],
    "oo": [(320, 80), (800, 110), (2300, 250)],
    "boo": [(280, 70), (650, 100), (2200, 300)],
}


def envelope(n, points):
    """Piecewise-linear envelope from [(time_s, level), ...]."""
    t = np.arange(n) / SR
    xs, ys = zip(*points)
    return np.interp(t, xs, ys)


def voice(n, f0, contour, onset, length, vib_rate, vib_depth, jitter=0.01):
    """One shouting voice: sawtooth with a pitch contour, vibrato and wobble."""
    t = np.arange(n) / SR
    pitch = f0 * np.interp(t, *zip(*contour))
    pitch *= 1 + vib_depth * np.sin(2 * np.pi * vib_rate * t + rng.uniform(0, 6.28))
    # slow random drift so no two voices lock together
    drift = np.cumsum(rng.normal(0, 1, n))
    drift = drift / (np.abs(drift).max() + 1e-9)
    pitch *= 1 + jitter * drift
    phase = np.cumsum(pitch / SR)
    saw = 2 * (phase % 1.0) - 1
    amp = np.clip((t - onset) / 0.08, 0, 1) * np.clip((onset + length - t) / 0.25, 0, 1)
    return saw * amp


def formant_filter(signal, vowel):
    """Shape a buzzy signal into a vowel by multiplying its spectrum by formant peaks."""
    spec = np.fft.rfft(signal)
    freqs = np.fft.rfftfreq(len(signal), 1 / SR)
    shape = np.zeros_like(freqs)
    for i, (f, bw) in enumerate(VOWELS[vowel]):
        shape += (0.9**i) * np.exp(-0.5 * ((freqs - f) / bw) ** 2)
    shape += 0.02  # a little breathiness everywhere
    return np.fft.irfft(spec * shape, len(signal))


def band_noise(n, lo, hi):
    spec = np.fft.rfft(rng.normal(0, 1, n))
    freqs = np.fft.rfftfreq(n, 1 / SR)
    spec[(freqs < lo) | (freqs > hi)] = 0
    out = np.fft.irfft(spec, n)
    return out / (np.abs(out).max() + 1e-9)


def applause(n, start, density, length):
    """Lots of short noisy claps."""
    out = np.zeros(n)
    clap_len = int(0.012 * SR)
    clap_env = np.exp(-np.linspace(0, 6, clap_len))
    count = int(density * length)
    for _ in range(count):
        t0 = int((start + rng.uniform(0, length) ** 1.3 / length**0.3) * SR)
        if t0 + clap_len < n:
            out[t0:t0 + clap_len] += rng.normal(0, 1, clap_len) * clap_env * rng.uniform(0.3, 1)
    return band_noise_like(out, 800, 6000)


def band_noise_like(sig, lo, hi):
    spec = np.fft.rfft(sig)
    freqs = np.fft.rfftfreq(len(sig), 1 / SR)
    spec[(freqs < lo) | (freqs > hi)] = 0
    return np.fft.irfft(spec, len(sig))


def crowd(seconds, voices, vowels, f0_range, contour, onset_spread, length_range, vib=(4, 8), vib_depth=0.02):
    n = int(seconds * SR)
    groups = {v: np.zeros(n) for v in vowels}
    for _ in range(voices):
        v = rng.choice(vowels)
        f0 = rng.uniform(*f0_range)
        onset = rng.uniform(0, onset_spread)
        length = rng.uniform(*length_range)
        groups[v] += voice(n, f0, contour, onset, length, rng.uniform(*vib), vib_depth) * rng.uniform(0.4, 1)
    return sum(formant_filter(sig, v) for v, sig in groups.items())


def normalise(sig, peak=0.85):
    return sig / (np.abs(sig).max() + 1e-9) * peak


def fade(sig, fade_in=0.02, fade_out=0.2):
    n = len(sig)
    a, b = int(fade_in * SR), int(fade_out * SR)
    sig = sig.copy()
    sig[:a] *= np.linspace(0, 1, a)
    sig[n - b:] *= np.linspace(1, 0, b)
    return sig


# ----------------------------------------------------------------------------- sounds
def make_cheer():
    """GOAL! A rising roar of 'YEAAH', applause, then it dies away."""
    secs = 3.2
    n = int(secs * SR)
    contour = [(0, 0.85), (0.25, 1.2), (0.6, 1.3), (1.6, 1.25), (2.6, 1.05), (secs, 1.0)]
    voices = crowd(secs, 90, ["ah", "eh", "ah", "oh"], (120, 320), contour, 0.3, (1.6, 2.8), vib_depth=0.03)
    roar = band_noise(n, 200, 3500) * envelope(n, [(0, 0), (0.2, 0.8), (1.5, 0.7), (secs, 0)])
    claps = applause(n, 0.4, 900, 2.4)
    mix = normalise(voices) * envelope(n, [(0, 0), (0.15, 0.9), (0.5, 1.0), (1.8, 0.9), (secs, 0)])
    mix += 0.35 * roar + 0.5 * normalise(claps) * envelope(n, [(0, 0), (0.5, 0.6), (2.0, 0.5), (secs, 0)])
    return fade(normalise(mix), 0.01, 0.6)


def make_ooh():
    """Near miss: 'OOOOOH' rising then sagging away in disappointment."""
    secs = 1.8
    n = int(secs * SR)
    contour = [(0, 0.9), (0.35, 1.18), (0.7, 1.12), (1.3, 0.85), (secs, 0.8)]
    voices = crowd(secs, 70, ["oo", "oh", "oo"], (110, 300), contour, 0.12, (1.1, 1.6), vib_depth=0.015)
    air = band_noise(n, 150, 1500) * envelope(n, [(0, 0), (0.25, 0.5), (1.0, 0.3), (secs, 0)])
    mix = normalise(voices) * envelope(n, [(0, 0), (0.25, 1.0), (0.8, 0.85), (secs, 0)]) + 0.25 * air
    return fade(normalise(mix, 0.8), 0.02, 0.5)


def make_boo():
    """A low, sustained 'BOOOO' from the home end."""
    secs = 2.0
    n = int(secs * SR)
    contour = [(0, 1.0), (0.3, 1.04), (1.4, 0.97), (secs, 0.9)]
    voices = crowd(secs, 70, ["boo", "oo"], (80, 190), contour, 0.25, (1.2, 1.8), vib=(3, 6), vib_depth=0.025)
    rumble = band_noise(n, 80, 900) * envelope(n, [(0, 0), (0.3, 0.6), (1.5, 0.5), (secs, 0)])
    mix = normalise(voices) * envelope(n, [(0, 0), (0.3, 1.0), (1.4, 0.9), (secs, 0)]) + 0.3 * rumble
    return fade(normalise(mix, 0.8), 0.03, 0.5)


def make_murmur():
    """Background crowd hum for the highlights - loops seamlessly."""
    secs = 6.0
    n = int(secs * SR)
    bed = band_noise(n, 120, 2200) * 0.5
    chatter = np.zeros(n)
    for _ in range(140):  # short random syllables from all around the ground
        start = rng.uniform(0, secs - 0.4)
        length = rng.uniform(0.15, 0.4)
        f0 = rng.uniform(100, 260)
        v = rng.choice(list(VOWELS))
        sig = voice(n, f0, [(0, 1), (secs, 1)], start, length, 5, 0.02)
        chatter += formant_filter(sig, v) * rng.uniform(0.2, 0.6)
    mix = normalise(bed) * 0.6 + normalise(chatter) * 0.5
    # crossfade the end into the start so the loop has no click
    x = int(0.5 * SR)
    mix[:x] = mix[:x] * np.linspace(0, 1, x) + mix[-x:] * np.linspace(1, 0, x)
    return normalise(mix[:-x], 0.5)


def write_wav(name, sig):
    OUT.mkdir(parents=True, exist_ok=True)
    data = (np.clip(sig, -1, 1) * 32767).astype("<i2").tobytes()
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data)
    print(f"{name}.wav  {len(sig) / SR:.1f}s  {len(data) // 1024} KB")


if __name__ == "__main__":
    write_wav("cheer", make_cheer())
    write_wav("ooh", make_ooh())
    write_wav("boo", make_boo())
    write_wav("murmur", make_murmur())
