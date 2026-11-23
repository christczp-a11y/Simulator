"""ElevenLabs sound-generation + per-space treatment + mix -> remotion/public/sfx_mix.wav (48 kHz stereo, 107.0 s).
python make_sfx.py      (cached: files already in sfx/ are not regenerated; prompts listed in sfx/prompts.json)
Key: elevenlab_api_key in C:\\YouTubeNeuropolis\\api-keys.env (never printed)."""
import json, pathlib, subprocess, urllib.request
import numpy as np

ENV = r'C:\YouTubeNeuropolis\api-keys.env'
HERE = pathlib.Path(__file__).resolve().parent
SFX = HERE / 'sfx'; SFX.mkdir(exist_ok=True)
OUT = HERE / 'remotion' / 'public' / 'sfx_mix.wav'
FPS, SR, TOTAL = 30, 48000, 107.0
XF = 6 / FPS                                    # crossfade at cuts

# space treatments (ffmpeg -af)
SPACE = {
    'outdoor': 'highpass=f=25,aecho=0.8:0.4:60:0.12',
    'map':     'highpass=f=25,lowpass=f=6000',
    'coach':   'highpass=f=40,lowpass=f=9000,aecho=0.8:0.6:11|23:0.35|0.22',
    'cab':     'highpass=f=30',
    'signal':  'highpass=f=80,treble=g=3:f=4000,aecho=0.8:0.5:7|14:0.3|0.18',
    'impact':  'asetrate=48000*0.72,aresample=48000,highshelf=f=300:g=6',
    'clock':   'highpass=f=120,aecho=0.8:0.3:9:0.15',
}
# (name, prompt, generated seconds, start frame, length frames, space, target LUFS)
BEDS = [
    ('s01', 'outdoor farmland beside a railway track, gentle wind, distant birds, faint electric rail hum slowly rising', 5.6, 0, 150, 'outdoor', -26),
    ('s02', 'outdoor railway trackside, heavy deep low rumble of an approaching train rising, rail hum, wind', 4.6, 150, 120, 'outdoor', -24),
    ('s03', 'very low dark ambient drone, subtle and cinematic, no melody, no rhythm', 10.6, 270, 300, 'map', -30),
    ('s04', 'outdoor train station platform, unintelligible crowd murmur, diesel locomotive engine revving and pulling away', 4.1, 570, 105, 'outdoor', -24),
    ('s05', 'inside a stationary passenger train coach, enclosed ventilation fan hum, quiet passenger murmurs, seat creaks', 6.6, 675, 180, 'coach', -26),
    ('s06', 'diesel locomotive exterior accelerating, steel wheels over rail joints clacking faster and faster', 6.9, 855, 195, 'outdoor', -23),
    ('s07', 'small railway signal control room interior, electrical equipment hum, fluorescent light buzz, relay clicks, distant telephone ringing', 7.4, 1050, 210, 'signal', -26),
    ('s08', 'inside a diesel locomotive cab, close engine low rumble, cab vibration, dry', 6.9, 1260, 195, 'cab', -24),
    ('s09', 'standing beside the track, train wheels on rails growing very loud, heavy ground rumble approaching fast', 4.6, 1455, 120, 'outdoor', -21),
    ('s10', 'almost silent low room tone with a faint distant rhythmic rail pulse', 3.6, 1575, 90, 'map', -34),
    ('s11', 'inside a diesel locomotive cab, engine rumble, then a loud emergency brake air release hiss', 3.6, 1665, 90, 'cab', -22),
    ('s11a', 'inside a moving passenger coach braking hard, steel wheel squeal, coach body resonance, luggage sliding', 2.0, 1755, 45, 'coach', -21),
    ('black', 'low deep rumble slowly decaying into silence', 2.2, 2040, 30, 'map', -28),
    ('s16', 'outdoor accident aftermath, wind, distant unintelligible commotion and voices, hot metal ticking', 6.6, 2070, 180, 'outdoor', -26),
    ('s17', 'quiet small control room, electrical hum, paper rustling, pen writing on paper', 5.6, 2250, 150, 'signal', -29),
    ('s18', 'outside a small rural railway building, wind, distant road traffic', 5.6, 2400, 150, 'outdoor', -27),
    ('s19', 'diesel locomotive engine shutting down, then near silence with metal ticking as it cools', 7.6, 2550, 210, 'cab', -27),
    ('history', 'very low dark ambient drone, slow, cinematic, no melody', 9.6, 2760, 270, 'map', -30),
]
# impact slow motion (s12 starts 1800): 3-4 events, slowed/pitched down by 'impact'
EVENTS = [
    ('imp_boom', 'deep heavy cinematic impact boom of two trains colliding, sub bass', 3.0, 1801, 'impact', -16),
    ('imp_tear', 'massive steel tearing and screeching, train metal being ripped apart', 4.0, 1835, 'impact', -18),
    ('imp_fold', 'train coach crumpling and folding, heavy steel bending and crunching', 4.0, 1925, 'impact', -18),
    ('imp_glass', 'many train windows shattering, glass breaking and falling', 2.5, 1990, 'impact', -20),
    ('clack1', 'single mechanical flip clock flap clack, close', 0.6, 3030 + 15, 'clock', -22),
    ('clack2', 'single mechanical flip clock flap clack, close', 0.6, 3030 + 45, 'clock', -22),
    ('clack3', 'single mechanical flip clock flap clack, close', 0.6, 3030 + 75, 'clock', -22),
    ('clack_final', 'one heavy mechanical flip clock clack, final and solid', 0.9, 3030 + 82, 'clock', -18),
]


