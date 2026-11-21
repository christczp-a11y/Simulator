"""mix.py — builds the sound track (audio/mix.wav, 48 kHz stereo) from the ElevenLabs effects in audio/ and the per-frame data in src/data.json.
Cues are tied to the picture: the flip-clock clicks fall on the frames where the third decimal of the countdown changes, the sub rumble follows the seat g curve."""
import numpy as np, json, wave
from scipy.signal import butter, sosfilt
SR = 48000; D = json.load(open('src/data.json')); F = D['frames']; FPS = D['fps']; N = len(F); L = int(N / FPS * SR)
first = lambda ph: next(i for i, f in enumerate(F) if f['phase'] == ph); T = lambda fr: fr / FPS; S = lambda sec: int(round(sec * SR))
P = {ph: first(ph) for ph in ('freeze', 'rewind', 'hold', 'real', 'black', 'end')}
CONTACT = next(i for i, f in enumerate(F) if f['t'] >= 0); SLOW0 = next(i for i, f in enumerate(F) if f['slow'] > 1.02)
def load(n):
    w = wave.open(f'audio/{n}.wav'); return np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, 2).astype(np.float64) / 32768
db = lambda x: 10 ** (x / 20.0)
def norm(a, peak_db): return a / np.abs(a).max() * db(peak_db)
def fade(a, i=0.0, o=0.0):
    a = a.copy(); ni, no = S(i), S(o)
    if ni: a[:ni] *= np.linspace(0, 1, ni)[:, None] ** 2
    if no: a[-no:] *= np.linspace(1, 0, no)[:, None] ** 2
    return a
def lp(a, hz): return sosfilt(butter(4, hz, 'low', fs=SR, output='sos'), a, axis=0)
def hp(a, hz): return sosfilt(butter(2, hz, 'high', fs=SR, output='sos'), a, axis=0)
def resample(a, rate):                              # play `a` (looped) at a time-varying rate (one value per output sample)
    pos = np.concatenate([[0], np.cumsum(rate)[:-1]]) % (len(a) - 1); i = pos.astype(int); fr = (pos - i)[:, None]; return a[i] * (1 - fr) + a[i + 1] * fr
M = np.zeros((L, 2))
def put(a, sec, gain=1.0):
    s = S(sec); e = min(L, s + len(a))
    if e > s: M[s:e] += a[:e - s] * gain

amb, drop, slowmo, rewind, crash, pop, flap = (load(n) for n in ('amb', 'drop', 'slowmo', 'rewind', 'crash', 'pop', 'flap'))
amb = norm(amb, -5); pop = pop[max(0, np.argmax(np.abs(pop).max(1) > 0.1 * np.abs(pop).max()) - 240):]   # start the hit on its attack, so that it lands on the frame
flap = flap[np.argmax(np.abs(flap).max(1) > 0.02) - 48:][:S(0.12)]; flap = fade(norm(hp(flap, 900), -3), 0, 0.05)

# 1. approach in real time, then the same sound is slowed down with the picture: playback rate follows the film's own slow-motion factor
t1 = T(P['freeze']); n1 = S(t1); slow = np.interp(np.arange(n1) / SR * FPS, np.arange(N), [max(f['slow'], 1.0) if f['phase'] == 'main' else 1.0 for f in F])
rate = np.maximum(1.0 / slow, 0.06); bed = resample(amb, rate)                       # below ~4 octaves down it just becomes rumble, so the rate is floored
g = np.interp(np.arange(n1) / SR * FPS, [0, SLOW0, CONTACT, CONTACT + 40, P['freeze']], [1.0, 1.0, db(-9), db(-15), db(-12)])
cut = np.interp(np.arange(n1) / SR * FPS, [0, SLOW0, CONTACT, P['freeze']], [16000, 16000, 1400, 900])
out = np.zeros_like(bed); blk = 2048                                                    # low-pass that closes as time slows (block-wise)
for b in range(0, n1, blk):
    seg = bed[max(0, b - blk):b + blk]; y = lp(seg, float(cut[b])); out[b:b + blk] = y[-min(blk, n1 - b) - 0:][:min(blk, n1 - b)] if b == 0 else y[blk:blk + min(blk, n1 - b)]
