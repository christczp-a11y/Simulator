// Windows/PC final render.  Usage (in this folder):
//   node render_pc.mjs <framesDir> <out.mp4> [concurrency=4]
// framesDir holds sNN/sNN_####.png (made by extract_frames.mjs). Serves them on 127.0.0.1:8123 while rendering.
import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';
const [framesDir, out, c] = process.argv.slice(2); const conc = Number(c ?? 4);
const srv = http.createServer((req, res) => {
	const p = path.join(framesDir, decodeURIComponent(req.url.split('?')[0]));
	fs.readFile(p, (e, d) => { if (e) { res.writeHead(404); res.end(); return; } res.writeHead(200, {'Content-Type': 'image/png', 'Access-Control-Allow-Origin': '*'}); res.end(d); });
}).listen(8123, '127.0.0.1');
const sfx = fs.existsSync('public/sfx_mix.wav');
const inputProps = {frameBase: 'http://127.0.0.1:8123', ui: true, sfx};
const serveUrl = await bundle({entryPoint: 'src/index.ts'});
const composition = await selectComposition({serveUrl, id: 'Episode', inputProps});
const t0 = Date.now(); let last = 0;
await renderMedia({composition, serveUrl, codec: 'h264', outputLocation: out, inputProps, concurrency: conc, imageFormat: 'jpeg', jpegQuality: 97, crf: 16, pixelFormat: 'yuv420p', colorSpace: 'bt709', audioCodec: 'aac', audioBitrate: '320k',
	onProgress: ({renderedFrames}) => { if (renderedFrames - last >= 100) { last = renderedFrames; console.log('rendered', renderedFrames, '/', composition.durationInFrames, ((Date.now() - t0) / 1000).toFixed(0) + 's'); } }});
console.log('done', out, ((Date.now() - t0) / 1000).toFixed(0) + 's'); srv.close();
