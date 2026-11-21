import {bundle} from '@remotion/bundler';
import {renderMedia, renderStill, selectComposition} from '@remotion/renderer';
import {createServer} from 'node:http';
import {createReadStream, existsSync} from 'node:fs';
import {readFile, stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const [manifest, folder, output, frame] = process.argv.slice(2);
if (!manifest || !folder || !output) throw new Error('node render-car.mjs manifest.json image-folder out.mp4 [still-frame]');
const cwd = path.dirname(fileURLToPath(import.meta.url));
const images = path.resolve(folder);
const data = JSON.parse(await readFile(manifest, 'utf8'));
if (!data.frames.length) throw new Error('No solved frames in manifest.');
const server = createServer(async (req,res) => {
  try {
    const relative = decodeURIComponent(new URL(req.url,'http://localhost').pathname.slice(1));
    const file = path.resolve(images,relative);
    if (!file.startsWith(images+path.sep) || !/\.png$/i.test(file) || !(await stat(file)).isFile()) throw new Error('Unknown frame');
    res.writeHead(200,{'Content-Type':'image/png','Access-Control-Allow-Origin':'*'});
    createReadStream(file).on('error',()=>res.destroy()).pipe(res);
  } catch {res.writeHead(404);res.end();}
});
await new Promise((resolve,reject)=>server.once('error',reject).listen(0,'127.0.0.1',resolve));
try {
  const inputProps = {...data,base:`http://127.0.0.1:${server.address().port}`,ui:true};
  const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE || (existsSync('/usr/bin/chromium')?'/usr/bin/chromium':undefined);
  const serveUrl = await bundle({entryPoint:path.join(cwd,'src/CarShort.tsx'),publicDir:path.join(cwd,'public')});
  const options = {serveUrl,inputProps,browserExecutable};
  const composition = await selectComposition({...options,id:'CarShort'});
  if (frame !== undefined) await renderStill({...options,composition,frame:Number(frame),output,imageFormat:'png'});
  else await renderMedia({...options,composition,codec:'h264',crf:17,pixelFormat:'yuv420p',concurrency:2,
    colorSpace:'bt709',muted:true,outputLocation:output});
} finally {server.closeAllConnections();server.close();}
