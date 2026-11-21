"""mix2.py — sound track built only from the ElevenLabs clips in audio2/ (n_*.wav, 48 kHz stereo).
Nothing is synthesised. Real-time parts use the clips as they are; in the slow-motion part the clips are played slower (varispeed:
longer and lower, as film sound editors do for slow motion). Otherwise: trim, place on a picture event, level, fade, pan, peak limiter. Cue times come from src/data.json.
Usage: python3 mix2.py [out.wav]   (prints the cue list and writes audio2/cues.txt)"""
import numpy as np, json, wave, sys
from scipy.ndimage import minimum_filter1d, uniform_filter1d
SR = 48000; D = json.load(open('src/data.json')); F = D['frames']; FPS = D['fps']; N = len(F); L = int(N / FPS * SR)
first = lambda ph: next(i for i, f in enumerate(F) if f['phase'] == ph)
P = {ph: first(ph) for ph in ('freeze', 'rewind', 'hold', 'real', 'black', 'end')}
CONTACT = next(i for i, f in enumerate(F) if f['t'] >= 0)                       # nose touches (slow motion)
SLOW0 = next(i for i, f in enumerate(F) if f['slow'] > 1.02)                    # slow motion starts
BELLY = next(i for i, f in enumerate(F) if f['phase'] == 'main' and f['t'] >= 12.0)
PEAKG = max(range(P['freeze']), key=lambda i: F[i]['g'])
HIT = P['real'] + next(k for k in range(30) if F[P['real'] + k]['t'] >= 0)      # nose touches (real speed)
T = lambda fr: fr / FPS; S = lambda sec: int(round(sec * SR)); db = lambda x: 10 ** (x / 20.0)

def clip(n, a=0.0, b=None):
    w = wave.open(f'audio2/{n}.wav'); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, 2).astype(np.float64) / 32768
    x = x[:len(x) - S(0.03)]                                                    # the decoded mp3s end on a click
    return x[S(a):S(b) if b else None].copy()
def fade(x, i=0.004, o=0.004):
    x = x.copy(); ni, no = min(S(i), len(x)), min(S(o), len(x))
    if ni: x[:ni] *= (np.linspace(0, 1, ni) ** 2)[:, None]
    if no: x[-no:] *= (np.linspace(1, 0, no) ** 2)[:, None]
    return x
peak = lambda x, d: x / np.abs(x).max() * db(d)
M = np.zeros((L, 2)); U = np.zeros((L, 2)); CUES = []        # M: sounds of the scene (get the outdoor space), U: interface sounds (stay dry)
def put(name, x, sec, what, pan=0.5, until=None, ui=False):
    """place clip x at `sec`; `until` cuts it there (with a short fade)"""
    if until is not None and sec + len(x) / SR > until: x = fade(x[:max(1, S(until - sec))], 0, 0.02)
    g = np.array([np.cos(pan * np.pi / 2), np.sin(pan * np.pi / 2)]) * np.sqrt(2)   # constant-power pan
    s = S(sec); e = min(L, s + len(x))
    if e > s: (U if ui else M)[s:e] += x[:e - s] * g
    CUES.append((sec, sec + len(x) / SR, name, what))

FRZ = T(P['freeze']); t_slow = T(SLOW0); t_c = T(CONTACT)
# Slow motion, the way film sound editors do it: the real sound is played slower, so it gets longer and lower (varispeed, like slowing a tape).
# The picture goes down to 1/500, which would push every sound below hearing, so (as in films) the sound follows the picture down only to
# FLOOR and each event gets its own rate: 2 to 3 times slower, about 1 to 1.6 octaves down. Real-time parts are untouched.
def vari(x, rate):                                                              # constant rate: rate 0.35 = 2.9 times longer, 1.5 octaves lower
    pos = np.arange(0, len(x) - 1, rate); i = pos.astype(int); fr = (pos - i)[:, None]; return x[i] * (1 - fr) + x[i + 1] * fr
def vari_curve(x, rate):                                                        # rate changes over time (one value per output sample)
    pos = np.concatenate([[0], np.cumsum(rate)[:-1]]); pos = pos[pos < len(x) - 1]; i = pos.astype(int); fr = (pos - i)[:, None]; return x[i] * (1 - fr) + x[i + 1] * fr
