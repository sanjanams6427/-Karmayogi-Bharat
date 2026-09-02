import subprocess, os, json

langs = ['asm','ben','bod','doi','guj','hin','kan','kas','kok','mai','mal','mar','mni','nep','ory','pan','san','sat','snd','tam','tel','urd']
base = os.path.join('output', 'KB_COURSE_001')

print(f"{'LANG':<5} {'MB':>7}  {'V_CODEC':<8} {'A_CODEC':<7} {'W':>4} {'H':>4}  {'V_DUR':>8} {'A_DUR':>8}  {'SR':>6} {'CH':>2}  STATUS")
print('-'*95)

for lang in langs:
    mp4 = os.path.join(base, lang, f'KB_COURSE_001_{lang}.mp4')
    if not os.path.exists(mp4):
        print(f'{lang:<5} MISSING')
        continue
    size_mb = os.path.getsize(mp4) / 1024**2
    r = subprocess.run(['ffprobe','-v','error','-show_streams','-of','json', mp4], capture_output=True, text=True)
    streams = json.loads(r.stdout).get('streams', [])
    v = next((s for s in streams if s.get('codec_type')=='video'), {})
    a = next((s for s in streams if s.get('codec_type')=='audio'), {})
    v_codec = v.get('codec_name','NONE')
    a_codec = a.get('codec_name','NONE')
    w = v.get('width',0); h = v.get('height',0)
    v_dur = float(v.get('duration',0))
    a_dur = float(a.get('duration',0))
    sr = a.get('sample_rate','?')
    ch = a.get('channels','?')
    drift = abs(v_dur - a_dur)
    if a_codec == 'NONE':   status = 'NO_AUDIO'
    elif v_codec == 'NONE': status = 'NO_VIDEO'
    elif size_mb < 1.0:     status = 'TINY_FILE'
    elif drift >= 2.0:      status = f'DRIFT_{drift:.1f}s'
    else:                   status = 'OK'
    print(f'{lang:<5} {size_mb:>7.1f}  {v_codec:<8} {a_codec:<7} {w:>4} {h:>4}  {v_dur:>8.1f} {a_dur:>8.1f}  {sr:>6} {ch:>2}  {status}')
