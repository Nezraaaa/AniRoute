"""Original 30 s soundtrack for the AniRoute product film, synthesised from scratch.

Warm ambient pad + soft piano motif + light pulse (D major, 96 BPM), with sound design timed to the
film: whooshes on camera moves, glassy UI ticks, a gentle detection chime, the confirm tap, a low thrum
when the hazard pin lands, and a resolving chord on the logo.

    python make_audio.py      -> assets/soundtrack.wav (48 kHz, 16-bit stereo)
"""
from pathlib import Path

import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt

SR = 48_000
DUR = 40.0
# The film plays the story slower after a 6 s prologue (see storyTime in scene.js); sound effects are
# authored in story time and mapped to film time with the inverse of that curve.
T0, SLOW = -4.0, 26.5 / 32.5


def story_time(T):
    if T <= 6:
        return T0 + T
    if T <= 9:
        u = (T - 6) / 3
        return T0 + 6 + 3 * u + (SLOW - 1) * 3 * (u ** 3 - u ** 4 / 2)
    return T0 + 7.5 + 1.5 * SLOW + (T - 9) * SLOW


def film_time(s):
    lo, hi = 0.0, DUR
    for _ in range(60):
        mid = (lo + hi) / 2
        if story_time(mid) < s: lo = mid
        else: hi = mid
    return (lo + hi) / 2
N = int(SR * DUR)
rng = np.random.default_rng(7)
t_all = np.arange(N) / SR
L = np.zeros(N)
R = np.zeros(N)


def note_hz(name: str) -> float:
    names = {'C': -9, 'C#': -8, 'D': -7, 'D#': -6, 'E': -5, 'F': -4, 'F#': -3, 'G': -2, 'G#': -1, 'A': 0, 'A#': 1, 'B': 2}
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[pitch] + (octave - 4) * 12) / 12)


def add(sig, start, gain=1.0, pan=0.0):
    i = int(start * SR)
    if i >= N:
        return
    sig = sig[: N - i]
    lg, rg = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    L[i:i + len(sig)] += sig * gain * lg * 1.414
    R[i:i + len(sig)] += sig * gain * rg * 1.414


def env_adsr(n, a, d, s, r):
    e = np.ones(n) * s
    na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
    na = min(na, n)
    e[:na] = np.linspace(0, 1, na, endpoint=False)
    if nd:
        e[na:na + nd] = np.linspace(1, s, min(nd, max(0, n - na)))[: max(0, min(nd, n - na))]
    if nr and n > nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def lowpass(x, hz, order=2):
    return sosfilt(butter(order, hz, 'low', fs=SR, output='sos'), x)


def highpass(x, hz, order=2):
    return sosfilt(butter(order, hz, 'high', fs=SR, output='sos'), x)


def bandpass(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], 'band', fs=SR, output='sos'), x)


# ── harmony: D – Bm – G – A, one chord per bar (2.5 s), 12 bars ──────────────────────────
BAR = 2.5
chords = [['D3', 'A3', 'D4', 'F#4'], ['B2', 'F#3', 'B3', 'D4'], ['G2', 'D3', 'G3', 'B3'], ['A2', 'E3', 'A3', 'C#4']] * 4
chords[-1] = ['D3', 'A3', 'D4', 'F#4']            # resolve home under the logo
chords[-2] = ['G2', 'D3', 'B3', 'E4']             # Gadd6 lift into the finale

# pad: detuned soft saws through a slowly opening low-pass
for b, ch in enumerate(chords):
    start, length = b * BAR, BAR + 1.2
    n = int(length * SR)
    tt = np.arange(n) / SR
    sig = np.zeros(n)
    for name in ch:
        f = note_hz(name)
        for det in (-0.12, 0.0, 0.11):
            ph = rng.random() * 2 * np.pi
            ff = f * 2 ** (det / 12)
            sig += (2 * ((ff * tt + ph / (2 * np.pi)) % 1) - 1) * 0.18
    cutoff = 700 + 1300 * min(1.0, start / 24.0)
    sig = lowpass(sig, cutoff, 2) * env_adsr(n, 0.9, 0.5, 0.85, 1.1)
    gain = 0.12 * (0.7 + 0.3 * min(1.0, start / 3.0))
    add(sig, start, gain, pan=-0.15)
    add(np.roll(sig, 900), start, gain * 0.9, pan=0.15)

# sub bass on the chord roots
for b, ch in enumerate(chords):
    if b < 2:
        continue
    f = note_hz(ch[0]) / 2
    n = int(BAR * SR)
    tt = np.arange(n) / SR
    sig = np.sin(2 * np.pi * f * tt) * env_adsr(n, 0.05, 0.4, 0.7, 0.4)
    add(sig, b * BAR, 0.16)