FLOOR = 0.22
# 1. real time approach, then cockpit roar and warning slow down WITH the picture (the film's own slow-motion factor drives the playback rate)
n_ramp = S(t_slow + 5.0); slow = np.interp(np.arange(n_ramp) / SR * FPS, np.arange(N), [max(f['slow'], 1.0) if f['phase'] == 'main' else 1.0 for f in F])
rate = np.maximum(1.0 / slow, FLOOR); tt = np.arange(n_ramp) / SR
env = np.interp(tt, [0, 0.03, t_slow, t_slow + 0.9, t_c, t_c + 0.4], [0, 1, 1, db(-5), db(-11), 0])
cp = np.concatenate([clip('n_cockpit', 0.3), clip('n_cockpit', 0.3)]); al = np.concatenate([clip('n_alarm')] * 3)
x = vari_curve(cp, rate); put('n_cockpit', x * env[:len(x), None] * db(-3), 0, 'cockpit wind and engines; slows down and drops in pitch with the picture')
x = vari_curve(al, rate); put('n_alarm', x * env[:len(x), None] * db(-6), 0, 'ground proximity warning; slows down with the picture')
put('n_flaproll', fade(peak(clip('n_flaproll', 0.2, 2.9), -11), 0.02, 0.15), 0, 'countdown digits rolling', ui=True)
fr2 = clip('n_flaproll', 0.3, 2.6); r2 = np.maximum(1.0 / np.interp(np.arange(S(2.2)) / SR * FPS + SLOW0, np.arange(N), [max(f['slow'], 1.0) for f in F]), 0.3)
put('n_flaproll', fade(peak(vari_curve(fr2, r2), -11), 0.1, 1.0), t_slow - 0.05, 'countdown digits rolling, slowing with the picture', ui=True)
# 2. into the slow motion: transition element, then one low drone as the bed
put('n_slowdown', fade(peak(clip('n_slowdown', 0.10), -7), 0.01, 0.2), t_slow, 'slow-motion transition')
put('n_bullet', fade(clip('n_bullet', 0.6) * db(2), 0.6, 2.0), t_slow + 0.1, 'bullet-time low drone')
put('n_bullet', fade(clip('n_bullet', 1.0) * db(2), 2.0, 0.02), 10.3, 'bullet-time low drone, second pass', until=FRZ)
# 3. At 1/500 the whole crash is 32 ms of real time, so there are only a few events and each one is long. Four sounds, one per event,
#    each a real-speed recording played slower; nothing else (no single debris hits, no repeated layers).
put('n2_nose_b', fade(peak(vari(clip('n2_nose_b', 0.015), 0.30), 1), 0.003, 2.5), t_c, 'EVENT 1, nose hits the ground: one crash played 3.3 times slower, rings until the belly hits', until=T(BELLY) + 2.5)
put('n_impact_slow', fade(peak(clip('n_impact_slow', 0.11), -6), 0.002, 0.5), t_c, 'low boom under the nose hit')
put('n2_belly', fade(peak(vari(clip('n2_belly', 0.07), 0.30), 0), 0.003, 1.5), T(BELLY), 'EVENT 2, belly hits the ground: one slam played 3.3 times slower')
put('n2_earth_blast', fade(peak(vari(clip('n2_earth_blast', 0.06), 0.28), -4), 0.4, 2.5), T(BELLY) + 0.2, 'the earth it throws up, 3.6 times slower (tail of event 2)', until=T(PEAKG) + 3.0)
tear = clip('n2_metal_tear')
put('n2_metal_tear', fade(vari(tear[S(0.19):S(2.6)], 0.34) * db(-1), 0.003, 1.2), T(PEAKG), 'EVENT 3, peak g: the cockpit structure tears, one take played 3 times slower', pan=0.52, until=FRZ)
put('n_glass', fade(vari(clip('n_glass', 1.0, 3.6), 0.40) * db(-8), 0.3, 0.3), T(436), 'EVENT 4, the windshield breaks: 2.5 times slower', pan=0.55, until=FRZ)
sw = clip('n2_bullet', 0.3, 8.0); put('n2_bullet', fade(sw * db(-8), 0.3, 0.02), FRZ - 3.1, 'swell into the freeze', until=FRZ)
# 6. the countdown: one stopwatch tick per millisecond once the picture is slow enough to count them (tick and tock alternate)
tick = [fade(peak(clip('n_tick', 0.085, 0.20), -9), 0.002, 0.03), fade(peak(clip('n_tick', 0.315, 0.43), -9), 0.002, 0.03)]
last = -99; k = 0; nt = 0; t_first = None
for i in range(SLOW0, P['freeze']):
    a, b = int(F[i - 1]['left'] * 1000 + 1e-6), int(F[i]['left'] * 1000 + 1e-6)
    if a == b: continue
    gap = i - last; last = i
    if gap < 3: continue
    x = tick[k % 2] * db(-12 if gap < 6 else -9 if gap < 12 else -7); s = S(T(i)); U[s:s + len(x)] += x; k += 1; nt += 1; t_first = t_first or T(i)
CUES.append((t_first, FRZ, 'n_tick', f'countdown: {nt} ticks, one per millisecond'))
# 7. freeze on 0.000: everything stops, one low hit; rewind; silence on the hold
# Outdoor space. The clips are dry, close recordings; an open field has no room reflections, only the sound coming back late from far
# objects and a long soft decay. That response is taken from a generated recording of one gunshot in an open field (ir_field_a): the
# shot itself is removed, what follows it is what the field does to any sound. The scene sounds are convolved with it and mixed under
# the dry sound. In the slow motion the response is played slower as well (its tail gets longer and lower, like everything else).
from scipy.signal import fftconvolve
ir = clip('ir_field_a'); o = int(np.argmax(np.abs(ir).max(1))); tail = fade(ir[o + S(0.015):o + S(3.3)], 0.005, 0.5)
def space(x, h, pre):                                                           # wet signal only, same loudness scale as x for a steady noise
    h = h / np.sqrt((h ** 2).sum(0)).mean(); y = np.stack([fftconvolve(x[:, c], h[:, c]) for c in (0, 1)], 1); return np.concatenate([np.zeros((S(pre), 2)), y])
