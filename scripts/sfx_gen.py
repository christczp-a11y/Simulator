"""sfx_gen.py — fetches the sound effects for the Short from ElevenLabs (text to sound effects). Standard library only.

  python sfx_gen.py                      (run from anywhere; reads audio\\sfx_prompts.json, writes audio\\<name>.mp3 and audio\\sfx.log)

The API key is read only from an environment variable containing ELEVEN.
Requests stay on api.elevenlabs.io. Existing sound files are skipped."""
import json, os, sys, time, urllib.request, urllib.error
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); AUD = os.path.join(ROOT, "audio")

def log(*a):
    with open(os.path.join(AUD, "sfx.log"), "a", encoding="utf-8") as f: f.write(time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a) + "\n")

def key():
    for n, v in os.environ.items():                      # cloud: set ELEVENLABS_API_KEY (or any name containing ELEVEN) as an environment secret
        if "ELEVEN" in n.upper() and v.strip(): return v.strip(), n
    return None, None

k, name = key()
if not k:
    sys.exit("Set an ElevenLabs environment variable to generate missing sounds.")

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

client = urllib.request.build_opener(NoRedirect())
for p in json.load(open(os.path.join(AUD, "sfx_prompts.json"), encoding="utf-8")):
    out = os.path.join(AUD, p["name"] + ".mp3")
    if os.path.exists(out) and os.path.getsize(out) > 2000: log(p["name"], "already there"); continue
    for model in ("eleven_text_to_sound_v3", "eleven_text_to_sound_v2"):
        body = dict(text=p["text"], duration_seconds=p["seconds"], prompt_influence=p.get("influence", 0.4), model_id=model)
        req = urllib.request.Request("https://api.elevenlabs.io/v1/sound-generation?output_format=mp3_44100_128", data=json.dumps(body).encode(), method="POST",
                                     headers={"xi-api-key": k, "Content-Type": "application/json", "Accept": "audio/mpeg"})
        try:
            with client.open(req, timeout=180) as r:
                data = r.read(); open(out, "wb").write(data); log(p["name"], "ok", model, len(data), "bytes", "cost header", r.headers.get("character-cost")); break
        except urllib.error.HTTPError as e:
            log(p["name"], model, "HTTP", e.code, e.read()[:300].decode("utf-8", "replace").replace(k, "***"))
        except Exception as e:
            log(p["name"], model, "error", repr(e).replace(k, "***"))
log("done")
