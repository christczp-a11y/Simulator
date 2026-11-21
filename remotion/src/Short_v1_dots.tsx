import React from 'react';
import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';
import raw from './data.json';
import {FlipClock, Tag} from './FlipClock';
import {DISPLAY, INK, PAPER, TEXT, back, clamp, ease} from './theme';

type Fr = {phase: string; src: number; t: number; slow: number; left: number; kmh: number; g: number; srcf?: number; p?: number};
const FR = raw.frames as Fr[];
const HAVE = raw.have as number[];
const first = (ph: string) => FR.findIndex((d) => d.phase === ph);
const START = {freeze: first('freeze'), rewind: first('rewind'), hold: first('hold'), real: first('real'), black: first('black'), end: first('end')};
const CONTACT = FR.findIndex((d) => d.t >= 0);
// largest g so far in the current forward run (main film, or the real-speed replay)
const PEAK: number[] = [];
FR.forEach((d, i) => { PEAK[i] = d.phase === 'main' || d.phase === 'freeze' ? Math.max(d.g, i ? PEAK[i - 1] : 0) : d.phase === 'real' ? Math.max(d.g, FR[i - 1].phase === 'real' ? PEAK[i - 1] : 0) : d.g; });

const haveSet = new Set(HAVE);
const nearest = (n: number) => { if (haveSet.has(n) || HAVE.length === 0) return n; let b = HAVE[0]; for (const h of HAVE) if (Math.abs(h - n) < Math.abs(b - n)) b = h; return b; };
const full: React.CSSProperties = {position: 'absolute', left: 0, top: 0, width: 1080, height: 1920};

const Footage: React.FC<{f: number; base: string}> = ({f, base}) => {
	const d = FR[f];
	if (d.src < 0) return <AbsoluteFill style={{background: '#000'}} />;
	const url = (n: number) => `${base}/s_${String(nearest(Math.round(clamp(n, 0, 613)))).padStart(5, '0')}.png`;
	if (d.phase === 'rewind') {
		// black-and-white halftone while the film runs backwards: a soft dot screen is added to the picture and the sum is pushed to pure black or white, so dots grow where the picture is dark
		const sf = d.srcf as number; const v = Math.abs(sf - (FR[f - 1].srcf ?? 521)); const k = f - START.rewind; const edge = clamp(Math.min(k + 1, START.hold - f) / 3);
		return (
			<AbsoluteFill style={{background: '#000'}}>
				<svg width="0" height="0" style={{position: 'absolute'}}>
					<filter id="lift" colorInterpolationFilters="sRGB">
						<feColorMatrix type="saturate" values="0" />
						<feComponentTransfer><feFuncR type="gamma" exponent="0.5" amplitude="1.1" /><feFuncG type="gamma" exponent="0.5" amplitude="1.1" /><feFuncB type="gamma" exponent="0.5" amplitude="1.1" /></feComponentTransfer>
					</filter>
				</svg>
				<div style={{...full, background: '#fff', filter: 'contrast(24)', isolation: 'isolate'}}>
					<div style={{...full, filter: 'url(#lift)'}}>
						<Img src={url(sf)} style={full} />
						<Img src={url(Math.min(521, sf + v * 0.4))} style={{...full, opacity: 0.5}} />
						<Img src={url(Math.min(521, sf + v * 0.8))} style={{...full, opacity: 0.33}} />
					</div>
					<div style={{position: 'absolute', left: -700, top: -300, width: 2500, height: 2500, transform: 'rotate(45deg)', opacity: 0.5, backgroundImage: 'radial-gradient(circle at center, #fff 0%, #9a9a9a 38%, #000 74%)', backgroundSize: '12px 12px'}} />
				</div>
				<div style={{...full, background: PAPER, mixBlendMode: 'multiply'}} />
				<div style={{...full, top: ((f * 613) % 1700), height: 5, background: 'rgba(0,0,0,.55)'}} />
				<div style={{...full, top: ((f * 947 + 300) % 1800), height: 14, background: 'rgba(0,0,0,.35)'}} />
				{edge < 1 ? <Img src={url(sf)} style={{...full, opacity: 1 - edge}} /> : null}
			</AbsoluteFill>
		);
	}
	const fz = d.phase === 'freeze' ? (f - START.freeze) / 30 : 0;
	const hit = d.phase === 'real' && d.t > 0;
	return (
		<AbsoluteFill style={{background: '#000'}}>
			<Img src={url(d.src)} style={{...full, transform: `scale(${1 + 0.05 * ease(fz) + (hit ? 0.06 : 0)})`}} />
			{d.phase === 'freeze' ? <div style={{...full, background: '#000', opacity: 0.5 * ease(fz * 3)}} /> : null}
		</AbsoluteFill>
	);
};

