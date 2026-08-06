from huggingface_hub import list_datasets

for query in ["indic tts", "kathbath", "ai4bharat speech", "IndicTTS"]:
    print(f"\n=== {query} ===")
    results = list(list_datasets(search=query, limit=10))
    for r in results:
        print(" ", r.id)
