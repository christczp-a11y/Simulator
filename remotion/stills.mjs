import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
// node stills.mjs <f1,f2,…> [uiScale=1] [suffix]  →  out/st_XXXX<suffix>.jpg
const HS = '/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell';
const frames = process.argv[2].split(',').map(Number);
const inputProps = {frameBase: 'http://127.0.0.1:8123', ui: true, uiScale: Number(process.argv[3] || 1), keepLabels: process.argv[5] !== 'uniform'};
const sfx = process.argv[4] || '';
const serveUrl = await bundle({entryPoint: 'src/index.ts'});
const composition = await selectComposition({serveUrl, id: 'Short', browserExecutable: HS, inputProps});
for (const f of frames) {
	await renderStill({composition, serveUrl, frame: f, output: `out/st_${String(f).padStart(4, '0')}${sfx}.jpg`, imageFormat: 'jpeg', jpegQuality: 88, browserExecutable: HS, inputProps});
	console.log('still', f);
}
