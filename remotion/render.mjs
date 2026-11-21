// node render.mjs out.mp4 [ui=1] [concurrency=4]   — renders the whole composition (frames come from the local server on port 8123)
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';
const HS = '/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell';
const out = process.argv[2]; const ui = (process.argv[3] ?? '1') === '1'; const conc = Number(process.argv[4] ?? 4); const uiScale = Number(process.argv[5] ?? 1); const keepLabels = process.argv[6] !== 'uniform';   // node render.mjs out.mp4 [ui=1] [concurrency=4] [uiScale=1] [uniform]
const inputProps = {frameBase: 'http://127.0.0.1:8123', ui, uiScale, keepLabels};
const serveUrl = await bundle({entryPoint: 'src/index.ts'});
const composition = await selectComposition({serveUrl, id: 'Short', browserExecutable: HS, inputProps});
const t0 = Date.now(); let last = 0;
await renderMedia({composition, serveUrl, codec: 'h264', outputLocation: out, inputProps, browserExecutable: HS, concurrency: conc, imageFormat: 'jpeg', jpegQuality: 97, crf: 14, pixelFormat: 'yuv420p', colorSpace: 'bt709', x264Preset: 'slow', muted: true,
	onProgress: ({renderedFrames, encodedFrames}) => { if (renderedFrames - last >= 50) { last = renderedFrames; console.log('rendered', renderedFrames, 'encoded', encodedFrames, ((Date.now() - t0) / 1000).toFixed(0) + 's'); } }});
console.log('done', out, ((Date.now() - t0) / 1000).toFixed(0) + 's');
