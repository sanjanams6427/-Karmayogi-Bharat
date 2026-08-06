import json
from pathlib import Path
for lang in ['doi','bod','kok','san','mni','sat','kas','snd','hin','ben']:
    f = Path(f'datasets/parallel/{lang}/train.jsonl')
    if f.exists():
        r = json.loads(open(f, encoding='utf-8').readline())
        print(f"{lang}: src_lang={r.get('src_lang','?')!r} tgt_lang={r.get('tgt_lang','?')!r} synthetic={r.get('synthetic',False)} src={r['src'][:50]!r}")
