import os
import requests
from gtts import gTTS
from dotenv import load_dotenv

# Load environment constants
load_dotenv(".env")
AUDIO = os.getenv("AUDIO_NAME", "speech.mp3")
ELEVENLABS_API_KEYS = [
    "sk_14bacdb15e1a7c6350918ab24ad90596c251bf94a685459f",
    "sk_86f517a2b897235933e8bc3d14648ae3ce32ad158650c091"
]

def make_audio(quote, out):
    """Generate speech using ElevenLabs first, then gTTS as a backup."""
    
    for api_key in ELEVENLABS_API_KEYS:
        print(f"🎤 Trying ElevenLabs API key: {api_key[:10]}...")

        elevenlabs_audio = elevenlabs_tts(quote, api_key)
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

def elevenlabs_tts(text, api_key, voice_id="CwhRBWXzGAHq8TQ4Fs17"):
    """Generate speech using ElevenLabs API with fallback on different API keys."""
    
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