const label: React.CSSProperties = {fontFamily: TEXT, fontWeight: 800, letterSpacing: '-0.02em', color: PAPER, lineHeight: 1};

const Stat: React.FC<{name: string; value: string; unit?: string; sub: string; hot?: boolean; w: number; s: number; keep: boolean}> = ({name, value, unit, sub, hot, w, s, keep}) => {
	const L = (px: number, min: number) => (keep ? Math.max(min, px * s) : px * s);
	return (
	<div style={{width: w}}>
		<div style={{...label, fontSize: L(36, 30), opacity: 0.85}}>{name}</div>
		<div style={{display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 8, height: 116 * s}}>
			<span style={{fontFamily: DISPLAY, fontSize: 112 * s, lineHeight: `${116 * s}px`, color: hot ? INK : PAPER, background: hot ? PAPER : 'transparent', padding: hot ? '0 12px' : 0, marginLeft: hot ? -12 : 0, borderRadius: 10}}>{value}</span>
			{unit ? <span style={{...label, fontSize: L(34, 28)}}>{unit}</span> : null}
		</div>
		<div style={{...label, fontWeight: 700, fontSize: L(30, 27), opacity: 0.78, marginTop: 10}}>{sub}</div>
	</div>
	);
};

const Hud: React.FC<{f: number; s: number; keep: boolean}> = ({f, s, keep}) => {
	const L = (px: number, min: number) => (keep ? Math.max(min, px * s) : px * s);
	const ws = keep ? Math.max(s, 0.78) : s;                      // column widths cannot shrink below what the kept labels need
	const rowH = 23 + L(36, 30) * 1.2 + 8 + 116 * s + 10 + L(30, 27) * 1.2;
	const d = FR[f];
	const txt = (k: number) => Math.min(FR[Math.max(0, f - k)].left, 9.9999).toFixed(4);
	const values = [0, 1, 2, 3, 4, 5].map(txt);
	const slow = d.phase === 'rewind' ? '◀◀' : d.phase === 'freeze' ? '0×' : `${d.slow >= 100 ? Math.round(d.slow / 5) * 5 : Math.round(d.slow)}×`;
	const slowSub = d.phase === 'rewind' ? 'rewinding' : d.phase === 'freeze' ? 'paused' : d.slow <= 1 ? 'real time' : 'slower than real';
	const g = d.g < 9.95 ? d.g.toFixed(1) : String(Math.round(d.g));
	const peak = PEAK[f];
	const since = f - CONTACT;
	return (
		<AbsoluteFill>
			<Img src={staticFile('ht_top.png')} style={{position: 'absolute', left: 0, top: 0, width: 1080, opacity: 0.85}} />
			<div style={{position: 'absolute', left: 0, top: 1549 - rowH - 112, width: 1080, height: 720, background: 'linear-gradient(rgba(0,0,0,0), rgba(0,0,0,.42) 28%, rgba(0,0,0,.42))'}} />
			<Img src={staticFile('ht_bottom.png')} style={{position: 'absolute', left: 0, top: 1160, width: 1080}} />
			<div style={{position: 'absolute', left: 56, top: 236}}>
				<div style={{...label, fontSize: L(60, 42), marginBottom: 22 * s}}>lights out in</div>
				<div style={{display: 'flex', alignItems: 'flex-end', gap: 16}}>
					<FlipClock values={values} h={156 * s} />
					<div style={{...label, fontSize: L(44, 32), paddingBottom: 18 * s}}>sec</div>
				</div>
			</div>
			{d.phase === 'main' && since >= 0 && since < 66 ? (
				<div style={{position: 'absolute', left: 56, top: 236 + 324 * s, transformOrigin: '0 50%', transform: `scale(${back(since / 7) * s}) rotate(-2deg)`, opacity: clamp((66 - since) / 8)}}>
					<Tag size={56}>ground contact</Tag>
				</div>
			) : null}
			<div style={{position: 'absolute', left: 56, top: 1549 - rowH, width: 840 * ws}}>
				<div style={{height: 3, background: PAPER, opacity: 0.9, marginBottom: 20}} />
				<div style={{display: 'flex'}}>
					<Stat w={310 * ws} s={s} keep={keep} name="speed" value={String(Math.round(d.kmh))} unit="km/h" sub={`${Math.round(d.kmh * 0.621371)} mph`} />
					<Stat w={258 * ws} s={s} keep={keep} name="g-force" value={g} unit="g" sub={peak >= 100 && d.phase !== 'rewind' && d.phase !== 'hold' ? `peak ${Math.round(peak)} g` : 'at the seat'} hot={d.g >= 100} />
					<Stat w={272 * ws} s={s} keep={keep} name="slow motion" value={slow} sub={slowSub} hot={d.phase === 'hold' || d.phase === 'real'} />
				</div>
			</div>
		</AbsoluteFill>
	);
};

