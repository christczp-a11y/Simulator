import React from 'react';
import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';
import {INK, PAPER, TEXT, back, clamp, ease} from './theme';

export const RED = '#D7261E';
const LAND = 82;   // frame where the last leaf lands on 00:00 (flipclock.py: 75 + 7)
const full: React.CSSProperties = {position: 'absolute', left: 0, top: 0, width: 1080, height: 1920};

/** Shot 20: the Blender flip clock (transparent PNGs) over the channel's halftone sweep, then the subscribe call. */
export const EndCard: React.FC<{clockBase: string; frame?: number; clockFrame?: number}> = ({clockBase, frame, clockFrame}) => {
	const cf = useCurrentFrame();
	const f = frame ?? cf;
	const k = f - LAND;
	const drift = f / 150;
	// the landing gives the whole card a short, damped kick (same spring as the in-shot camera shakes)
	const kick = k >= 0 ? Math.exp(-k / 4) * Math.sin(k * 1.9) * 7 : 0;
	const pop = back(clamp((k - 6) / 10));
	const sub = clamp((k - 6) / 4);
	const line = ease(clamp((k - 14) / 10));
	const tail = clamp((k - 22) / 8);
	return (
		<AbsoluteFill style={{background: PAPER, overflow: 'hidden'}}>
			<Img src={staticFile('ht_ep2_end.png')} style={{position: 'absolute', left: -110 - 40 * drift, top: -190 - 70 * drift, width: 1300, height: 2300, transform: `scale(${1.02 + 0.03 * drift})`}} />
			<div style={{...full, transform: `translateY(${-250 + kick}px)`}}>
				<Img src={`${clockBase}/s20_${String(clockFrame ?? f + 1).padStart(4, '0')}.png`} style={{...full, filter: 'drop-shadow(0 26px 30px rgba(0,0,0,.28)) drop-shadow(0 6px 8px rgba(0,0,0,.22))'}} />
			</div>
			<div style={{position: 'absolute', left: 0, top: 1060, width: 1080, textAlign: 'center', mixBlendMode: 'difference', opacity: sub}}>
				<div style={{fontFamily: TEXT, fontWeight: 800, fontSize: 196, letterSpacing: '-0.055em', lineHeight: 1, color: '#fff', transform: `scale(${0.6 + 0.4 * pop})`}}>subscribe</div>
			</div>
			<div style={{position: 'absolute', left: 540 - 300 * line, top: 1290, width: 600 * line, height: 10, background: RED}} />
			<div style={{position: 'absolute', left: 0, top: 1340, width: 1080, textAlign: 'center', fontFamily: TEXT, fontWeight: 700, fontSize: 46, letterSpacing: '-0.02em', color: INK, opacity: tail, transform: `translateY(${(1 - ease(tail)) * 14}px)`}}>
				the last seconds of every disaster
			</div>
		</AbsoluteFill>
	);
};