put(fade(out * g[:, None], 0.03, 0.05), 0)
put(fade(norm(drop, -6), 0.05, 0.3), T(SLOW0) - 0.15)

# 2. slow-motion bed: the generated metal groans, rising towards the end, and a sub rumble whose level is the seat g
t0 = T(CONTACT) - 0.5; sm = norm(slowmo, -4)[:S(t1 - t0)]; ramp = np.interp(np.arange(len(sm)) / SR, [0, 0.8, len(sm) / SR - 3, len(sm) / SR], [0, db(-5), db(-3), db(0)])
put(fade(sm * ramp[:, None], 0, 0.04), t0)
tt = np.arange(n1) / SR; gcurve = np.interp(tt * FPS, np.arange(N), [f['g'] if f['phase'] == 'main' else 0 for f in F]) / D['peak_g']
sub = (np.sin(2 * np.pi * 41 * tt) + 0.5 * np.sin(2 * np.pi * 61.5 * tt + 1.0)) * np.clip(gcurve, 0, 1) ** 0.8 * db(-9)
put(fade(np.stack([sub, sub], 1), 0, 0.04), 0)

boom = lp(resample(norm(crash, -1), np.full(S(t1 - T(CONTACT)), 0.125)), 500)                  # the impact itself, three octaves down: what a 125-times slow-motion of it would roughly be
put(fade(boom, 0.01, 0.3), T(CONTACT), db(-7))
# 3. flip-clock clicks: one whenever the third decimal changes, louder when they come one at a time
rng = np.random.default_rng(3); last = -99
for i in range(1, N):
    if F[i]['phase'] in ('black', 'end', 'freeze'): continue
    a, b = int(F[i - 1]['left'] * 1000 + 1e-6), int(F[i]['left'] * 1000 + 1e-6)
    if a == b: continue
    gap = i - last; last = i; lvl = -25 if gap <= 2 else -19 if gap <= 6 else -13
    r = rng.uniform(0.9, 1.12); k = resample(flap, np.full(int(len(flap) / r), r)); pan = rng.uniform(0.35, 0.65)
    put(k * np.array([1 - pan, pan]) * 2, T(i), db(lvl))

# 4. the stop on 0.032 s: everything cuts, one low hit
put(fade(norm(pop, -4), 0, 0.25), t1 - 0.02)
# 5. rewind
rl = S(T(P['hold']) - T(P['rewind']) + 0.02); rw = norm(rewind, -6)[-rl:]; put(fade(rw, 0.03, 0.02), T(P['rewind']))   # the riser ends where the picture stops
# 6. real speed: full cockpit noise for the 0.43 s that are left, the impact on the frame where the nose touches, then nothing
ra = fade(amb[S(1.0):S(1.0) + S(T(P['black']) - T(P['real']))] * db(3), 0.02, 0.01); put(ra, T(P['real']))
hit = P['real'] + next(k for k in range(20) if F[P['real'] + k]['t'] >= 0)
cr = norm(crash, -0.5)[:S(T(P['black']) - T(hit) + 0.14)]; put(fade(cr, 0, 0.12), T(hit))
# 7. end card
put(fade(norm(pop, -3), 0, 0.2), T(P['end']) - 0.01); put(flap, T(P['end'] + 11), db(-8))

M = np.tanh(M * 1.15) / np.tanh(1.15); M = M / max(1.0, np.abs(M).max() / db(-1.0))
w = wave.open('audio/mix.wav', 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(M, -1, 1) * 32767).astype(np.int16).tobytes()); w.close()
win = S(0.25); print('length %.2f s' % (L / SR), 'contact frame', CONTACT, 'slow from', SLOW0, 'hit', hit, P)
print('level per quarter second (dB):', ' '.join('%.0f' % (20 * np.log10(max(np.sqrt((M[i:i + win] ** 2).mean()), 1e-5))) for i in range(0, L - win, win)))
