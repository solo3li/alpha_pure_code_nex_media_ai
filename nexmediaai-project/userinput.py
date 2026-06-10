import httpx

url = "https://nihalgazi-text-to-speech-unlimited.hf.space/api/predict/text_to_speech_app"

payload = {
    "data": [
        "Hello!!",    # prompt
        "alloy",      # voice
        "neutral",    # emotion
        True,         # use_random_seed
        12345         # specific_seed
    ]
}

r = httpx.post(url, json=payload, timeout=300)
print("Status:", r.status_code)
print("Response:", r.json())
