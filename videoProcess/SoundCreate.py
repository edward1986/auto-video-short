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
    "sk_9a66def8648739174ed7f5934a7a5cae57c6fb6f7a767823",
    "sk_f9ab6a4d3ea849b85302b3d590172fff3a09d44da62dc2b2",
    "sk_9065e66ee1a5662b14f831c308f74c1448e66aff7ec06900",
    "sk_a99dbb766144930e82a5f622004b9368ac3971566de9501c",
    "sk_1d0c44a850d0f3e693ac60b9091a7a34985c88ccc5a75673",
    "sk_3195492f19f0e3cbf4a64cfffe4a55a3c3949694ebf016b9",
    "sk_5750fdf2f60810dc6aa1801f7c69e08816123c9a796afa18",
    "sk_809f3aacce966859de8944d32e88de2f62deb515905166f3",
    "sk_43b2382845d59ab8a4b040b15fdb6cf3ed267e9c5625892e",
    "sk_e8b4c1752bd5fecee0dd05430c74800710688d47d4a935e8",
    "sk_6a4d153f9eccfd2ca3b38d0f9b506e38eb1b8dea78d92c06",
    "sk_a3a800f932a3a83e90b702c68f12edb8e27bba256bbffedd",
    "sk_82e0fd09418e37c587a25fa0b5d14c260a171981b1708946",
    "sk_ae400bf113c280092384c3e2febc4952941244e63258bd75",
    "sk_30e021f20374ee8cbeee49cd810c8387a2733ce7f9d7bcb7",
    "sk_37b34fbfa5b72252846d7b6e6fdae5b69df54c33434c35a0",
    "sk_c2c6fe4d8b25879206564537f2c4dd37e335d4e49ad914ce",
    "sk_672fff8d79cc04625ad64e05649451b61e582c36b11e7237",
    "sk_7e27d0aa0a8b9b5fbc62ad89dc2b08174be5a6a10565edb6",
    "sk_e7c8e22b874c9d7206e67b3308ee96e11ea9353f757be085",
    "sk_3723a1a59792d5536d9d5c00f11c7ad084f233c127214798",
    "sk_ad7f79817adb79f10f513c75a978e79a632f9b52e06056c1",
    "sk_a9fe92a3ed910546dcc038a5b6cd581db76fb2c7488f4012",
    "sk_3a50f94d24e2acc961a6be741e942a9a958c9f54741689f6",
    "sk_d6c8c9757e60bcf1c874f74ee6872c84dfca7596c93b0c39",
    "sk_59122bdc1ec48db74033617282fe2be302b81dd9360a7bda",
    "sk_d70cbfa599768e0cea85422a9c262958dc673433c34154cd",
    "sk_ecc3d9e548a5faf97b82fb9fb2cf9a15891dd6a2dc38fa53",
    "sk_2e9c3a490321b4328e7c3ad1bb752a1742a464c97c563adb",
    "sk_14bacdb15e1a7c6350918ab24ad90596c251bf94a685459f",
    "sk_86f517a2b897235933e8bc3d14648ae3ce32ad158650c091",
    "sk_40b361541763420f95e5e493c2405a3b8c6ac52c4100f1aa",
    "sk_283d5bbca1f5fd5d7ad288907215a92bb3e40e60ace2e3c3",
    "sk_d44b0722cb0b36ec45c466c090274936b2171940bdc90ac5",
    "sk_daae0c0de846357315d7f829fcfbdb4b35ca9fecb6348cb1",
    "sk_d78925238331831bfac502006c8415a5fbb052bdaa6688e9",
    "sk_ab0230e48aaf55264693c09d0cd0e5822f4f14d8851c4241",
    "sk_dfc880f060fd604e2087f3886bdace4d8b2ca74b8465a7db",
    "sk_654a7862dda64f5a585211b7a577970bf2e398d8e30839f8", 
    "sk_d8b3755b444957564366a430e09c1c90c3be1b163d9f9a8d",
    "sk_7524a025c70dd26ad9e4f3e98594e8d33707629901d1d7ed",
    "sk_5aec505f72c91c701f6ad2cc0efa349355fed402f8943045",
    "sk_344ffd5c0b46d2d31e5ed450cb4a0cda90b60072a88417c9"
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

WORDS_PER_MINUTE = 180

def adjust_text_length(text, target_duration=60):
    """Adjusts text length to match the target duration in seconds (approx. 150 WPM)."""
    words = text.split()
    target_word_count = WORDS_PER_MINUTE * target_duration // 60
    return " ".join(words[:target_word_count])

def make_audio(text, output_dir, filename):
    """Generate speech using ElevenLabs first, then gTTS as a backup."""
    text = adjust_text_length(text, 60)  # Ensure approx. 1-minute duration

    for api_key in ELEVENLABS_API_KEYS:
        voice_id = random.choice(ELEVENLABS_VOICE_IDS)
        print(f"🎤 Trying ElevenLabs API key: {api_key[:10]}... with Voice ID: {voice_id}")

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
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    data = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}
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
