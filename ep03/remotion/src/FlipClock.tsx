import React from 'react';
import {DISPLAY, INK, PAPER, TEXT, ease} from './theme';

/** One split-flap digit. `prog` 0..1 is how far the flap carrying the new digit has fallen. */
const Flap: React.FC<{cur: string; prev: string; prog: number; w: number; h: number}> = ({cur, prev, prog, w, h}) => {
	const half = h / 2;
	const glyph = (ch: string, top: boolean, shade: number): React.CSSProperties => ({
		position: 'absolute', left: 0, top: top ? 0 : -half, width: w, height: h, lineHeight: `${h}px`, textAlign: 'center',
		fontFamily: DISPLAY, fontSize: h * 0.86, color: PAPER, filter: `brightness(${shade})`, paddingTop: h * 0.035,
	});
	const leaf = (top: boolean): React.CSSProperties => ({
		position: 'absolute', left: 0, top: top ? 0 : half, width: w, height: half, overflow: 'hidden',
		background: top ? 'linear-gradient(#222120, #161615)' : 'linear-gradient(#121211, #1b1a19)',
		borderRadius: top ? '9px 9px 0 0' : '0 0 9px 9px', backfaceVisibility: 'hidden',
	});
	const flipping = prog < 1 && cur !== prev;
	const a = flipping ? ease(prog) : 1;
	return (
		<div style={{position: 'relative', width: w, height: h, perspective: h * 3.2}}>
			<div style={leaf(true)}><div style={glyph(cur, true, 1)}>{cur}</div></div>
			<div style={leaf(false)}><div style={glyph(flipping ? prev : cur, false, 0.94)}>{flipping ? prev : cur}</div></div>
			{flipping && a < 0.5 ? (
				<div style={{...leaf(true), transformOrigin: '50% 100%', transform: `rotateX(${-180 * a}deg)`}}><div style={glyph(prev, true, 1 - a * 1.1)}>{prev}</div></div>
			) : null}
			{flipping && a >= 0.5 ? (
				<div style={{...leaf(false), transformOrigin: '50% 0%', transform: `rotateX(${180 * (1 - a)}deg)`}}><div style={glyph(cur, false, 0.45 + a * 0.5)}>{cur}</div></div>
			) : null}
			<div style={{position: 'absolute', left: 0, top: half - 2, width: w, height: 4, background: '#050505'}} />
			<div style={{position: 'absolute', left: -3, top: half - 9, width: 7, height: 18, borderRadius: 3, background: '#2b2a28'}} />
			<div style={{position: 'absolute', right: -3, top: half - 9, width: 7, height: 18, borderRadius: 3, background: '#2b2a28'}} />
		</div>
	);
};

/** `values[0]` is the text now, `values[k]` the text k frames ago (same length). A digit that changed n frames ago is n/FL of the way through its flip. */
export const FlipClock: React.FC<{values: string[]; h?: number; flip?: number}> = ({values, h = 168, flip = 5}) => {
	const now = values[0];
	const w = h * 0.7;
	return (
		<div style={{display: 'inline-flex', alignItems: 'center', gap: h * 0.06, padding: h * 0.11, borderRadius: h * 0.16, background: 'linear-gradient(#2a2927, #0d0d0c)', boxShadow: `0 ${h * 0.05}px ${h * 0.28}px rgba(0,0,0,.55), inset 0 2px 0 rgba(255,255,255,.10), inset 0 -2px 0 rgba(0,0,0,.6)`}}>
			{now.split('').map((ch, i) => {
				if (ch === '.' || ch === ':') {
					return <div key={i} style={{width: h * 0.16, height: h, position: 'relative'}}><div style={{position: 'absolute', bottom: h * 0.1, left: 0, width: h * 0.16, height: h * 0.16, borderRadius: h, background: PAPER}} /></div>;
				}
				let n = 0;
				while (n + 1 < values.length && values[n + 1][i] === ch) n++;
				const changed = n + 1 < values.length;
				const prev = changed ? values[n + 1][i] : ch;
				return <Flap key={i} cur={ch} prev={prev} prog={changed ? (n + 1) / flip : 1} w={w} h={h} />;
			})}
		</div>
	);
};

export const Tag: React.FC<{children: React.ReactNode; size?: number; invert?: boolean; style?: React.CSSProperties}> = ({children, size = 44, invert = true, style}) => (
	<div style={{display: 'inline-block', fontFamily: TEXT, fontWeight: 800, fontSize: size, letterSpacing: '-0.03em', lineHeight: 1, padding: `${size * 0.2}px ${size * 0.34}px ${size * 0.26}px`, background: invert ? PAPER : INK, color: invert ? INK : PAPER, borderRadius: size * 0.16, ...style}}>{children}</div>
);
