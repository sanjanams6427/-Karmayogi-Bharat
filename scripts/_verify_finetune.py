import sys, os
sys.path.insert(0, r'e:\Manick_AI_ML\project')
os.chdir(r'e:\Manick_AI_ML\project')
from finetune.finetune_indictrans import build_records, EN_INDIC_TRAIN_LANGS, INDIC_INDIC_PAIRS

print(f'en_indic langs: {len(EN_INDIC_TRAIN_LANGS)} = {sorted(EN_INDIC_TRAIN_LANGS)}')
print(f'indic_indic pairs: {len(INDIC_INDIC_PAIRS)}')
print()
for direction in ['en_indic', 'indic_en', 'indic_indic']:
    recs = build_records(direction, 'train', epoch=1, quiet=True)
    dev  = build_records(direction, 'dev',   epoch=1, quiet=True)
    print(f'{direction}: train={len(recs):,}  dev={len(dev):,}')
print()
recs3 = build_records('en_indic', 'train', epoch=3, quiet=True)
print(f'en_indic epoch3 (with synthetic): train={len(recs3):,}')