# soft piano: sine partials with hammer brightness and exponential decay
def piano(name, dur=2.4, vel=1.0):
    f = note_hz(name)
    n = int(dur * SR)
    tt = np.arange(n) / SR
    sig = np.zeros(n)
    for k, amp in enumerate([1.0, 0.42, 0.2, 0.11, 0.05], start=1):
        sig += amp * np.sin(2 * np.pi * f * k * tt * (1 + 0.0004 * k * k)) * np.exp(-tt * (1.6 + 0.9 * k))
    attack = np.minimum(1.0, tt / 0.004)
    return sig * attack * vel * 0.32


motif = ['F#5', 'A5', 'D6', 'A5', 'F#5', 'E5', 'D5', 'E5']
beat = BAR / 4
for b, ch in enumerate(chords[:15]):
    roots = [c[:-1] for c in ch]
    for i in range(4):
        tpos = b * BAR + i * beat
        if b < 1 and i < 2:
            continue
        name = motif[(b * 4 + i) % len(motif)]
        # keep motif notes in the chord's colour
        if name[:-1] not in roots and name[:-1] not in ('E', 'A'):
            name = roots[2] + '5' if len(roots) > 2 else name
        add(piano(name, vel=0.8 if i % 2 else 1.0), tpos, 0.42 * min(1.0, 0.3 + tpos / 7.0), pan=0.25 if i % 2 else -0.2)
# final chord under the logo
for k, name in enumerate(['D4', 'F#4', 'A4', 'D5', 'A5']):
    add(piano(name, dur=3.0, vel=0.9), film_time(28.35) + k * 0.035, 0.5, pan=-0.3 + k * 0.15)

# light pulse: soft kick + shaker from 9 s, thinning out for the finale
for b in range(3, 15):
    for i in range(8):
        tpos = b * BAR + i * beat / 2
        if tpos > film_time(27.0):
            break
        if i % 4 == 0:
            n = int(0.35 * SR); tt = np.arange(n) / SR
            kick = np.sin(2 * np.pi * (48 + 70 * np.exp(-tt * 28)) * tt) * np.exp(-tt * 9)
            add(kick, tpos, 0.2)
        n = int(0.09 * SR)
        sh = highpass(rng.standard_normal(n), 6500) * np.exp(-np.arange(n) / SR * 55)
        add(sh, tpos + (0.012 if i % 2 else 0), 0.035 if i % 2 else 0.05, pan=0.35 if i % 2 else -0.35)


# ── sound design ──────────────────────────────────────────────────────────────────────
def add_s(sig, story_start, gain=1.0, pan=0.0):
    add(sig, film_time(story_start), gain, pan)


def whoosh(dur=1.2, lo=300, hi=3500, gain=0.25):
    n = int(dur * SR)
    noise = rng.standard_normal(n)
    out = np.zeros(n)
    steps = 24
    for s in range(steps):
        a, b = s * n // steps, (s + 1) * n // steps
        u = s / (steps - 1)
        centre = lo * (hi / lo) ** np.sin(np.pi * u * 0.5)
        seg = bandpass(noise[max(0, a - 2000):b], centre * 0.6, min(centre * 1.6, SR / 2 - 100))[-(b - a):]
        out[a:b] = seg
    env = np.sin(np.pi * np.linspace(0, 1, n)) ** 1.6
    return out * env * gain


def tick(freq=2400, gain=0.12):
    n = int(0.06 * SR); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * freq * tt) * np.exp(-tt * 90) + 0.3 * highpass(rng.standard_normal(n), 4000) * np.exp(-tt * 200)) * gain


def glass(freq=1760, dur=0.9, gain=0.12):
    n = int(dur * SR); tt = np.arange(n) / SR
    sig = sum(a * np.sin(2 * np.pi * freq * m * tt) * np.exp(-tt * (4 + 3 * m)) for m, a in [(1, 1), (2.76, 0.4), (5.4, 0.18)])
    return sig * np.minimum(1, tt / 0.002) * gain


def chime(gain=0.18):
    a = glass(note_hz('A5'), 1.2, 1.0)
    b = glass(note_hz('E6'), 1.4, 0.8)
    out = np.zeros(len(b) + int(0.16 * SR))
    out[:len(a)] += a; out[int(0.16 * SR):int(0.16 * SR) + len(b)] += b
    return out * gain


def thrum(gain=0.35):
    n = int(1.6 * SR); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * (55 + 25 * np.exp(-tt * 6)) * tt) * np.exp(-tt * 2.6) + 0.25 * lowpass(rng.standard_normal(n), 220) * np.exp(-tt * 5)) * gain


