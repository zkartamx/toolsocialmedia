import subprocess
import sys
import os
import whisper
import torch
from pyannote.audio import Pipeline
import pandas as pd
from gtts import gTTS
from deep_translator import GoogleTranslator
from datetime import datetime

# Importar la configuración local
try:
    from config import HUGGING_FACE_TOKEN
except ImportError:
    HUGGING_FACE_TOKEN = None

# --- CONFIGURACIÓN ---
CARPETA_VIDEOS = 'videos'
CARPETA_AUDIOS = 'audios'
CARPETA_TRANSCRIPCIONES = 'transcripciones'
CARPETA_AUDIO_SINTETIZADO = 'audio_sintetizado'
CARPETA_TEST_OUTPUTS = 'test_outputs'

# --- FUNCIONES DE UTILIDAD ---

def crear_carpetas_necesarias():
    """Asegura que todas las carpetas necesarias para el proyecto existan."""
    for carpeta in [CARPETA_VIDEOS, CARPETA_AUDIOS, CARPETA_TRANSCRIPCIONES, CARPETA_AUDIO_SINTETIZADO, CARPETA_TEST_OUTPUTS]:
        os.makedirs(carpeta, exist_ok=True)

# --- FUNCIONES DE EXTRACCIÓN ---

def extraer_audio(ruta_video):
    if not os.path.exists(ruta_video):
        print(f"ERROR: El archivo '{ruta_video}' no fue encontrado.")
        return None

    os.makedirs(CARPETA_AUDIOS, exist_ok=True)
    nombre_base = os.path.splitext(os.path.basename(ruta_video))[0]
    ruta_salida_mp3 = os.path.join(CARPETA_AUDIOS, f"{nombre_base}.mp3")

    print(f"INFO: Iniciando extracción de audio de '{ruta_video}'...")
    comando = ['ffmpeg', '-i', ruta_video, '-q:a', '0', '-map', 'a', '-y', ruta_salida_mp3]
    try:
        subprocess.run(comando, check=True, capture_output=True, text=True)
        print(f"SUCCESS: Audio guardado en '{ruta_salida_mp3}'")
        return ruta_salida_mp3
    except subprocess.CalledProcessError as e:
        print(f"ERROR con FFmpeg extrayendo audio: {e.stderr}")
        return None

def descargar_video_youtube(url, start_time=None, end_time=None):
    """
    Descarga un video de YouTube, opcionalmente cortando un segmento específico.
    Optimizado para velocidad forzando el formato MP4 y con validación de tiempo mejorada.
    Devuelve una tupla (ruta_del_archivo, mensaje_de_error).
    """
    print(f"INFO: Iniciando descarga de video desde: {url}")
    os.makedirs(CARPETA_VIDEOS, exist_ok=True)

    # --- Validar y procesar tiempos de forma robusta ---
    cortar_video = bool(start_time and end_time)
    
    if (start_time and not end_time) or (not start_time and end_time):
        error_msg = "Debes especificar tanto el tiempo de inicio como el de fin para cortar el video."
        print(f"ERROR: {error_msg}")
        return None, error_msg

    if cortar_video:
        try:
            datetime.strptime(start_time, '%H:%M:%S')
            datetime.strptime(end_time, '%H:%M:%S')
        except ValueError:
            error_msg = "Formato de tiempo inválido. Usa HH:MM:SS."
            print(f"ERROR: {error_msg}")
            return None, error_msg

    # --- Determinar la ruta de salida de forma robusta ---
    try:
        get_name_cmd = ['yt-dlp', '--get-filename', '-o', '%(title)s.%(ext)s', url]
        nombre_base_original = subprocess.run(get_name_cmd, check=True, capture_output=True, text=True, encoding='utf-8').stdout.strip()
        
        nombre_base, extension = os.path.splitext(nombre_base_original)
        nombre_base_limpio = "".join([c for c in nombre_base if c.isalpha() or c.isdigit() or c in (' ', '_', '-')]).rstrip()

        if cortar_video:
            nombre_final = f"{nombre_base_limpio}_cut_{start_time.replace(':', '')}_{end_time.replace(':', '')}.mp4"
        else:
            nombre_final = f"{nombre_base_limpio}.mp4"
            
        ruta_salida_final = os.path.join(CARPETA_VIDEOS, nombre_final)

    except subprocess.CalledProcessError as e:
        error_msg = f"No se pudo obtener el nombre del archivo de yt-dlp: {e.stderr}"
        print(f"ERROR: {error_msg}")
        return None, error_msg

    # --- Construir y ejecutar el comando de descarga optimizado ---
    # Forzar formato a MP4 para optimizar el corte y evitar re-codificación.
    comando = ['yt-dlp', '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', '-o', ruta_salida_final]

    if cortar_video:
        comando.extend([
            '--download-sections', f'*{start_time}-{end_time}',
            '--force-keyframes-at-cuts'
        ])

    comando.append(url)

    # --- Ejecutar el comando ---
    try:
        print(f"INFO: Ejecutando comando: {' '.join(comando)}")
        resultado = subprocess.run(comando, check=True, capture_output=True, text=True, encoding='utf-8')
        print("SUCCESS: Proceso de descarga de yt-dlp finalizado.")

        if os.path.exists(ruta_salida_final):
            print(f"SUCCESS: Video guardado en '{ruta_salida_final}'")
            return ruta_salida_final, None
        else:
            error_msg = "El archivo de video no fue encontrado después de la descarga."
            print(f"ERROR: {error_msg}")
            return None, error_msg

    except subprocess.CalledProcessError as e:
        if os.path.exists(ruta_salida_final):
            print(f"SUCCESS: Video guardado en '{ruta_salida_final}' (a pesar de un error de yt-dlp, el archivo existe).")
            return ruta_salida_final, None
        
        stderr_output = e.stderr.lower()
        if "ffmpeg" in stderr_output or "ffprobe" in stderr_output:
            error_msg = "Error con FFmpeg. Asegúrate de que esté instalado y en el PATH."
        else:
            error_msg = f"Falló la descarga con yt-dlp. Error:\n{e.stderr}"
        
        print(f"ERROR: {error_msg}")
        return None, error_msg
    except Exception as e:
        error_msg = f"Ocurrió un error inesperado durante la descarga: {e}"
        print(f"ERROR: {error_msg}")
        return None, error_msg

