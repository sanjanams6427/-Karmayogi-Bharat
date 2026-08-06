from datasets import load_dataset, get_dataset_config_names

# Kathbath schema
print("=== ai4bharat/Kathbath sample (hindi) ===")
try:
    ds = load_dataset("ai4bharat/Kathbath", "hindi", split="train", streaming=True)
    row = next(iter(ds))
    print("  keys:", list(row.keys()))
    for k, v in row.items():
        if k != "audio":
            print(f"  {k}: {repr(v)[:100]}")
        else:
            print(f"  audio: {list(v.keys()) if isinstance(v,dict) else type(v)}")
except Exception as e:
    print(f"  ERROR: {e}")

# psk/indic-tts-966h schema
print("\n=== psk/indic-tts-966h sample (tamil) ===")
try:
    ds2 = load_dataset("psk/indic-tts-966h", "tamil", split="train", streaming=True)
    row2 = next(iter(ds2))
    print("  keys:", list(row2.keys()))
    for k, v in row2.items():
        if k != "audio":
            print(f"  {k}: {repr(v)[:100]}")
        else:
            print(f"  audio: {list(v.keys()) if isinstance(v,dict) else type(v)}")
except Exception as e:
    print(f"  ERROR: {e}")

# Kathbath full config list
print("\n=== Kathbath all configs ===")
cfgs = get_dataset_config_names("ai4bharat/Kathbath")
for c in cfgs:
    print(" ", c)
