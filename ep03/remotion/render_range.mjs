// Render a frame range of the episode (same settings as render_pc.mjs).
//   node render_range.mjs <framesDir> <out.mp4> <from> <to> [concurrency=4]
import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';
const [framesDir, out, a, b, c] = process.argv.slice(2);
const srv = http.createServer((req, res) => {
	const p = path.join(framesDir, decodeURIComponent(req.url.split('?')[0]));
	fs.readFile(p, (e, d) => { if (e) { res.writeHead(404); res.end(); return; } res.writeHead(200, {'Content-Type': 'image/png', 'Access-Control-Allow-Origin': '*'}); res.end(d); });
}).listen(8123, '127.0.0.1');
const inputProps = {frameBase: 'http://127.0.0.1:8123', ui: true, sfx: fs.existsSync('public/sfx_mix.wav')};
const serveUrl = await bundle({entryPoint: 'src/index.ts'});
const composition = await selectComposition({serveUrl, id: 'Episode', inputProps});
await renderMedia({composition, serveUrl, codec: 'h264', outputLocation: out, inputProps, concurrency: Number(c ?? 4), frameRange: [Number(a), Number(b)],
	imageFormat: 'jpeg', jpegQuality: 97, crf: 16, pixelFormat: 'yuv420p', colorSpace: 'bt709', audioCodec: 'aac', audioBitrate: '320k'});
console.log('done', out); srv.close();
