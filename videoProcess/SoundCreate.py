import os
import requests
import random
from gtts import gTTS
from dotenv import load_dotenv

# Load environment constants
load_dotenv(".env")
AUDIO = os.getenv("AUDIO_NAME", "speech.mp3")

# API Keys (with fallback)
ELEVENLABS_API_KEYS = [
    "sk_14bacdb15e1a7c6350918ab24ad90596c251bf94a685459f",
    "sk_86f517a2b897235933e8bc3d14648ae3ce32ad158650c091",
    "sk_40b361541763420f95e5e493c2405a3b8c6ac52c4100f1aa",
    "sk_283d5bbca1f5fd5d7ad288907215a92bb3e40e60ace2e3c3",
    "sk_d44b0722cb0b36ec45c466c090274936b2171940bdc90ac5",
    "sk_daae0c0de846357315d7f829fcfbdb4b35ca9fecb6348cb1"
]

# List of available ElevenLabs voice IDs
ELEVENLABS_VOICE_IDS = [
    "GBv7mTt0atIp3Br8iCZE", "bIHbv24MWmeRgasZH58o", "pMsXgVXv3BLzUgSXRplE",
    "EXAVITQu4vr4xnSDxMaL", "yoZ06aMxZJJ28mfd3POQ", "CwhRBWXzGAHq8TQ4Fs17",
    "SAz9YHcvj6GT2YYXdXww", "5Q0t7uMcjvnagumLfvZi", "ODq5zmih8GrVes37Dizd",
    "piTKgcLEGmPE4e6mEKli", "flq6f7yk4E4fJM5XTYuZ", "XrExE9yKIg1WjnnlVkGX",
    "pFZP5JQG7iQjIQuC4Bku", "TX3LPaxmHKxFdv7VOQHJ", "FGY2WhTYpPnrIDTdsKH5",
    "TxGEqnHWrfWFTfGW9XjX", "Zlb1dXrM653N07WRdFW3", "t0jbNlBVZ17f02VDIeMI",
    "cgSgspJ2msm6clMCkdW9", "bVMeCyTHy58xNoL34h3p", "ZQe5CZNOzWyzPSCn5a3c",
    "SOYHLrjzK2X1ezoPC6cr", "oWAxZDx7w5VEj9dCyTzz", "z9fAnlkpzviPz146aGWa",
    "zcAOhNBS3c14rBihAFp1", "jBpfuIE2acCO8z3wKNLl", "JBFqnCBsd6RMkjVDRZzb",
    "jsCqWAovK2LkecY7zXl4", "D38z5RcWu1voky8WS1ja", "g5CIjZEefAph4nQFvHAz",
    "cjVigY5qzO86Huf0OWal", "LcfcDJNUP1GQjkzn1xUU", "MF3mGyEYCl7XYWbV9V6O",
    "29vD33N1CtxCmqQRPOHJ", "ThT5KcBeYPX3keUQqHPh", "AZnzlk1XvdvUeBnXmlld",
    "CYw3kZ02Hs0563khs1Fj", "onwK4e9ZLuTAKqWW03F9", "2EiwWnXFnvU5JabPnv8n",
    "XB0fDUnXU5powFXDhCwa", "IKne3meq5aSn9XLyUdCD", "N2lVS1w4EtoT3dr4eOWO",
    "nPczCjzI2devNBz1zQrb", "pqHfZKP75CvOlQylNhV4", "VR6AewLTigWG4xSOukaG",
    "9BWtsMINqrJLrRacOk9x", "ErXwobaYiN019PkySvjV"
]

def make_audio(quote, out):
    """Generate speech using ElevenLabs first, then gTTS as a backup."""
    
    for api_key in ELEVENLABS_API_KEYS:
        voice_id = random.choice(ELEVENLABS_VOICE_IDS)  # Randomly select a voice
        print(f"🎤 Trying ElevenLabs API key: {api_key[:10]}... with Voice ID: {voice_id}")

        elevenlabs_audio = elevenlabs_tts(quote, api_key, voice_id)
        if elevenlabs_audio:
            os.makedirs(out, exist_ok=True)  # Ensure output directory exists
            with open(f"{out}/{AUDIO}", "wb") as f:
                f.write(elevenlabs_audio)
            print(f"✅ ElevenLabs Audio saved as {out}/{AUDIO}")
            return  # Exit after successful ElevenLabs generation
    
    print("⚠️ ElevenLabs failed. Switching to gTTS...")
    
    # ✅ If ElevenLabs fails, use gTTS as a fallback
    try:
        speech = gTTS(quote)
        os.makedirs(out, exist_ok=True)  # Ensure output directory exists
        speech.save(f"{out}/{AUDIO}")
        print(f"✅ gTTS Audio saved as {out}/{AUDIO}")
    except Exception as e:
        print(f"❌ Both ElevenLabs & gTTS failed: {e}")

def elevenlabs_tts(text, api_key, voice_id):
    """Generate speech using ElevenLabs API with a random voice ID."""
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    data = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}
    }

    response = requests.post(url, json=data, headers=headers)

    if response.status_code == 200:
        print("✅ ElevenLabs TTS Success!")
        return response.content  # Returns audio file in bytes
    else:
        print(f"❌ ElevenLabs API error: {response.status_code} - {response.text}")
        return None