def shimmer(dur=1.6, gain=0.08):
    n = int(dur * SR); tt = np.arange(n) / SR
    sig = np.zeros(n)
    for k, name in enumerate(['D6', 'F#6', 'A6', 'D7']):
        sig += np.sin(2 * np.pi * note_hz(name) * tt + k) * (0.5 + 0.5 * np.sin(2 * np.pi * (5 + k) * tt))
    return sig * np.sin(np.pi * np.linspace(0, 1, n)) ** 2 * gain


for tpos, d, lo, hi, g in [(3.4, 1.4, 250, 2500, 0.18), (9.38, 1.8, 300, 4200, 0.2), (15.9, 1.4, 260, 3600, 0.2),
                           (16.9, 1.1, 400, 5000, 0.2), (24.3, 1.2, 380, 4800, 0.2), (26.9, 1.5, 300, 4000, 0.18)]:
    add_s(whoosh(d, lo, hi, g), tpos, 1.0, pan=0.0)
for k, tpos in enumerate(np.linspace(5.8, 7.5, 9)):
    add_s(tick(2200 + 140 * (k % 3), 0.07), tpos, 1.0, pan=0.2)
add_s(glass(1320, 0.8, 0.1), 5.0, 1.0, pan=0.1)            # card lifts
add_s(tick(1900, 0.13), 7.72, 1.0, pan=0.15)                # tap on Find routes
add_s(glass(1568, 0.8, 0.08), 7.8, 1.0, pan=0.15)          # the button lights up
add_s(glass(1175, 0.8, 0.06), 9.05, 1.0, pan=0.1)          # card lands on the form
add_s(shimmer(2.2, 0.06), 11.1, 1.0)                        # routes ignite
add_s(shimmer(1.9, 0.045), 9.45, 1.0)                       # the gold line flies to the map
for k, tpos in enumerate([11.0, 12.4]):
    add_s(glass(1568, 0.7, 0.09), tpos, 1.0, pan=-0.2 + 0.4 * k)   # pins
for k in range(3):
    add_s(glass(2093 + 200 * k, 0.6, 0.07), 12.5 + 0.22 * k, 1.0, pan=0.4)   # route cards
add_s(chime(0.16), 21.0, 1.0, pan=0.15)                     # detection
add_s(glass(1760, 0.9, 0.08), 21.8, 1.0, pan=0.3)          # dialog floats out
add_s(tick(1800, 0.16), 24.0, 1.0, pan=0.3)                 # tap on Confirm
add_s(chime(0.13), 24.08, 1.0, pan=0.2)                     # it lights up: confirmed
add_s(thrum(0.32), 25.45, 1.0)                              # hazard pin lands
add_s(shimmer(1.4, 0.06), 25.9, 1.0)                        # reroute
add_s(whoosh(1.3, 500, 6000, 0.12), 27.6, 1.0)              # ribbons rise
n = int(2.0 * SR); tt = np.arange(n) / SR
add_s(lowpass(rng.standard_normal(n), 900) * np.exp(-tt * 2.2) * 0.12 + np.sin(2 * np.pi * 73.4 * tt) * np.exp(-tt * 1.8) * 0.22, 28.2, 1.0)  # logo impact
add_s(shimmer(2.0, 0.05), 28.3, 1.0)


# prologue (story time): footsteps while the farmer walks, the crate landing on the truck bed, birds
for k in range(9):
    n = int(0.12 * SR); tt = np.arange(n) / SR
    step = lowpass(rng.standard_normal(n), 900) * np.exp(-tt * 45)
    add_s(step, -3.95 + k * 0.24 if k < 8 else -0.3, 0.05, pan=-0.1)
n = int(0.5 * SR); tt = np.arange(n) / SR
thud = (np.sin(2 * np.pi * 90 * tt) * np.exp(-tt * 18) + 0.5 * lowpass(rng.standard_normal(n), 1400) * np.exp(-tt * 30))
add_s(thud, -0.62, 0.22, pan=0.25)
for tb, f0 in [(0.6, 3400), (2.1, 4100), (4.4, 3700), (6.2, 4300)]:
    n = int(0.35 * SR); tt = np.arange(n) / SR
    chirp = np.sin(2 * np.pi * (f0 + 900 * np.sin(2 * np.pi * 9 * tt)) * tt) * np.exp(-tt * 9) * np.minimum(1, tt / 0.01)
    add(chirp, tb, 0.025, pan=0.5 if tb % 2 > 1 else -0.5)
n = int(8.0 * SR); tt = np.arange(n) / SR
add(lowpass(rng.standard_normal(n), 400) * np.sin(np.pi * np.minimum(1, tt / 8.0)) * 0.05, 0.0, 1.0)   # soft wind


