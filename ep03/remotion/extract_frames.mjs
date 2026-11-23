// node extract_frames.mjs <videosDir> <framesDir>   — needs ffmpeg on PATH. s20.mov keeps its alpha.
import {execFileSync} from 'node:child_process'; import fs from 'node:fs'; import path from 'node:path';
const [vid, out] = process.argv.slice(2);
for (const f of fs.readdirSync(vid).filter((x) => /^s\d+a?\.(mp4|mov)$/.test(x))) {
	const s = f.split('.')[0]; const d = path.join(out, s); fs.mkdirSync(d, {recursive: true});
	if (fs.readdirSync(d).length) { console.log('skip', s); continue; }
	const args = ['-v', 'error', '-i', path.join(vid, f)].concat(s === 's20' ? ['-pix_fmt', 'rgba'] : []).concat([path.join(d, `${s}_%04d.png`)]);
	execFileSync('ffmpeg', args, {stdio: 'inherit'}); console.log(s, fs.readdirSync(d).length, 'frames');
}
