import os
import requests
import random
from gtts import gTTS
from dotenv import load_dotenv

# Load environment constants
load_dotenv(".env")
AUDIO = os.getenv("AUDIO_NAME", "speech.mp3")

# API Keys (with fallback) - Read from env
ELEVENLABS_API_KEYS = os.getenv("ELEVENLABS_API_KEYS", "").split(",")

# List of available ElevenLabs voice IDs
ELEVENLABS_VOICE_IDS = [
    "pNInz6obpgDQGcFmaJgB",
    "Xb7hH8MSUJpSbSDYk0k2",
    "hpp4J3VqNfWAUOO0d1Us",
    "pqHfZKP75CvOlQylNhV4",
    "nPczCjzI2devNBz1zQrb",
    "4YYIPFl9wE5c4L2eu2Gb",
    "N2lVS1w4EtoT3dr4eOWO",
    "IKne3meq5aSn9XLyUdCD",
    "iP95p4xoKVk53GoZ742B",
    "onwK4e9ZLuTAKqWW03F9",
    "cjVigY5qzO86Huf0OWal",
    "JBFqnCBsd6RMkjVDRZzb",
    "SOYHLrjzK2X1ezoPC6cr",
    "cgSgspJ2msm6clMCkdW9",
    "FGY2WhTYpPnrIDTdsKH5",
    "TX3LPaxmHKxFdv7VOQHJ",
    "pFZP5JQG7iQjIQuC4Bku",
    "XrExE9yKIg1WjnnlVkGX",
    "SAz9YHcvj6GT2YYXdXww",
    "CwhRBWXzGAHq8TQ4Fs17",
    "EXAVITQu4vr4xnSDxMaL",
    "bIHbv24MWmeRgasZH58o",
]

WORDS_PER_MINUTE = 180


def adjust_text_length(text, target_duration=60):
    """Adjusts text length to match the target duration in seconds (approx. 150 WPM)."""
    words = text.split()
    target_word_count = WORDS_PER_MINUTE * target_duration // 60
    return " ".join(words[:target_word_count])


def make_audio(text, output_dir, filename):
    """Generate speech using ElevenLabs first, then gTTS as a backup."""
    text = adjust_text_length(text, 60)  # Ensure approx. 1-minute duration

    for api_key in [k for k in ELEVENLABS_API_KEYS if k.strip()]:
        voice_id = random.choice(ELEVENLABS_VOICE_IDS)
        print(
            f"🎤 Trying ElevenLabs API key: {api_key[:10]}... with Voice ID: {voice_id}"
        )

        elevenlabs_audio = elevenlabs_tts(text, api_key, voice_id)
        if elevenlabs_audio:
            os.makedirs(output_dir, exist_ok=True)
            file_path = os.path.join(output_dir, f"{filename}.mp3")
            with open(file_path, "wb") as f:
                f.write(elevenlabs_audio)
            print(f"✅ ElevenLabs Audio saved as {file_path}")
            return file_path  # Success, return file path

    print("⚠️ ElevenLabs failed. Switching to gTTS...")

    # If ElevenLabs fails, use gTTS
    try:
        speech = gTTS(text)
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, f"{filename}.mp3")
        speech.save(file_path)
        print(f"✅ gTTS Audio saved as {file_path}")
        return file_path
    except Exception as e:
        print(f"❌ Both ElevenLabs & gTTS failed: {e}")
        return None


def elevenlabs_tts(text, api_key, voice_id):
    """Generate speech using ElevenLabs API with a random voice ID."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.8},
    }

    try:
        response = requests.post(url, json=data, headers=headers, timeout=15)

        if response.status_code == 200:
            print("✅ ElevenLabs TTS Success!")
            return response.content  # Returns audio file in bytes
        else:
            print(f"❌ ElevenLabs API error: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.Timeout:
        print("⚠️ ElevenLabs API request timed out.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ ElevenLabs API request failed: {e}")
        return None