# --- FUNCIONES DE TRANSCRIPCIÓN ---

def transcribir_y_diarizar(ruta_audio, diarizar=True, model_size="medium"):
    """Transcribe un archivo de audio, devuelve la ruta de la transcripción y el idioma detectado."""
    if diarizar and not HUGGING_FACE_TOKEN:
        print("ERROR: El token de Hugging Face no está configurado para la diarización.")
        return None, None

    token = HUGGING_FACE_TOKEN

    print(f"INFO: Cargando modelo de Whisper ({model_size})...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    modelo_whisper = whisper.load_model(model_size, device=device)
    print(f"INFO: Usando dispositivo: {device}")
    
    try:
        print(f"STEP 1/2: Transcripción para: {ruta_audio}")
        transcription_result = modelo_whisper.transcribe(ruta_audio, word_timestamps=True)
        detected_language = transcription_result.get('language', 'unknown')
        print(f"INFO: Idioma detectado: {detected_language}")

        final_transcript_text = ""
        if diarizar:
            print("INFO: Cargando modelo de diarización...")
            diarization_pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=token)
            diarization_pipeline = diarization_pipeline.to(device)
            
            print(f"STEP 2/2: Diarización y combinación para: {ruta_audio}")
            diarization_result = diarization_pipeline(ruta_audio)
            final_transcript_segments = get_transcript_with_speakers(diarization_result, transcription_result["segments"])
            
            for segment in final_transcript_segments:
                final_transcript_text += f"[{segment['speaker']}] ({segment['start']:.2f}s - {segment['end']:.2f}s)\n"
                final_transcript_text += f"{segment['text'].strip()}\n\n"
        else:
            final_transcript_text = transcription_result["text"]

        os.makedirs(CARPETA_TRANSCRIPCIONES, exist_ok=True)
        nombre_base = os.path.splitext(os.path.basename(ruta_audio))[0]
        ruta_salida_txt = os.path.join(CARPETA_TRANSCRIPCIONES, f"{nombre_base}_transcripcion.txt")

        with open(ruta_salida_txt, "w", encoding='utf-8') as f:
            f.write(final_transcript_text)

        print(f"SUCCESS: Transcripción guardada en: {ruta_salida_txt}")
        return ruta_salida_txt, detected_language

    except Exception as e:
        print(f"ERROR durante el proceso de IA: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def get_transcript_with_speakers(diarization, whisper_segments):
    def get_speaker_from_time(time, diarization_result):
        for turn, _, speaker in diarization_result.itertracks(yield_label=True):
            if turn.start <= time <= turn.end:
                return speaker
        return "[Hablante Desconocido]"

    transcript = []
    current_speaker = None
    current_segment = None

    word_list = [word for seg in whisper_segments for word in seg.get('words', [])]

    for i, word in enumerate(word_list):
        word_mid_time = (word['start'] + word['end']) / 2
        speaker = get_speaker_from_time(word_mid_time, diarization)

        if current_segment and speaker != current_speaker:
            transcript.append(current_segment)
            current_segment = None

        if not current_segment:
            current_speaker = speaker
            current_segment = {
                "speaker": speaker,
                "text": word['word'].strip(),
                "start": word['start'],
                "end": word['end']
            }
        else:
            current_segment["text"] += " " + word['word'].strip()
            current_segment["end"] = word['end']
            
    if current_segment:
        transcript.append(current_segment)

    return transcript

# --- FUNCIONES DE TRADUCCIÓN Y SÍNTESIS ---

def detectar_idioma(texto):
    """Detecta el idioma de un texto dado."""
    try:
        # La función detect() devuelve un objeto Detected. Ej: Detected(lang=es, confidence=1)
        detected_obj = GoogleTranslator(source='auto', target='en').detect(texto)
        # El objeto tiene un atributo 'lang' con el código del idioma.
        if detected_obj and hasattr(detected_obj, 'lang'):
            idioma_detectado = detected_obj.lang
            print(f"INFO: Idioma detectado: {idioma_detectado}")
            return idioma_detectado
        return None # No se detectó ningún idioma
    except Exception as e:
        print(f"ERROR al detectar el idioma: {e}")
        return None

def traducir_texto(texto, idioma_origen='auto', idioma_destino='es'):
    """
    Traduce un texto de un idioma de origen a un idioma de destino.
    """
    try:
        print(f"INFO: Traduciendo texto de '{idioma_origen}' a '{idioma_destino}'...")
        traducido = GoogleTranslator(source=idioma_origen, target=idioma_destino).translate(texto)
        print("SUCCESS: Texto traducido.")
        return traducido
    except Exception as e:
        print(f"ERROR traduciendo texto: {e}")
        return None

def traducir_y_sintetizar_audio(ruta_audio):
    """
    Traduce y sintetiza audio. Si el audio ya está en español, solo lo sintetiza.
    """
    print(f"--- INICIANDO PROCESO DE TRADUCCIÓN/SÍNTESIS PARA: {ruta_audio} ---")
    
    # 1. Transcribir y detectar idioma
    ruta_transcripcion, idioma_detectado = transcribir_y_diarizar(ruta_audio, diarizar=False)
    if not ruta_transcripcion:
        print("ERROR: No se pudo obtener la transcripción.")
        return None, None

    with open(ruta_transcripcion, 'r', encoding='utf-8') as f:
        texto_original = f.read()

    nombre_base = os.path.splitext(os.path.basename(ruta_audio))[0]
    texto_final = ""
    ruta_transcripcion_final = ""
    sufijo_audio = ""

    # 2. Decidir si traducir o solo sintetizar
    if idioma_detectado == 'es':
        print("INFO: El audio ya está en español. Omitiendo traducción.")
        texto_final = texto_original
        ruta_transcripcion_final = ruta_transcripcion # Reutilizamos la transcripción original
        sufijo_audio = "_sintetizado_es"
    else:
        print(f"INFO: Traduciendo de '{idioma_detectado}' a español.")
        texto_final = traducir_texto(texto_original, idioma_origen=idioma_detectado, idioma_destino='es')
        if not texto_final:
            return None, None
        
        ruta_transcripcion_final = os.path.join(CARPETA_TRANSCRIPCIONES, f"{nombre_base}_traduccion_es.txt")
        with open(ruta_transcripcion_final, 'w', encoding='utf-8') as f:
            f.write(texto_final)
        print(f"INFO: Transcripción traducida guardada en: {ruta_transcripcion_final}")
        sufijo_audio = "_traducido_es"

    # 3. Sintetizar el texto final
    ruta_audio_sintetizado = sintetizar_texto_a_audio(texto_final, nombre_base, sufijo=sufijo_audio)
    if not ruta_audio_sintetizado:
        return None, None

    print(f"SUCCESS: Proceso de audio completado.")
    return ruta_audio_sintetizado, ruta_transcripcion_final

def sintetizar_texto_a_audio(texto, nombre_base, sufijo="_sintetizado", lang='es'):
    """Función interna para sintetizar texto con gTTS y guardar el archivo."""
    try:
        os.makedirs(CARPETA_AUDIO_SINTETIZADO, exist_ok=True)
        ruta_salida_mp3 = os.path.join(CARPETA_AUDIO_SINTETIZADO, f"{nombre_base}{sufijo}.mp3")

        print(f"INFO: Sintetizando texto con gTTS...")
        tts = gTTS(text=texto, lang=lang, slow=False)
        tts.save(ruta_salida_mp3)
        print(f"SUCCESS: Audio sintetizado guardado en '{ruta_salida_mp3}'")
        return ruta_salida_mp3
    except Exception as e:
        print(f"ERROR sintetizando audio con gTTS: {e}")
        return None


def sintetizar_gtts(texto_o_ruta, es_ruta_archivo=True, lang='es'):
    """
    Sintetiza texto a audio usando gTTS.
    Puede recibir una ruta a un archivo de transcripción o una cadena de texto directamente.
    Permite especificar el idioma para la síntesis.
    """
    texto_a_sintetizar = ""
    nombre_base = ""

    if es_ruta_archivo:
        ruta_transcripcion = texto_o_ruta
        if not os.path.exists(ruta_transcripcion):
            print(f"ERROR: El archivo de transcripción '{ruta_transcripcion}' no fue encontrado.")
            return None
        
        print(f"INFO: Leyendo transcripción de '{ruta_transcripcion}' para sintetizar...")
        try:
            with open(ruta_transcripcion, "r", encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    # Extraer solo el texto, ignorando timestamps y nombres de hablantes
                    partes = line.split(')')
                    texto = partes[-1].strip() if len(partes) > 1 else line
                    if texto and not texto.startswith('['):
                        texto_a_sintetizar += texto + " "
            
            nombre_base = os.path.splitext(os.path.basename(ruta_transcripcion))[0]
        except Exception as e:
            print(f"ERROR leyendo o procesando el archivo de transcripción: {e}")
            return None
    else:
        texto_a_sintetizar = texto_o_ruta
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_base = f"sintesis_manual_{timestamp}"

    texto_a_sintetizar = texto_a_sintetizar.strip()
    if not texto_a_sintetizar:
        print("WARNING: No se encontró texto para sintetizar.")
        return None

    return sintetizar_texto_a_audio(texto_a_sintetizar, nombre_base, lang=lang)


# --- LÓGICA PRINCIPAL ---

if __name__ == "__main__":
    import argparse

    crear_carpetas_necesarias()

    parser = argparse.ArgumentParser(description="Extractor y transcriptor de audio desde YouTube o archivos locales.")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--url', type=str, help="URL de YouTube para procesar.")
    group.add_argument('--file', type=str, help="Ruta a un archivo de video o audio local para procesar.")
    group.add_argument('--sintetizar', type=str, help="Ruta a un archivo de transcripción (.txt) para sintetizar con gTTS.")

    parser.add_argument('--model-size', type=str, default="medium", help="Tamaño del modelo de Whisper a utilizar (pequeño, mediano, grande).")

    args = parser.parse_args()

    ruta_audio_final = None
    
    if args.url:
        print(f"--- PROCESANDO URL: {args.url} ---")
        ruta_video = descargar_video_youtube(args.url)
        if ruta_video:
            ruta_audio_final = extraer_audio(ruta_video)
    
    elif args.file:
        print(f"--- PROCESANDO ARCHIVO: {args.file} ---")
        if not os.path.exists(args.file):
            print(f"ERROR: El archivo '{args.file}' no existe.")
            sys.exit(1)
        
        if args.file.lower().endswith(('.mp3', '.wav', '.m4a')):
            ruta_audio_final = args.file
        else:
            ruta_audio_final = extraer_audio(args.file)

    elif args.sintetizar:
        print(f"--- SINTETIZANDO TRANSCRIPCIÓN: {args.sintetizar} ---")
        sintetizar_gtts(args.sintetizar, es_ruta_archivo=True)
        sys.exit(0)

    if ruta_audio_final:
        print("--- INICIANDO TRANSCRIPCIÓN ---")
        transcribir_y_diarizar(ruta_audio_final, model_size=args.model_size)
    else:
        print("ERROR: No se pudo obtener un archivo de audio válido para procesar.")
        sys.exit(1)

    print("\n--- PROCESO COMPLETADO ---")
