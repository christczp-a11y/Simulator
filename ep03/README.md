# EP03 El Ayyat (Egypt train collision, 2026-11-08) - production code

- `blender/` - scene + shot scripts (Blender 5.2, run via `blender -b --factory-startup -P blender/shots.py -- <shot> <outdir>`; scripts expect the tree at `/home/claude/ep03`). FE crash data: `fe/el_ayyat/out/frames.npz` in this repo (copy to `blender/fe/frames.npz`).
  - `shots.py` v2 additions: `s01h` hook shot (train 134 closing 180 m -> 30 m, push-in + shake), `--persist`, `--eevee`, `--bench B|C` timing options.
- `remotion/` - 2D compositing (subtitles, HUD, end card, flip clock). `npm ci`, then `node extract_frames.mjs <videos> <frames>` and `node render_pc.mjs <frames> <out.mp4> 8`. Audio (VO mp3, sfx_mix.wav) is not in git: see Out\ep03-egypt-train\audio on Chris's PC.
- `tools/` - ElevenLabs VO (`make_vo.py`), v1 generated SFX (`make_sfx.py`, rejected), v2 library SFX mix (`make_sfx_v2.py`, `--v1b` = published mix), library grabber (`recv_server.py` + `grab.js`), finishing scripts, thumbnails (`thumb_final.py`, no red circles), `SOURCES.md` (library sound list).
- Published: V1 picture + v2 library sound = `ep03_v1b_norm.mp4`.
