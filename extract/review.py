#!/usr/bin/env python3
"""Second reading: Opus checks and corrects the Gemini Flash extraction of a colophon (via `claude -p`).
Usage: review.py review_list.jsonl firstdir outdir [--model opus] [--jobs 4] [--limit N] [--preamble FILE]"""
import json, subprocess, pathlib, argparse, concurrent.futures as cf, time, re, threading, datetime
from zoneinfo import ZoneInfo

HERE = pathlib.Path(__file__).parent
ap = argparse.ArgumentParser()
ap.add_argument('records'); ap.add_argument('firstdir'); ap.add_argument('outdir')
ap.add_argument('--model', default='opus'); ap.add_argument('--jobs', type=int, default=4)
ap.add_argument('--limit', type=int, default=0)
ap.add_argument('--preamble', default='', help='file whose text goes before the prompt (e.g. bendall_preamble.txt)')
a = ap.parse_args()
out = pathlib.Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
prompt = (HERE / 'review_prompt.txt').read_text()
if a.preamble:
    prompt = pathlib.Path(a.preamble).read_text() + prompt
schema = (HERE / 'review_schema.json').read_text()
first = pathlib.Path(a.firstdir)


def record_text(r):
    f = r['fields']
    parts = [f"REEL: {r['reel']}", f"TITLE: {r['title']}", f"SCRIPT: {r['script']}",
             'CATALOGUE FIELDS: ' + '; '.join(f'{k}: {v}' for k, v in f.items() if v),
             '=== COLOPHON (as quoted by the cataloguer) ===\n' + r['colophon']]
    return '\n'.join(parts)


LIMIT_RE = re.compile(r"hit your .*limit.*?resets\s+(.+?)\s*$", re.I | re.S)
pause_until = 0.0
pause_lock = threading.Lock()


def reset_wait(err):
    m = LIMIT_RE.search(err)
    if not m: return 1800
    txt = m.group(1)
    tz = re.search(r'\(([A-Za-z_/]+)\)', txt); tzname = tz.group(1) if tz else 'Asia/Tokyo'
    tm = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', txt, re.I)
    if not tm: return 1800
    h, mi, ap_ = int(tm.group(1)), int(tm.group(2) or 0), tm.group(3).lower()
    if ap_ == 'pm' and h != 12: h += 12
    if ap_ == 'am' and h == 12: h = 0
    now = datetime.datetime.now(ZoneInfo(tzname))
    t = now.replace(hour=h, minute=mi, second=0, microsecond=0)
    if t <= now: t += datetime.timedelta(days=1)
    return min((t - now).total_seconds() + 90, 7 * 24 * 3600)


def wait_if_paused():
    while (d := pause_until - time.time()) > 0:
        time.sleep(min(d, 60))


def run(r):
    global pause_until
    fid = r['reel'].replace(' ', '_').replace('/', '-')
    dst = out / f'{fid}.json'
    if dst.exists(): return fid, 'cached'
    fr = json.loads((first / f'{fid}.json').read_text())
    fr.pop('_meta', None)
    msg = (prompt + "\n\n" + record_text(r) + "\n\n=== FIRST READING ===\n" + json.dumps(fr, ensure_ascii=False, indent=1))
    attempt, err = 0, ''
    while attempt < 3:
        wait_if_paused()
        t0 = time.time()
        p = subprocess.run(['claude', '-p', '--model', a.model, '--output-format', 'json', '--tools', '',
                            '--json-schema', schema], input=msg, capture_output=True, text=True, timeout=1200)
        try:
            res = json.loads(p.stdout)
            so = res.get('structured_output')
            if so:
                so['_meta'] = {'reel': r['reel'], 'model': a.model, 'cost_usd': res.get('total_cost_usd'),
                               'secs': round(time.time() - t0, 1)}
                dst.write_text(json.dumps(so, ensure_ascii=False, indent=1))
                return fid, f"ok {so['_meta']['secs']}s {so['review']['verdict']} changes={len(so['review']['changes'])}"
            err = res.get('result', '')[:200]
        except Exception as e:
            err = f'{e}: {p.stdout[:200]} {p.stderr[:200]}'
        if re.search(r"hit your .*limit", err, re.I):
            with pause_lock:
                if pause_until < time.time():
                    pause_until = time.time() + reset_wait(err)
                    print(f"[{time.strftime('%H:%M')}] usage limit -> pausing until "
                          f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(pause_until))}", flush=True)
            continue  # not counted as an attempt
        attempt += 1
        (out / f'{fid}.err').write_text(err)
    return fid, f'FAILED {err}'


recs = [json.loads(l) for l in open(a.records)]
if a.limit: recs = recs[:a.limit]
with cf.ThreadPoolExecutor(a.jobs) as ex:
    for fid, status in ex.map(run, recs):
        print(fid, status, flush=True)