nF = S(FRZ); send = M[:nF] * np.interp(np.arange(nF) / SR, [0, t_c - 0.06, t_c], [db(-9), db(-9), 1.0])[:, None]   # inside the closed cockpit only a little
wet = space(send, vari(tail, 0.6), 0.09)[:nF] * db(-7); M[:nF] += wet
CUES.append((0, FRZ, 'ir_field_a', 'outdoor space on every scene sound: open-field echo and decay, slowed with the picture'))
M[:nF] += U[:nF]; M[S(FRZ) - S(0.02):S(FRZ)] *= (np.linspace(1, 0, S(0.02)) ** 2)[:, None]; M[S(FRZ):] = 0; U[:] = 0
put('n_stop', fade(peak(clip('n_stop'), -4), 0.001, 0.3), FRZ, 'freeze: low boom, everything else cuts', until=T(P['rewind']))
put('n2_stop', fade(peak(clip('n2_stop', 0.13), -1), 0.001, 0.2), FRZ, 'freeze: hard stop hit', until=T(P['rewind']))
put('n_flap', fade(peak(clip('n_flap', 0.12), -5), 0.002, 0.1), FRZ, 'freeze: the clock lands on 0.0000')
rw = clip('n_rewind'); put('n_rewind', fade(rw * db(-3), 0.03, 0.002), T(P['hold']) - len(rw) / SR + 0.01, 'tape rewind; ends where the picture stops')
# 8. real speed: cockpit and warning at full level, the crash on the contact frame, cut to silence with the end card
t_r = T(P['real']); t_cut = T(HIT) + 1 / FPS
put('n_cockpit', fade(clip('n_cockpit', 2.0, 2.0 + t_cut - t_r) * db(2), 0.015, 0.03), t_r, 'cockpit at real speed')
put('n_alarm', fade(clip('n_alarm', 0.5, 0.5 + t_cut - t_r) * db(-2), 0.015, 0.03), t_r, 'warning at real speed')
put('n_crash', fade(peak(clip('n_crash'), -0.5)[:S(T(P['end']) - T(HIT))], 0.0, 0.05), T(HIT), 'the crash at real speed, through the black frames')
a_, b_ = S(t_r), S(T(P['end'])); wet = space(M[a_:b_].copy(), tail, 0.06) * db(-5)       # the crash rolls away across the field, under the end card
wet = fade(wet[:S(T(P['end']) - t_r + 2.6)], 0, 2.0); e_ = min(L, a_ + len(wet)); M[a_:e_] += wet[:e_ - a_]
CUES.append((t_r, t_r + len(wet) / SR, 'ir_field_a', 'outdoor echo of the real-speed crash, rolls on under the end card'))
# 9. end card
put('n_pop', fade(peak(clip('n_pop', 0.012), -5), 0.001, 0.2), T(P['end']), 'subscribe pops')
put('n_flap', fade(peak(clip('n_flap', 0.12), -10), 0.002, 0.1), T(P['end'] + 11), 'flip clock lands on 0.032')

# master: gain, then a look-ahead peak limiter (5 ms look-ahead, ~60 ms release) to -1 dBFS
MASTER = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
M *= db(MASTER); thr = db(-1.7); pk = np.abs(M).max(1); need = np.minimum(1.0, thr / np.maximum(pk, 1e-9))
g = minimum_filter1d(need, S(0.005) * 2 + 1); g = np.minimum(g, uniform_filter1d(minimum_filter1d(g, S(0.06), origin=-S(0.03) + 1), S(0.005)))
M *= np.minimum(g, need)[:, None]
out = sys.argv[1] if len(sys.argv) > 1 else 'audio2/mix2.wav'
w = wave.open(out, 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(M, -1, 1) * 32767).astype(np.int16).tobytes()); w.close()
CUES.sort(); open('audio2/cues.txt', 'w').write('\n'.join('%6.2f-%6.2f s  frame %3d  %-14s %s' % (a, b, round(a * FPS), n, wh) for a, b, n, wh in CUES) + '\n')
print(open('audio2/cues.txt').read())
print('frames: slow', SLOW0, 'contact', CONTACT, 'belly', BELLY, 'peak g', PEAKG, 'hit', HIT, P, '| limiter max reduction %.1f dB, active %.1f %% of samples' % (20 * np.log10(g.min()), 100 * (need < 1).mean()))
from scipy.signal import butter, sosfilt
H = sosfilt(butter(4, 300, 'high', fs=SR, output='sos'), M, axis=0)
win = S(0.5); print('phone band (>300 Hz, analysis only):', ' '.join('%.0f' % (20 * np.log10(max(np.sqrt((H[i:i + win] ** 2).mean()), 1e-5))) for i in range(0, L - win + 1, win)))
print('rms per half second (dB):', ' '.join('%.0f' % (20 * np.log10(max(np.sqrt((M[i:i + win] ** 2).mean()), 1e-5))) for i in range(0, L - win + 1, win)))
