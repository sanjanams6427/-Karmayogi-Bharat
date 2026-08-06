from datasets import get_dataset_config_names
configs = get_dataset_config_names("google/fleurs")
indic = [c for c in configs if c.endswith("_in") or c in ("ur_pk", "ne_np")]
print(f"FLEURS Indic configs found: {len(indic)}")
for c in sorted(indic):
    print(" ", c)

# Also check IndicTTS
try:
    cfgs2 = get_dataset_config_names("ai4bharat/indic-tts-coqui")
    print(f"\nIndicTTS configs found: {len(cfgs2)}")
    for c in sorted(cfgs2):
        print(" ", c)
except Exception as e:
    print(f"\nIndicTTS check failed: {e}")
