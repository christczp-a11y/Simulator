import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {INK, PAPER, TEXT, DISPLAY, back, clamp, ease} from './theme';
import {CUES, Cue, IMPACT, ILLUSTRATIVE, LABELS, START, cueDur, shotAt} from './timeline';

export const RED = '#D7261E';
export const GREY = '#8A8A8A';
const SHADOW = 'drop-shadow(0 3px 10px rgba(0,0,0,.28))';

// ---------------------------------------------------------------- text helpers
/** split a cue into on-screen chunks of at most ~`max` characters, at word boundaries, preferring punctuation */
const chunks = (t: string, max = 34): string[] => {
	if (t.includes('|')) return t.split('|');
	const out: string[] = []; let cur = '';
	for (const w of t.split(/\s+/)) {
		const nxt = cur ? cur + ' ' + w : w;
		if (nxt.length > max && cur) { out.push(cur); cur = w; } else cur = nxt;
		if (/[.,]$/.test(w) && cur.length > max * 0.55) { out.push(cur); cur = ''; }
	}
	if (cur) out.push(cur);
	return out;
};
/** colour the emphasised phrases red */
const Rich: React.FC<{text: string; emph?: string[]}> = ({text, emph = []}) => {
	let parts: {s: string; e: boolean}[] = [{s: text, e: false}];
	for (const p of emph) {
		parts = parts.flatMap((x) => {
			if (x.e) return [x];
			const words = p.split(' ');
			// emphasis may straddle a chunk boundary: match the longest leading/trailing piece present
			for (let n = words.length; n > 0; n--) for (let i = 0; i + n <= words.length; i++) {
				const sub = words.slice(i, i + n).join(' '); const k = x.s.indexOf(sub);
				if (k >= 0 && sub.length > 3) return [{s: x.s.slice(0, k), e: false}, {s: sub, e: true}, {s: x.s.slice(k + sub.length), e: false}];
			}
			return [x];
		});
	}
	return <>{parts.map((x, i) => x.e ? <span key={i} style={{color: RED}}>{x.s}</span> : <span key={i}>{x.s}</span>)}</>;
};

// ---------------------------------------------------------------- plates
/** A paper (or ink) plate whose right end dissolves into a halftone dot fade, like the channel banner. */
const Plate: React.FC<{ink?: boolean; children: React.ReactNode; pad?: number; h?: number}> = ({ink, children, pad = 22}) => (
	<div style={{display: 'inline-flex', alignItems: 'stretch'}}>
		<div style={{background: ink ? '#0E0E0E' : PAPER, color: ink ? PAPER : INK, padding: `${pad * 0.62}px ${pad}px ${pad * 0.78}px`, borderRadius: '6px 0 0 6px'}}>{children}</div>
		<div style={{width: 120, backgroundImage: `url(${staticFile(ink ? 'ht_fade_ink.png' : 'ht_fade_paper.png')})`, backgroundSize: '220px 100%', backgroundRepeat: 'no-repeat'}} />
	</div>
);

