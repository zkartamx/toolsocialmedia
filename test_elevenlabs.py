import os
from elevenlabs.client import ElevenLabs

# Asegúrate de que tu API Key esté configurada en config.py
try:
    from config import ELEVEN_LABS_API_KEY
except ImportError:
    ELEVEN_LABS_API_KEY = None

if ELEVEN_LABS_API_KEY == "TU_API_KEY_DE_ELEVEN_LABS_AQUI" or not ELEVEN_LABS_API_KEY:
    print("ERROR: Por favor, configura tu ELEVEN_LABS_API_KEY en config.py")
    exit()

client = ElevenLabs(api_key=ELEVEN_LABS_API_KEY)

text_to_generate = "Hola, esto es una prueba de Eleven Labs desde Python."
output_folder = "test_outputs"
os.makedirs(output_folder, exist_ok=True)
output_path = os.path.join(output_folder, "test_elevenlabs.mp3")

try:
    print(f"Intentando generar audio: \"{text_to_generate}\"...")
    audio = client.generate(
        text=text_to_generate,
        voice="21m00Tcm4TlvDq8ikWAM", # Adam
        model_id="eleven_multilingual_v2"
    )

    with open(output_path, "wb") as f:
        f.write(audio)
    print(f"SUCCESS: Audio de prueba guardado en {output_path}")

except Exception as e:
    print(f"ERROR al generar audio con Eleven Labs: {e}")
