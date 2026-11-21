import {loadFont} from '@remotion/fonts';
import {staticFile} from 'remotion';

export const PAPER = '#F2F0EB';
export const INK = '#0A0A0A';
export const DISPLAY = 'Anton';
export const TEXT = 'Inter Tight';

loadFont({family: DISPLAY, url: staticFile('anton.woff2'), weight: '400'});
loadFont({family: TEXT, url: staticFile('intertight600.woff2'), weight: '600'});
loadFont({family: TEXT, url: staticFile('intertight700.woff2'), weight: '700'});
loadFont({family: TEXT, url: staticFile('intertight800.woff2'), weight: '800'});

export const clamp = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const ease = (p: number) => { const x = clamp(p); return x * x * (3 - 2 * x); };
export const back = (p: number) => { const x = clamp(p), c = 1.9; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); };
