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
    "sk_4e981800fd6333e98a28291b47e867e730d0c08d26a21ce5",
    "sk_023dc378d262241c2d0b8fbae3909ab72884b0a45aa47c5a",
    "sk_768124a0125c7d3d55922f0df0e537970aa90d49cb0865bf",
    "sk_8cbb486e47a4c86d45010bbc267ebadc1ad151cd15e70e3d",
    "sk_bb5915932d41adcbb460547ccd13b13014777d826007a0ce",
    "sk_9df605c181274d695c7c6cfe1ce0841cd04bb02fef3d1522",
    "sk_20332f0c1d8310b0400bd0dba6e732c7659dc71ab5d2941f",
    "sk_5b833db1762b19398ec215285d6e2806d4493405a38f44d5",
    "sk_f98ef37dfa0a699708b8850eae28af91a21596a8bcd909a0",
    "sk_b1ebf59a4416868e21a8737e2b3ffbe05d02e715693e61fb",
    "sk_bfb27542cd0b59779267ce461968567db39094b0f0f04018",
    "sk_54f11acac666ac3ed11a0e762084dc6f2e4bf3fcf5e8e39d",
    "sk_da39c43091ad8e3cec61ef16c5785cda039959b4a47647c5",
    "sk_9fde73709be38d4bd809a787874e8e1694e7800e2659e7d1",
    "sk_d671493566fc10e23e024831cb631feca637df2a280d494c",
    "sk_7adde641659e12e8003866587931ed06ee9499b595cead14",
    "sk_f2e539e0698dd602668f6401a4f493ad827a5fd13f127a2c",
    "sk_b24d1194fd91bd451ebafd337bcafd285d3c10fc94ad3ffd",
    "sk_0eb5138b44227f6023146fd9134584f898e2f4194c9d5f1c",
    "sk_ac6d52bc55e78fcc39de4be02bbe3759da1af2bc8e17895f",
    "sk_46cb1d0020018249d481870bf6d15805496327320832a57a",
    "sk_8a7f77d67f1b428a0a5940e3f2228f822e4e340cc0ae27bd",
    "sk_9612de7197272c6422280a0550ea701a4800517d1c598139",
    "sk_6d33b131dc738b69e876b3935cba27e0debed28b87fcd836",
    "sk_ae6e6e60e3c46b17abfeefb1cead5b1f6e48763459a0869d",
    "sk_68baf48093b574c47cdab041af6789f84d251c9ae3b5d3fe",
    "sk_8d3402f1a59df957ba4259cb18f2dfe33da6d9d11ce2ee2d",
    "sk_dbcdb30e00b90d9f050c4c6285db512815e3fefd9f7e9762",
    "sk_5c61605bb833ad4c33aa7beeb040a90fcb04c8cf46cfca90",
    "sk_0cf381442ff2c0e9f8d9a44935c5ad8d508e5759f5e25d8d",
    "sk_260b999f13f0b0961612a3bcb632662c6e2acb83c9b45c61",
    "sk_ca89570086b3283a1b47ab226bfb3363a9a769be85523201",
    "sk_e07658e04b32501d6e02abc916df4404b0dee7092386139b",
    "sk_0fbfa238ba251b68f04e5d5b59458fd04366d2573d584061",
    "sk_9dfef43b5fd22fe76cfd667b12daaa2bd0c66463066582ea",
    "sk_6a63a8a822d6a47664245bc40b70a6133b8f84ff9c471bd8",
    "sk_f3ec8cc7156d48de8844d182025b36510a5f9f92ac427c4d",
    "sk_d0ccf90118e17d1fcc71c00deee22060a3ac79f7e1ec93f5",
    "sk_fd62fe586c4c3b9c7997578919a63019dd7fd46f81af34c1",
    "sk_a4c6c403d863f3cb062aceb3d327acf076f3ff9b5be06127",
    "sk_a632c725b0ac4bbeba1c188627d4271c76ee93b1a7fbf13f",
    "sk_a160d0984d02d3b469ce3f85fe27189b3b74694a4123cc3c",
    "sk_9f130d8c6c198cfe762c9f8d0b95a348f790697778ff56c6",
    "sk_b215e4a058f750ec63f5a7d47d11f3f8b3fdcc517e0d86ca",
    "sk_5ab8a0f10143716e4e688b925025dbdd9ce571441dcd5f22",
    "sk_8ed96913f4daf2d6096d8c13841dc3e6330fb8411525e8b5",
    "sk_cae54e8ffe801ebf2b91af0eeee36c0ab48dc4004a0960f6",
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
    "bIHbv24MWmeRgasZH58o"
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
