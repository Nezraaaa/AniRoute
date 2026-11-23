"""Female voice-over for the AniRoute film (Microsoft neural voice en-PH-RosaNeural, via edge-tts).

Only the narration lines below are sent to the speech service. Each line is placed at its cue time; if a
line runs longer than its slot it is gently time-compressed (never more than 12%).

    python make_narration.py   -> assets/narration/*.wav + assets/narration/cues.json
"""
import asyncio
import json
import subprocess
import wave
from pathlib import Path

import edge_tts

import sys

LANG = 'tl' if '--lang' in sys.argv and sys.argv[sys.argv.index('--lang') + 1] == 'tl' else 'en'
VOICE = {'en': 'en-PH-RosaNeural', 'tl': 'fil-PH-AngeloNeural'}[LANG]      # English: female · Tagalog: male
OUT = Path(__file__).with_name('assets') / ('narration' if LANG == 'en' else 'narration_tl')
OUT.mkdir(parents=True, exist_ok=True)
RATE = {'en': '-2%', 'tl': '+0%'}[LANG]

# (cue start s, latest end s, line), film time
LINES_EN = [
    (1.4, 4.7, 'Every harvest deserves to arrive fresh.'),
    (7.8, 11.6, "Tell AniRoute what you're carrying, and where it's going."),
    (14.1, 16.6, 'It finds the real roads to your market,'),
    (16.85, 20.6, 'and scores each one for time, crop, and road safety.'),
    (20.95, 23.5, 'Choose the gentlest road for your harvest.'),
    (24.0, 27.2, 'Then follow it, every kilometer of the way.'),
    (28.7, 32.6, "Your phone's camera spots cracked, damaged road, in real time."),
    (32.9, 36.4, 'Confirm with a tap, and AniRoute finds a safer way.'),
    (37.2, 39.85, 'Protect the harvest, on the way to market.'),
]
LINES_TL = [
    (1.2, 4.9, 'Bawat ani ay dapat dumating nang sariwa.'),
    (7.6, 11.8, 'Sabihin sa AniRoute kung ano ang dala mo, at kung saan ito pupunta.'),
    (13.9, 16.6, 'Hinahanap nito ang totoong daan papunta sa palengke,'),
    (16.8, 20.7, 'at sinusuri ang bawat isa: oras, uri ng ani, at kaligtasan ng daan.'),
    (20.95, 23.6, 'Piliin ang pinakamaingat na daan para sa iyong ani.'),
    (24.0, 27.4, 'Pagkatapos, sundan ito, bawat kilometro ng biyahe.'),
    (28.6, 32.7, 'Nakikita ng camera ng telepono mo ang bitak at sirang kalsada, agad-agad.'),
    (32.9, 36.6, 'Kumpirmahin sa isang tap, at hahanap ang AniRoute ng mas ligtas na daan.'),
    (37.1, 39.9, 'Protektahan ang ani, hanggang sa palengke.'),
]
LINES = LINES_TL if LANG == 'tl' else LINES_EN


async def synth(i, text):
    mp3 = OUT / f'line{i}.mp3'
    await edge_tts.Communicate(text, VOICE, rate=RATE, pitch='+0Hz').save(str(mp3))
    return mp3


def duration(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


async def main():
    cues = []
    for i, (start, end, text) in enumerate(LINES):
        mp3 = await synth(i, text)
        raw = OUT / f'line{i}_raw.wav'
        # trim leading/trailing silence, 48 kHz mono
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(mp3), '-af',
                        'silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse',
                        '-ar', '48000', '-ac', '1', str(raw)], check=True)
        d = duration(raw)
        slot = end - start
        tempo = min(1.12, d / slot) if d > slot else 1.0
        final = OUT / f'line{i}.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(raw), '-af', f'atempo={tempo:.4f}', '-ar', '48000', '-ac', '1', str(final)], check=True)
        fd = duration(final)
        cues.append({'file': final.name, 'start': start, 'duration': round(fd, 3), 'text': text, 'tempo': round(tempo, 3)})
        flag = '  (over slot!)' if start + fd > end + 0.05 else ''
        print(f'{start:5.2f}s  {fd:4.2f}s  x{tempo:.2f}  {text}{flag}')
        raw.unlink(); mp3.unlink()
    (OUT / 'cues.json').write_text(json.dumps(cues, indent=1), encoding='utf-8')


asyncio.run(main())