const SUB_Y = 1290;   // bottom block: above the Shorts caption/buttons zone (~1500+), clear of the right-hand action column
export const Subtitles: React.FC<{f: number}> = ({f}) => {
	const [shot] = shotAt(f);
	if (shot === 'history' || shot === 'end' || shot === 'black') return null;
	const live = CUES.find((c) => { const s = START[c.shot] + c.at; return f >= s && f < s + cueDur(c) + 6; });
	if (!live) return null;
	const s0 = START[live.shot] + live.at; const dur = cueDur(live);
	const cs = chunks(live.text, live.voice === 'quote' ? 30 : 32);
	const words = cs.map((c) => c.split(' ').length); const tot = words.reduce((a, b) => a + b, 0);
	let t = s0, idx = 0;
	for (let i = 0; i < cs.length; i++) { const d = (dur * words[i]) / tot; if (f < t + d) { idx = i; break; } t += d; idx = i; }
	const k = f - t; const inn = ease(clamp(k / 5));
	const q = live.voice === 'quote';
	return (
		<AbsoluteFill style={{filter: SHADOW}}>
			<div style={{position: 'absolute', left: 56, top: SUB_Y - (q ? 58 : 0)}}>
				{q ? (
					<div style={{display: 'inline-block', marginBottom: 12, padding: '7px 12px 8px', background: PAPER, borderRadius: 4, fontFamily: TEXT, fontWeight: 800, fontSize: 21, letterSpacing: '0.1em', color: INK, opacity: clamp((f - s0) / 6)}}>
						<span style={{color: RED}}>●</span>&nbsp; PROSECUTION STATEMENT · TRANSLATED · VOICED
					</div>
				) : null}
				<div style={{opacity: inn, transform: `translateY(${(1 - inn) * 10}px)`}}>
					<Plate ink={q}>
						<div style={{fontFamily: TEXT, fontWeight: 800, fontSize: Math.min(58, 1500 / cs[idx].length), letterSpacing: '-0.025em', lineHeight: 1.08, whiteSpace: 'nowrap'}}>
							{q && idx === 0 ? '“' : ''}<Rich text={cs[idx]} emph={live.emph} />{q && idx === cs.length - 1 ? '”' : ''}
						</div>
					</Plate>
				</div>
			</div>
		</AbsoluteFill>
	);
};

// ---------------------------------------------------------------- top-left context labels
const TOP = 132;
export const Labels: React.FC<{f: number}> = ({f}) => {
	const [shot, k] = shotAt(f);
	const L = LABELS.find((l) => l.shot === shot);
	if (!L) return null;
	const n = L.text.length; const shown = Math.floor(clamp((k - 4) / 14) * n);   // typed on, like a teleprinter
	return (
		<div style={{position: 'absolute', left: 48, top: TOP, filter: SHADOW}}>
			<Plate ink pad={16}>
				<div style={{fontFamily: TEXT, fontWeight: 700, fontSize: 26, letterSpacing: '0.08em', whiteSpace: 'nowrap'}}>
					{L.text.slice(0, shown)}<span style={{opacity: 0}}>{L.text.slice(shown)}</span>
				</div>
			</Plate>
		</div>
	);
};

export const Illustrative: React.FC<{f: number}> = ({f}) => {
	const [shot, k] = shotAt(f);
	if (!ILLUSTRATIVE.has(shot)) return null;
	return (
		<div style={{position: 'absolute', right: 48, top: TOP + 150, opacity: clamp(k / 6), fontFamily: TEXT, fontWeight: 800, fontSize: 19, letterSpacing: '0.14em', color: PAPER, padding: '6px 10px 7px', border: `2px solid ${PAPER}`, borderRadius: 4, filter: SHADOW}}>
			ILLUSTRATIVE
		</div>
	);
};

