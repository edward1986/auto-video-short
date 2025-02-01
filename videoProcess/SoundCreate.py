import os
import requests
from gtts import gTTS
from dotenv import load_dotenv

# Load environment constants
load_dotenv(".env")
AUDIO = os.getenv("AUDIO_NAME", "speech.mp3")
ELEVENLABS_API_KEY = "sk_14bacdb15e1a7c6350918ab24ad90596c251bf94a685459f"

def make_audio(quote):
    """Generate speech using ElevenLabs first, then gTTS as a backup."""
    
    if ELEVENLABS_API_KEY:
        print("🎤 Using ElevenLabs for text-to-speech...")
        elevenlabs_audio = elevenlabs_tts(quote)
        if elevenlabs_audio:
            with open(f"output/{AUDIO}", "wb") as f:
                f.write(elevenlabs_audio)
            print(f"✅ ElevenLabs Audio saved as output/{AUDIO}")
            return  # Exit after successful ElevenLabs generation

    print("⚠️ ElevenLabs failed or API key missing. Switching to gTTS...")
    
    # ✅ If ElevenLabs fails, use gTTS as a fallback
    try:
        speech = gTTS(quote)
        speech.save(f"output/{AUDIO}")
        print(f"✅ gTTS Audio saved as output/{AUDIO}")
    except Exception as e:
        print(f"❌ Both ElevenLabs & gTTS failed: {e}")

def elevenlabs_tts(text, voice_id="CwhRBWXzGAHq8TQ4Fs17"):
    """Generate speech using ElevenLabs API."""
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
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
