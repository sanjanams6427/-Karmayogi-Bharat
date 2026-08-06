from huggingface_hub import list_datasets
results = list(list_datasets(search="ai4bharat tts", limit=20))
for r in results:
    print(r.id)