def key():
    for line in open(ENV, encoding='utf-8'):
        if line.lower().startswith('elevenlab_api_key='):
            return line.split('=', 1)[1].strip()
    raise SystemExit('elevenlab_api_key missing')


def gen(name, prompt, secs):
    f = SFX / f'{name}.mp3'
    if not f.exists():
        body = json.dumps({'text': prompt, 'duration_seconds': max(0.5, min(22, secs)), 'prompt_influence': 0.6}).encode()
        req = urllib.request.Request('https://api.elevenlabs.io/v1/sound-generation', data=body,
                                     headers={'xi-api-key': key(), 'Content-Type': 'application/json'})
        f.write_bytes(urllib.request.urlopen(req, timeout=180).read())
        print('generated', name, flush=True)
    return f


def load(f, af, lufs):
    """decode -> treatment -> loudness-normalise -> float32 (n,2) at 48 kHz"""
    chain = f'{af},loudnorm=I={lufs}:TP=-3:LRA=20:linear=true,aformat=sample_fmts=flt:channel_layouts=stereo,aresample={SR}'
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(f), '-af', chain, '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def place(mix, x, t0, length=None, fade=XF):
    i0 = int(round(t0 * SR))
    if length is not None:
        n = int(round(length * SR))
        if len(x) < n:                          # loop-pad short beds with a crossfade
            x = np.concatenate([x, x[: n - len(x)]])
        x = x[:n].copy()
    k = min(int(fade * SR), len(x) // 2)
    if k:
        ramp = np.linspace(0, 1, k)[:, None]
        x[:k] *= ramp; x[-k:] *= ramp[::-1]
    i1 = min(len(mix), i0 + len(x))
    mix[i0:i1] += x[: i1 - i0]


if __name__ == '__main__':
    json.dump({n: p for n, p, *_ in BEDS + EVENTS}, open(SFX / 'prompts.json', 'w'), indent=1)
    mix = np.zeros((int(TOTAL * SR), 2), np.float32)
    for name, prompt, secs, f0, nf, space, lufs in BEDS:
        x = load(gen(name, prompt, secs), SPACE[space], lufs)
        t0 = max(0, f0 / FPS - XF / 2)
        place(mix, x, t0, nf / FPS + XF)        # beds overlap XF at every cut
    for name, prompt, secs, f0, space, lufs in EVENTS:
        x = load(gen(name, prompt, secs), SPACE[space], lufs)
        place(mix, x, f0 / FPS, fade=0.005)
    # duck the signal-tower beds 3.5 dB under the quotes Q2 (s07) and Q4 (s17) so the words stay clear
    vo = json.load(open(HERE / 'remotion' / 'src' / 'durations.json'))
    for cue, f0 in (('Q2', 1050 + 10), ('Q4', 2250 + 10)):
        a, b = f0 / FPS - 0.1, f0 / FPS + vo[cue] + 0.2
        env = np.ones(len(mix), np.float32); g = 10 ** (-3.5 / 20); r = int(0.15 * SR)
        i, j = int(a * SR), int(b * SR)
        env[i:j] = g
        env[i - r:i] = np.linspace(1, g, r); env[j:j + r] = np.linspace(g, 1, r)
        mix *= env[:, None]
    peak = np.abs(mix).max()
    lim = 10 ** (-2 / 20)
    if peak > lim:                              # soft clip only the overs
        mix = np.where(np.abs(mix) > lim * 0.9, np.sign(mix) * (lim * 0.9 + (np.abs(mix) - lim * 0.9) * 0.2), mix)
        mix = np.clip(mix, -lim, lim)
    (mix * 32767).astype('<i2').tofile(SFX / 'mix.raw')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 's16le', '-ar', str(SR), '-ac', '2', '-i', str(SFX / 'mix.raw'), str(OUT)], check=True)
    (SFX / 'mix.raw').unlink()
    print('wrote', OUT, len(mix) / SR, 's, peak before limit', round(20 * np.log10(peak + 1e-9), 1), 'dBFS')
