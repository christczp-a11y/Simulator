import React from 'react';
import {AbsoluteFill, Audio, Img, Sequence, staticFile, useCurrentFrame} from 'remotion';
import {EndCard} from './EndCard';
import {Dial, History, Illustrative, Labels, Subtitles} from './Overlays';
import {CUES, START, VO, shotAt} from './timeline';
import have from './have.json';

const H = have as Record<string, number[]>;
const pick = (shot: string, n: number) => {
	const a = H[shot]; if (!a || a.length === 0 || a.includes(n)) return n;
	return a.reduce((b, x) => (Math.abs(x - n) < Math.abs(b - n) ? x : b), a[0]);
};
const full: React.CSSProperties = {position: 'absolute', left: 0, top: 0, width: 1080, height: 1920};

export const Episode: React.FC<{frameBase: string; ui: boolean; sfx?: boolean}> = ({frameBase, ui, sfx}) => {
	const f = useCurrentFrame();
	const [shot, k] = shotAt(f);
	let bg: React.ReactNode;
	if (shot === 'black') bg = <AbsoluteFill style={{background: '#000'}} />;
	else if (shot === 'history') bg = <History k={k} />;
	else if (shot === 'end') bg = <EndCard clockBase={`${frameBase}/s20`} frame={Math.min(k, 149)} clockFrame={pick('s20', Math.min(k, 149) + 1)} />;
	else bg = <Img src={`${frameBase}/${shot}/${shot}_${String(pick(shot, k + 1)).padStart(4, '0')}.png`} style={full} />;
	return (
		<AbsoluteFill style={{background: '#000'}}>
			{bg}
			{CUES.filter((c) => VO[c.id]).map((c) => (
				<Sequence key={c.id} from={START[c.shot] + c.at} durationInFrames={Math.ceil(VO[c.id] * 30) + 2}><Audio src={staticFile(`vo/${c.id}.mp3`)} /></Sequence>
			))}
			{sfx ? <Audio src={staticFile('sfx_mix.wav')} /> : null}
			{ui ? <><Labels f={f} /><Dial f={f} /><Illustrative f={f} /><Subtitles f={f} /></> : null}
		</AbsoluteFill>
	);
};