# risers that lift into each big transition (filtered noise swell + rising tone, cut at the hit)
def riser(dur=1.2, gain=0.12):
    n = int(dur * SR); tt = np.arange(n) / SR; u = tt / dur
    noise = rng.standard_normal(n)
    out = np.zeros(n)
    for s in range(16):
        a, b = s * n // 16, (s + 1) * n // 16
        c = 600 * (8 ** (s / 15))
        out[a:b] = bandpass(noise[max(0, a - 1500):b], c * 0.7, min(c * 1.5, SR / 2 - 100))[-(b - a):]
    tone = np.sin(2 * np.pi * (220 * 2 ** (u * 1.5)) * tt) * 0.25
    return (out * 0.8 + tone) * (u ** 2.2) * gain


for hit, d in [(11.15, 1.4), (17.0, 1.2), (24.45, 1.1), (28.2, 1.3)]:
    add(riser(d, 0.1), film_time(hit) - d, 1.0)

# ── reverb, master ────────────────────────────────────────────────────────────────────
ir_n = int(2.4 * SR)
ir_t = np.arange(ir_n) / SR
irL = rng.standard_normal(ir_n) * np.exp(-ir_t * 2.6)
irR = rng.standard_normal(ir_n) * np.exp(-ir_t * 2.6)
irL, irR = lowpass(irL, 6000), lowpass(irR, 6000)
irL /= np.sqrt(np.sum(irL ** 2)); irR /= np.sqrt(np.sum(irR ** 2))
wetL = fftconvolve(L, irL)[:N]
wetR = fftconvolve(R, irR)[:N]
outL = L * 0.8 + wetL * 0.32
outR = R * 0.8 + wetR * 0.32
fade = np.minimum(1, t_all / 0.8) * np.where(t_all > DUR - 0.8, np.cos(np.clip((t_all - (DUR - 0.8)) / 0.8, 0, 1) * np.pi / 2), 1)
outL *= fade; outR *= fade
# ── narration (Rosa) with ducking ─────────────────────────────────────────────────────
import json, wave as _wave
voice = np.zeros(N)
import sys as _sys
LANG = 'tl' if '--lang' in _sys.argv and _sys.argv[_sys.argv.index('--lang') + 1] == 'tl' else 'en'
nar = Path(__file__).with_name('assets') / ('narration' if LANG == 'en' else 'narration_tl')
cues = json.loads((nar / 'cues.json').read_text(encoding='utf-8')) if (nar / 'cues.json').exists() else []
for c in cues:
    with _wave.open(str(nar / c['file'])) as w:
        v = np.frombuffer(w.readframes(w.getnframes()), '<i2') / 32767.0
    i = int(c['start'] * SR)
    v = v[: max(0, N - i)]
    voice[i:i + len(v)] += v
if cues:
    voice = highpass(voice, 85)
    voice = voice / (np.sqrt(np.mean(voice[np.abs(voice) > 1e-4] ** 2)) + 1e-9) * 0.085   # speech RMS ~ -21 dBFS before the master
    voice = np.tanh(voice * 2.2) / 2.2                                                       # gentle limiting
    rir = rng.standard_normal(int(0.45 * SR)) * np.exp(-np.arange(int(0.45 * SR)) / SR * 11)
    rir = lowpass(rir, 5000); rir /= np.sqrt(np.sum(rir ** 2))
    voice = voice + fftconvolve(voice, rir)[:N] * 0.07
    # duck the music under the voice (50 ms attack, 350 ms release)
    env = np.abs(voice)
    a_att, a_rel = np.exp(-1 / (0.05 * SR)), np.exp(-1 / (0.35 * SR))
    sm = np.zeros(N); acc = 0.0
    for k in range(0, N, 48):
        x = env[k:k + 48].max()
        acc = a_att * acc + (1 - a_att) * x if x > acc else a_rel * acc + (1 - a_rel) * x
        sm[k:k + 48] = acc
    duck = 1 - 0.45 * np.clip(sm / 0.04, 0, 1)
    outL *= duck; outR *= duck
    outL += voice; outR += voice
stereo = np.stack([outL, outR], axis=1)
stereo = np.tanh(stereo * 1.2) / np.tanh(1.2)
stereo *= 0.89 / np.max(np.abs(stereo))
out = Path(__file__).with_name('assets') / ('soundtrack.wav' if LANG == 'en' else 'soundtrack_tl.wav')
import wave
with wave.open(str(out), 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((stereo * 32767).astype('<i2').tobytes())
rms = np.sqrt(np.mean(stereo ** 2))
print(f'wrote {out}  rms {20 * np.log10(rms):.1f} dBFS')
