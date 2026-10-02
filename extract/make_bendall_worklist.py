"""Bendall's Cambridge catalogue (1883) -> extract/worklist_bendall.jsonl, one record per manuscript
(an Add. number, or a numbered part of a composite entry such as Add. 1691 II)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'db'))
import bendall

ROMAN = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI',
         'XVII', 'XVIII', 'XIX', 'XX', 'XXI', 'XXII', 'XXIII', 'XXIV', 'XXV', 'XXVI', 'XXVII', 'XXVIII', 'XXIX', 'XXX']


def label(add_no, part=None):
    return f'Cambridge Add. {add_no}' + (f' ({ROMAN[part]})' if part else '')


def clip(t, n=9000):
    return t if len(t) <= n else t[:1500] + '\n[...]\n' + t[-(n - 1500):]


def units():
    for e in bendall.parse():
        if not e['parts']:
            yield e, None, e['title'], e['text']
        for p in e['parts']:
            yield e, p, p['title'], f"[Composite entry; general note:] {e['description']}\n\n" + p['text']


if __name__ == '__main__':
    n = 0
    with open(os.path.join(HERE, 'worklist_bendall.jsonl'), 'w') as o:
        for e, p, title, text in units():
            d = p or e
            o.write(json.dumps({'reel': label(e['add_no'], p and p['part']), 'title': title or '',
                                'script': d.get('hand') or '', 'fields': {'Date of Copying': d.get('date_text') or ''},
                                'colophon': clip(text), 'ce': d.get('year_ce')}, ensure_ascii=False) + '\n')
            n += 1
    print(n, 'records')
