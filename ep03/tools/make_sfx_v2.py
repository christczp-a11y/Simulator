"""v2 sound mix: ready-made ElevenLabs library sounds (sfx_lib/) + the few v1 drones Chris did not object to (sfx/).
Writes remotion/public/sfx_mix.wav (48 kHz stereo, exactly 107.0 s).  python make_sfx_v2.py"""
import json, pathlib, subprocess, sys
V1B = '--v1b' in sys.argv   # V1 picture (static opening): calm outdoor bed, no horn hits
CAND = '--cand' in sys.argv   # candidate hook: 0.7 s flash close-up first, horn on the hard cut at frame 21
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
LIB, OLD = HERE / 'sfx_lib', HERE / 'sfx'
OUT = HERE / 'remotion' / 'public' / ('sfx_mix_v1b.wav' if V1B else 'sfx_mix_cand.wav' if CAND else 'sfx_mix.wav')
FPS, SR, TOTAL = 30, 48000, 107.0
XF = 6 / FPS

SPACE = {   # per-space acoustics
    'outdoor': 'highpass=f=25,aecho=0.8:0.4:60:0.10',
    'map':     'highpass=f=25,lowpass=f=6000',
    'coach':   'highpass=f=40,lowpass=f=7000,aecho=0.8:0.6:11|23:0.32|0.2',
    'cab':     'highpass=f=30,lowpass=f=9000',
    'tower':   'highpass=f=45,lowpass=f=5500,aecho=0.8:0.5:7|14:0.28|0.16',   # nothing continuous above ~6 kHz
    'distant': 'highpass=f=80,lowpass=f=1800',
    'impact':  'asetrate=48000*0.8,aresample=48000,lowshelf=f=90:g=5,highshelf=f=300:g=3',
    'impact2': 'asetrate=48000*0.88,aresample=48000,lowshelf=f=90:g=3',
    'clock':   'highpass=f=120,aecho=0.8:0.3:9:0.15',
    'dry':     'anull',
}
# beds: (file, start_sec_in_file, start frame, length frames, space, LUFS)
BEDS = [
    *([(LIB / 'country.wav', 2.0, 0, 150, 'outdoor', -27), (LIB / 'freight_pass.wav', 0.0, 0, 150, 'distant', -40)] if V1B else
      [(LIB / 'approach_horn.wav', 8.6, 0, 150, 'outdoor', -20)]),   # s01: V1B = field wind, birds, faint distant rail hum
    (LIB / 'freight_pass.wav', 0.6, 150, 120, 'outdoor', -24),      # s02 trackside, heavy low approach
    (OLD / 's03.mp3', 0, 270, 300, 'map', -30),
    (LIB / 'platform.wav', 3.0, 570, 105, 'outdoor', -29),          # s04 station murmur
    (LIB / 'coach_interior.wav', 0, 675, 180, 'coach', -28),        # s05 + s05a
    (LIB / 'freight_pass.wav', 2.0, 855, 195, 'outdoor', -22),      # s06 loco passing
    (LIB / 'control_room.wav', 1.0, 1050, 210, 'tower', -31),       # s07
    (LIB / 'cab_interior.wav', 2.0, 1260, 195, 'cab', -24),         # s08
    (LIB / 'freight_pass.wav', 3.0, 1455, 120, 'outdoor', -20),     # s09 approach loud
    (OLD / 's10.mp3', 0, 1575, 90, 'map', -34),
    (LIB / 'cab_interior.wav', 9.0, 1665, 90, 'cab', -24),          # s11
    (OLD / 'black.mp3', 0, 2040, 30, 'map', -28),
    (LIB / 'country.wav', 0, 2070, 180, 'outdoor', -30),            # s16 aftermath: wind
    (LIB / 'platform.wav', 12.0, 2070, 180, 'distant', -38),        #      + distant unintelligible commotion
    (LIB / 'control_room.wav', 9.0, 2250, 150, 'tower', -34),       # s17 quieter
    (LIB / 'country.wav', 4.0, 2400, 150, 'outdoor', -30),          # s18 tower exterior
    (LIB / 'cab_interior.wav', 15.0, 2550, 40, 'cab', -26),         # s19 engine running briefly...
    (OLD / 'history.mp3', 0, 2760, 270, 'map', -30),
]
# events: (file, start_sec_in_file, length_sec or None, at frame, space, LUFS)
EVENTS = [
    *([] if V1B else [(LIB / 'loco_horn.wav', 0.0, 1.4, 21 if CAND else 55, 'outdoor', -16)]),          # hook: horn blast inside the first 3 s
    *([] if V1B else [(LIB / 'loco_horn.wav', 0.0, 1.0, 128, 'outdoor', -15)]),         #       second, closer blast right before the cut
    (LIB / 'relay.wav', 0, None, 1095, 'tower', -30), (LIB / 'relay.wav', 0, None, 1172, 'tower', -31),
    (LIB / 'relay.wav', 0, None, 1236, 'tower', -30), (LIB / 'relay.wav', 0, None, 2330, 'tower', -32),
    (LIB / 'phone_ring.wav', 0, None, 1200, 'distant', -34),
    (LIB / 'loco_horn.wav', 0.0, 2.2, 1668, 'cab', -18),            # s11 horn
    (LIB / 'brake_screech.wav', 0.0, None, 1700, 'cab', -20),       # s11 wheels locking
    (LIB / 'brake_screech.wav', 1.2, None, 1755, 'coach', -21),     # s11a felt inside the coach
    (LIB / 'crash_boom.wav', 0.0, None, 1801, 'impact', -13),       # impact slow motion: boom
    (LIB / 'crash_inside.wav', 1.4, None, 1806, 'impact2', -16),    #   crunch + glass
    (LIB / 'crash_derail.wav', 0.0, None, 1840, 'impact', -17),     #   long tearing / grinding steel
    (LIB / 'engine_off.wav', 0.0, None, 2590, 'cab', -25),          # s19 engine winding down
    (OLD / 'clack1.mp3', 0, None, 3045, 'clock', -22), (OLD / 'clack2.mp3', 0, None, 3075, 'clock', -22),
    (OLD / 'clack3.mp3', 0, None, 3105, 'clock', -22), (OLD / 'clack_final.mp3', 0, None, 3112, 'clock', -18),
]


