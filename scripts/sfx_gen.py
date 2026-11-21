"""sfx_gen.py — fetches the sound effects for the Short from ElevenLabs (text to sound effects). Standard library only.

  python sfx_gen.py                      (run from anywhere; reads audio\\sfx_prompts.json, writes audio\\<name>.mp3 and audio\\sfx.log)

The API key is read from an environment variable whose name contains ELEVEN (cloud), or else from api-keys.env one folder above
the repository (the owner's PC, the line whose name contains ELEVEN). It is sent only to
api.elevenlabs.io. It is never written to the log or printed. A sound that already exists is not fetched again."""
import json, os, re, sys, time, urllib.request, urllib.error
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); AUD = os.path.join(ROOT, "audio"); ENV = os.path.join(os.path.dirname(ROOT), "api-keys.env")

def log(*a):
    with open(os.path.join(AUD, "sfx.log"), "a", encoding="utf-8") as f: f.write(time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a) + "\n")

def key():
    for n, v in os.environ.items():                      # cloud: set ELEVENLABS_API_KEY (or any name containing ELEVEN) as an environment secret
        if "ELEVEN" in n.upper() and v.strip(): return v.strip(), n
    if not os.path.exists(ENV): return None, None
    for line in open(ENV, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*(?:export\s+)?([A-Za-z0-9_]*ELEVEN[A-Za-z0-9_]*)\s*=\s*(.+?)\s*$", line, re.I)
        if m: return m.group(2).strip().strip('"').strip("'"), m.group(1)
    return None, None

k, name = key()
if not k: log("no line with ELEVEN in its name in api-keys.env"); sys.exit(2)
log("key found under the name", name, "length", len(k))
for p in json.load(open(os.path.join(AUD, "sfx_prompts.json"), encoding="utf-8")):
    out = os.path.join(AUD, p["name"] + ".mp3")
    if os.path.exists(out) and os.path.getsize(out) > 2000: log(p["name"], "already there"); continue
    for model in ("eleven_text_to_sound_v3", "eleven_text_to_sound_v2"):
        body = dict(text=p["text"], duration_seconds=p["seconds"], prompt_influence=p.get("influence", 0.4), model_id=model)
        req = urllib.request.Request("https://api.elevenlabs.io/v1/sound-generation?output_format=mp3_44100_128", data=json.dumps(body).encode(), method="POST",
                                     headers={"xi-api-key": k, "Content-Type": "application/json", "Accept": "audio/mpeg"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read(); open(out, "wb").write(data); log(p["name"], "ok", model, len(data), "bytes", "cost header", r.headers.get("character-cost")); break
        except urllib.error.HTTPError as e:
            log(p["name"], model, "HTTP", e.code, e.read()[:300].decode("utf-8", "replace").replace(k, "***"))
        except Exception as e:
            log(p["name"], model, "error", repr(e).replace(k, "***"))
log("done")
