"""ElevenLabs VO for ep03 (El Ayyat).  python make_vo.py [--list-voices]
Reads remotion/vo_lines.json, writes remotion/public/vo/<id>.mp3 and remotion/src/durations.json.
Key: elevenlab_api_key in C:\\YouTubeNeuropolis\\api-keys.env (never printed)."""
import json, pathlib, subprocess, sys, urllib.request

ENV = r'C:\YouTubeNeuropolis\api-keys.env'
HERE = pathlib.Path(__file__).resolve().parent
R = HERE / 'remotion'
VOICES = {'daniel': 'onwK4e9ZLuTAKqWW03F9',   # Daniel - Steady Broadcaster (same as Vulcan)
          'quote': None}                       # filled from --quote-voice
SETTINGS = {'daniel': {'stability': 0.55, 'similarity_boost': 0.8, 'style': 0.0},
            'quote': {'stability': 0.8, 'similarity_boost': 0.75, 'style': 0.0}}   # flat, neutral read


def key():
    for line in open(ENV, encoding='utf-8'):
        if line.lower().startswith('elevenlab_api_key='):
            return line.split('=', 1)[1].strip()
    raise SystemExit('elevenlab_api_key missing')


def api(path, body=None):
    req = urllib.request.Request('https://api.elevenlabs.io' + path, data=json.dumps(body).encode() if body else None,
                                 headers={'xi-api-key': key(), 'Content-Type': 'application/json'})
    return urllib.request.urlopen(req, timeout=180).read()


def dur(p):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(p)],
                                capture_output=True, text=True, check=True).stdout)


if __name__ == '__main__':
    if '--list-voices' in sys.argv:
        for v in json.loads(api('/v1/voices'))['voices']:
            l = v.get('labels', {})
            print(v['voice_id'], v['name'], v.get('category'), l.get('gender'), l.get('accent'), l.get('descriptive') or l.get('description'), l.get('use_case'))
        sys.exit()
    VOICES['quote'] = sys.argv[sys.argv.index('--quote-voice') + 1]
    out = R / 'public' / 'vo'; out.mkdir(parents=True, exist_ok=True)
    durs = {}
    for c in json.load(open(R / 'vo_lines.json', encoding='utf-8')):
        f = out / f"{c['id']}.mp3"
        if not f.exists():
            f.write_bytes(api(f"/v1/text-to-speech/{VOICES[c['voice']]}?output_format=mp3_44100_192",
                              {'text': c['text'], 'model_id': 'eleven_multilingual_v2', 'voice_settings': SETTINGS[c['voice']]}))
        durs[c['id']] = round(dur(f), 3)
        print(c['id'], c['voice'], durs[c['id']], flush=True)
    json.dump(durs, open(R / 'src' / 'durations.json', 'w'), indent=1)