def load(f, ss, dur, af, lufs):
    cmd = ['ffmpeg', '-v', 'error', '-ss', str(ss), '-i', str(f)]
    if dur: cmd += ['-t', str(dur)]
    chain = f'{af},loudnorm=I={lufs}:TP=-2:LRA=20:linear=true,aformat=sample_fmts=flt:channel_layouts=stereo,aresample={SR}'
    raw = subprocess.run(cmd + ['-af', chain, '-f', 'f32le', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def place(mix, x, t0, length=None, fade=XF):
    i0 = int(round(t0 * SR))
    if length is not None:
        n = int(round(length * SR))
        while len(x) < n: x = np.concatenate([x, x])
        x = x[:n].copy()
    k = min(int(fade * SR), len(x) // 2)
    if k:
        ramp = np.linspace(0, 1, k)[:, None]; x[:k] *= ramp; x[-k:] *= ramp[::-1]
    i1 = min(len(mix), i0 + len(x)); mix[i0:i1] += x[: i1 - i0]


def duck(mix, a, b, db, r=0.15):
    g = 10 ** (db / 20); env = np.ones(len(mix), np.float32); i, j, k = int(a * SR), int(b * SR), int(r * SR)
    env[i:j] = g; env[max(0, i - k):i] = np.linspace(1, g, i - max(0, i - k)); env[j:j + k] = np.linspace(g, 1, len(env[j:j + k]))
    mix *= env[:, None]


if __name__ == '__main__':
    mix = np.zeros((int(TOTAL * SR), 2), np.float32)
    for f, ss, f0, nf, sp, lufs in BEDS:
        place(mix, load(f, ss, nf / FPS + XF + 0.1, SPACE[sp], lufs), max(0, f0 / FPS - XF / 2), nf / FPS + XF)
    vo = json.load(open(HERE / 'remotion' / 'src' / 'durations.json'))
    for cue, f0 in (('Q2', 1060), ('Q4', 2260)):                     # keep the quotes clear in the tower
        duck(mix, f0 / FPS - 0.1, f0 / FPS + vo[cue] + 0.2, -3.5)
    duck(mix, 1800 / FPS - 0.05, 2040 / FPS, -12, r=0.05)            # impact: everything else drops away
    for f, ss, dur, f0, sp, lufs in EVENTS:
        place(mix, load(f, ss, dur, SPACE[sp], lufs), f0 / FPS, fade=0.01)
    peak = np.abs(mix).max(); lim = 10 ** (-2 / 20)
    if peak > lim:
        knee = lim * 0.85
        mix = np.where(np.abs(mix) > knee, np.sign(mix) * (knee + (lim - knee) * np.tanh((np.abs(mix) - knee) / (lim - knee))), mix)
    (mix * 32767).astype('<i2').tofile(HERE / 'mix.raw')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 's16le', '-ar', str(SR), '-ac', '2', '-i', str(HERE / 'mix.raw'), str(OUT)], check=True)
    (HERE / 'mix.raw').unlink()
    print('wrote', OUT, len(mix) / SR, 's; peak before limit', round(20 * np.log10(peak + 1e-9), 1), 'dBFS')
