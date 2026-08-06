from datasets import get_dataset_config_names, load_dataset

# Check psk/indic-tts-966h
print("=== psk/indic-tts-966h configs ===")
try:
    cfgs = get_dataset_config_names("psk/indic-tts-966h")
    print(f"  {len(cfgs)} configs:", cfgs[:20])
except Exception as e:
    print(f"  ERROR: {e}")

# Peek at one row to see field names
print("\n=== psk/indic-tts-966h sample row (hi) ===")
try:
    ds = load_dataset("psk/indic-tts-966h", "hi", split="train", streaming=True)
    row = next(iter(ds))
    print("  keys:", list(row.keys()))
    for k, v in row.items():
        if k != "audio":
            print(f"  {k}: {repr(v)[:80]}")
        else:
            print(f"  audio: keys={list(v.keys()) if isinstance(v, dict) else type(v)}")
except Exception as e:
    print(f"  ERROR: {e}")

# Check Kathbath
print("\n=== ai4bharat/Kathbath configs ===")
try:
    cfgs2 = get_dataset_config_names("ai4bharat/Kathbath")
    print(f"  {len(cfgs2)} configs:", cfgs2[:10])
except Exception as e:
    print(f"  ERROR: {e}")