const Freeze: React.FC<{k: number}> = ({k}) => (
	<AbsoluteFill>
		<div style={{position: 'absolute', left: 56, top: 690, width: 968, opacity: clamp(k / 3)}}>
			<div style={{...label, fontSize: 76}}>nose to here</div>
			<div style={{display: 'flex', alignItems: 'baseline', gap: 18, transformOrigin: '0 60%', transform: `scale(${back(k / 8)})`}}>
				<span style={{fontFamily: DISPLAY, fontSize: 380, lineHeight: '400px', color: PAPER}}>0.032</span>
				<span style={{...label, fontSize: 84}}>sec</span>
			</div>
			<div style={{marginTop: 6, transform: 'rotate(-2deg)', transformOrigin: '0 50%', opacity: clamp((k - 6) / 3)}}><Tag size={60}>faster than a blink</Tag></div>
		</div>
	</AbsoluteFill>
);

const End: React.FC<{k: number}> = ({k}) => {
	const pop = back(k / 9);
	return (
		<AbsoluteFill style={{background: INK}}>
			<Img src={staticFile('ht_end.png')} style={{...full, transform: `scale(${1.5 - 0.45 * ease(k / 9) + k * 0.0006})`, opacity: clamp(k / 3)}} />
			<Img src={staticFile('ht_burst.png')} style={{...full, transform: `scale(${0.4 + 2.6 * ease(k / 8)})`, opacity: clamp(1.2 - k / 7)}} />
			<div style={{position: 'absolute', left: 0, top: 610, width: 1080, textAlign: 'center', opacity: clamp((k - 10) / 5)}}>
				<FlipClock values={['0.032', '0.032']} h={132} />
				<div style={{...label, fontSize: 46, marginTop: 24}}>seconds. that was all.</div>
			</div>
			<div style={{position: 'absolute', left: 0, top: 930, width: 1080, textAlign: 'center', transform: `scale(${pop})`}}>
				<div style={{...label, fontSize: 212, letterSpacing: '-0.05em', textShadow: `0 0 40px ${INK}, 0 0 14px ${INK}`}}>subscribe</div>
			</div>
			<div style={{position: 'absolute', left: 150, top: 1210, opacity: clamp((k - 14) / 5), transform: `translate(${-Math.sin(k / 4.5) * 9}px, ${Math.sin(k / 4.5) * 9}px) rotate(42deg)`}}>
				<svg width="125" height="221" viewBox="0 0 96 170"><path d="M48 6 V152 M10 112 L48 156 L86 112" fill="none" stroke={PAPER} strokeWidth="14" strokeLinecap="round" strokeLinejoin="round" /></svg>
			</div>
		</AbsoluteFill>
	);
};

export const Short: React.FC<{frameBase: string; ui: boolean; uiScale?: number; keepLabels?: boolean}> = ({frameBase, ui, uiScale = 1, keepLabels = true}) => {
	const s = uiScale;
	const f = useCurrentFrame();
	const d = FR[f];
	const hud = ui && ['main', 'freeze', 'rewind', 'hold', 'real'].includes(d.phase);
	const tagAt: React.CSSProperties = {position: 'absolute', left: 56, top: 590, transformOrigin: '0 50%'};
	return (
		<AbsoluteFill style={{background: '#000'}}>
			<Footage f={f} base={frameBase} />
			{hud ? <Hud f={f} s={s} keep={keepLabels} /> : null}
			{ui && d.phase === 'freeze' ? <Freeze k={f - START.freeze} /> : null}
			{ui && d.phase === 'rewind' ? <div style={{...tagAt, top: 236 + 354 * s, transform: `scale(${back((f - START.rewind) / 6) * s}) rotate(-2deg)`}}><Tag size={84}>◀◀ rewind</Tag></div> : null}
			{ui && (d.phase === 'hold' || d.phase === 'real') ? <div style={{...tagAt, top: 236 + 354 * s, transform: `scale(${back((f - START.hold) / 5) * s}) rotate(-2deg)`}}><Tag size={84}>real speed ▶</Tag></div> : null}
			{ui && d.phase === 'end' ? <End k={f - START.end} /> : null}
		</AbsoluteFill>
	);
};