// ---------------------------------------------------------------- the second hand (brand mark): counts the last ticks down to the impact
const ANCH: [number, number][] = [[START.s01, 9], [START.s09, 2], [START.s11, 1], [IMPACT, 0]];
const spring = (k: number) => Math.exp(-k / 2.2) * Math.cos(k * 1.9) * 0.18;   // overshoot and settle, like a quartz movement
const ticksLeft = (f: number): number => {
	if (f >= IMPACT) return -spring(f - IMPACT) * 0;   // the hand stops dead on the impact
	for (let i = 0; i + 1 < ANCH.length; i++) {
		const [fa, a] = ANCH[i], [fb, b] = ANCH[i + 1];
		if (f < fb) {
			const per = (fb - fa) / (a - b);
			const done = Math.max(0, Math.floor((f - fa) / per));
			const k = f - fa - done * per;
			return a - done - (done > 0 || i > 0 ? spring(k) : 0);
		}
	}
	return 0;
};
export const Dial: React.FC<{f: number}> = ({f}) => {
	const [shot] = shotAt(f);
	if (f > START.black + 30 || shot === 'black') return null;
	const left = f >= IMPACT ? 0 : ticksLeft(f);
	const hit = f >= IMPACT;
	const ang = -6 * left;
	const R = 54;
	const appear = clamp((f - 10) / 8);
	return (
		<div style={{position: 'absolute', right: 48, top: TOP, width: 2 * R + 8, height: 2 * R + 8, opacity: appear, transform: `scale(${0.85 + 0.15 * back(appear)})`, filter: SHADOW}}>
			<svg width={2 * R + 8} height={2 * R + 8} viewBox={`${-R - 4} ${-R - 4} ${2 * R + 8} ${2 * R + 8}`}>
				<circle r={R} fill={PAPER} />
				{Array.from({length: 60}, (_, i) => {
					const a = (i * 6 * Math.PI) / 180; const major = i % 5 === 0; const r0 = major ? R - 11 : R - 6;
					const live = i >= 60 - 9 || i === 0; // the last ten seconds are drawn darker
					return <line key={i} x1={Math.sin(a) * r0} y1={-Math.cos(a) * r0} x2={Math.sin(a) * (R - 3)} y2={-Math.cos(a) * (R - 3)} stroke={live ? INK : '#C9CBCD'} strokeWidth={major ? 3 : 1.6} strokeLinecap="round" />;
				})}
				<g transform={`rotate(${ang})`}>
					<line x1={0} y1={12} x2={0} y2={-R + 7} stroke={hit ? RED : INK} strokeWidth={3.2} strokeLinecap="round" />
				</g>
				<circle r={4.5} fill={hit ? RED : INK} />
			</svg>
		</div>
	);
};

// ---------------------------------------------------------------- history card (V10): typographic, on the halftone sweep, inverted
export const History: React.FC<{k: number}> = ({k}) => {
	const line = (at: number) => ({opacity: ease(clamp((k - at) / 7)), transform: `translateY(${(1 - ease(clamp((k - at) / 9))) * 22}px)`});
	return (
		<AbsoluteFill style={{background: INK, overflow: 'hidden'}}>
			<Img src={staticFile('ht_ep2_end.png')} style={{position: 'absolute', left: -110 + 30 * (k / 270), top: -190, width: 1300, height: 2300, transform: 'rotate(180deg)', filter: 'invert(1)', opacity: 0.55}} />
			<div style={{position: 'absolute', left: 72, top: 430, right: 72}}>
				<div style={{...line(6), fontFamily: TEXT, fontWeight: 700, fontSize: 40, letterSpacing: '0.08em', color: GREY}}>24 OCT 2009 · EL-AYYAT</div>
				<div style={{...line(14), fontFamily: DISPLAY, fontSize: 300, lineHeight: 1, color: PAPER, marginTop: 18}}>17 years</div>
				<div style={{...line(40), fontFamily: TEXT, fontWeight: 800, fontSize: 84, letterSpacing: '-0.04em', lineHeight: 1.04, color: PAPER, marginTop: 24}}>same place.<br />same kind of crash.</div>
				<div style={{...line(150), fontFamily: TEXT, fontWeight: 800, fontSize: 84, letterSpacing: '-0.04em', lineHeight: 1.04, color: PAPER, marginTop: 60}}>
					at least <span style={{fontFamily: DISPLAY, fontSize: 150, color: RED, letterSpacing: 0}}>50</span> dead.
				</div>
			</div>
			<div style={{position: 'absolute', left: 72, bottom: 250, fontFamily: TEXT, fontWeight: 600, fontSize: 24, letterSpacing: '0.06em', color: PAPER, background: INK, padding: '6px 10px', opacity: clamp((k - 170) / 10)}}>SOURCE: 2009 EL AYYAT RAILWAY ACCIDENT, OFFICIAL TOLL</div>
		</AbsoluteFill>
	);
};
