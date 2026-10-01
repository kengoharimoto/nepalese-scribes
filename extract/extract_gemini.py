#!/usr/bin/env python3
"""Same extraction as extract.py, through the Gemini API (key as in indology-genealogy/pipeline/llm.py).
Usage: extract_gemini.py worklist.jsonl outdir [--model gemini-pro-latest] [--jobs 8] [--limit N]"""
import json, os, pathlib, argparse, time, concurrent.futures as cf
from google import genai
from google.genai import types

HERE = pathlib.Path(__file__).parent
ap = argparse.ArgumentParser()
ap.add_argument('records'); ap.add_argument('outdir')
ap.add_argument('--model', default='gemini-pro-latest'); ap.add_argument('--jobs', type=int, default=8)
ap.add_argument('--limit', type=int, default=0)
a = ap.parse_args()
out = pathlib.Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
prompt = (HERE / 'prompt.txt').read_text()
schema = json.loads((HERE / 'schema.json').read_text())


def load_key():
    if os.getenv('GEMINI_API_KEY'):
        return os.environ['GEMINI_API_KEY']
    for line in open(os.path.expanduser('~/code/mitra-evaluation/.secrets.env')):
        if line.strip().startswith('GEMINI_API_KEY='):
            return line.split('=', 1)[1].strip().strip('"\'')


client = genai.Client(api_key=load_key())


def record_text(r):
    f = r['fields']
    return '\n'.join([f"REEL: {r['reel']}", f"TITLE: {r['title']}", f"SCRIPT: {r['script']}",
                      'CATALOGUE FIELDS: ' + '; '.join(f'{k}: {v}' for k, v in f.items() if v),
                      '=== COLOPHON (as quoted by the cataloguer) ===\n' + r['colophon']])


def run(r):
    fid = r['reel'].replace(' ', '_').replace('/', '-')
    dst = out / f'{fid}.json'
    if dst.exists(): return fid, 'cached'
    err = ''
    for attempt in range(5):
        t0 = time.time()
        try:
            resp = client.models.generate_content(
                model=a.model, contents=prompt + '\n\n' + record_text(r),
                config=types.GenerateContentConfig(temperature=0.0, response_mime_type='application/json',
                                                   response_json_schema=schema))
            so = json.loads(resp.text)
            um = resp.usage_metadata
            so['_meta'] = {'reel': r['reel'], 'model': a.model, 'secs': round(time.time() - t0, 1),
                           'in_tok': um.prompt_token_count or 0,
                           'out_tok': (um.candidates_token_count or 0) + (um.thoughts_token_count or 0)}
            dst.write_text(json.dumps(so, ensure_ascii=False, indent=1))
            return fid, f"ok {so['_meta']['secs']}s persons={len(so['persons'])} rel={len(so['relations'])}"
        except Exception as e:
            err = repr(e)[:300]
            time.sleep(min(60, 4 * 2 ** attempt))
    (out / f'{fid}.err').write_text(err)
    return fid, f'FAILED {err}'


recs = [json.loads(l) for l in open(a.records)]
if a.limit: recs = recs[:a.limit]
with cf.ThreadPoolExecutor(a.jobs) as ex:
    for fid, status in ex.map(run, recs):
        print(fid, status, flush=True)
