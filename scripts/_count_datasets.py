import json
from pathlib import Path
data = Path('datasets/parallel')
for lang in sorted(data.iterdir()):
    counts = {}
    for split in ['train','dev','test']:
        f = lang / f'{split}.jsonl'
        counts[split] = sum(1 for _ in open(f, encoding='utf-8')) if f.exists() else 0
    print(f'{lang.name:6s}  train={counts["train"]:6,}  dev={counts["dev"]:5,}  test={counts["test"]:5,}')
