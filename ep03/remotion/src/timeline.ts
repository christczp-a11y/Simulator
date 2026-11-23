// Shot order and lengths (frames @30fps) — must match shots.py / flipclock.py
export const SHOTS: [string, number][] = [
	['s01', 150], ['s02', 120], ['s03', 300], ['s04', 105], ['s05', 90], ['s05a', 90], ['s06', 195], ['s07', 210], ['s08', 195],
	['s09', 120], ['s10', 90], ['s11', 90], ['s11a', 45], ['s12', 120], ['s13', 60], ['s14', 60], ['black', 30], ['s16', 180],
	['s17', 150], ['s18', 150], ['s19', 210], ['history', 270], ['end', 180],
];
export const START: Record<string, number> = {};
let acc = 0;
for (const [s, n] of SHOTS) { START[s] = acc; acc += n; }
export const TOTAL = acc;
export const shotAt = (f: number): [string, number] => {
	for (const [s, n] of SHOTS) { if (f < START[s] + n) return [s, f - START[s]]; }
	return ['end', f - START.end];
};

export type Cue = {id: string; voice: 'daniel' | 'quote'; shot: string; at: number; text: string; emph?: string[]; dur?: number};
// `at` = frames after the shot starts; `dur` (frames) is replaced by the real VO length once audio exists (audio/durations.json)
export const CUES: Cue[] = [
	{id: 'V1', voice: 'daniel', shot: 's01', at: 8, text: 'A train is stopped on the track.|Behind it, another one is coming.'},
	{id: 'V2', voice: 'daniel', shot: 's02', at: 6, text: 'Its automatic train control|has been switched off.', emph: ['switched off.']},
	{id: 'V3', voice: 'daniel', shot: 's03', at: 2, text: 'Sunday, November 8th.|Fifty kilometres south of Cairo.|Train 2010, Cairo to Aswan,|stands between Kafr Ammar and Al-Raqqa.'},
	{id: 'V4', voice: 'daniel', shot: 's04', at: 0, text: 'On the same line,|train 134 leaves El-Ayyat.', emph: ['same line,']},
	{id: 'V5', voice: 'daniel', shot: 's05', at: 12, text: 'In the last coach of train 2010,|passengers wait for it to move again.'},
	{id: 'Q1', voice: 'quote', shot: 's06', at: 10, text: 'Injured passengers said|the train ran at high speed|from the moment it left|El-Ayyat station.', emph: ['high speed']},
	{id: 'Q2', voice: 'quote', shot: 's07', at: 10, text: 'The two station staff admitted|they did not monitor|the control panel|for signal tower 10.', emph: ['did not monitor']},
	{id: 'Q3', voice: 'quote', shot: 's08', at: 8, text: 'Technical inspection confirmed|the driver had switched off|the automatic control system|before the collision.', emph: ['switched off']},
	{id: 'V6', voice: 'daniel', shot: 's16', at: 20, text: 'Seven people were killed.|More than a hundred were injured.', emph: ['Seven people were killed.']},
	{id: 'Q4', voice: 'quote', shot: 's17', at: 10, text: 'The duty officer|altered the signal log|to cover up his negligence.', emph: ['altered the signal log']},
	{id: 'V7', voice: 'daniel', shot: 's18', at: 20, text: 'Both station staff are in custody.'},
	{id: 'V8', voice: 'daniel', shot: 's19', at: 10, text: 'The assistant driver is still|too badly injured to be questioned.'},
	{id: 'V9', voice: 'daniel', shot: 's19', at: 134, text: 'The investigation has not concluded.'},
	{id: 'V10', voice: 'daniel', shot: 'history', at: 12, text: 'Seventeen years ago,|at the same place,|another train ran into a stopped one.|At least fifty people died.', emph: ['At least fifty people died.']},
];
import durations from './durations.json';
export const VO = durations as Record<string, number>;   // seconds per cue id, written by make_vo after ElevenLabs generation
export const WPS = 2.6;   // Daniel, ~155 wpm — placeholder until real durations exist
export const cueDur = (c: Cue) => c.dur ?? (VO[c.id] ? Math.round(VO[c.id] * 30) : Math.round((c.text.replace(/\|/g, ' ').split(/\s+/).length / WPS + 0.3) * 30));

// Top-left context labels and illustrative tags
export const LABELS: {shot: string; text: string}[] = [
	{shot: 's03', text: 'SUN 08 NOV 2026 · ~50 KM S OF CAIRO'},
	{shot: 's04', text: 'TRAIN 134 · GIZA → FAYOUM'},
	{shot: 's05', text: 'TRAIN 2010 · LAST COACH'},
	{shot: 's07', text: 'SIGNAL TOWER 10 · AL-RAQQA'},
];
export const ILLUSTRATIVE = new Set(['s10', 's16', 's17', 's12', 's13', 's14']);
export const IMPACT = START.s12 + 1;   // FE t=0 (first contact) is the first frame of s12
