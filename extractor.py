import subprocess
import sys
import os
import whisper
import torch
from pyannote.audio import Pipeline
import pandas as pd
from gtts import gTTS
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

# --- FUNCIONES DE UTILIDAD ---

def crear_carpetas_necesarias():
    """Asegura que todas las carpetas necesarias para el proyecto existan."""
    for carpeta in [CARPETA_VIDEOS, CARPETA_AUDIOS, CARPETA_TRANSCRIPCIONES, CARPETA_AUDIO_SINTETIZADO]:
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
    Requiere que ffmpeg esté instalado y en el PATH si se usan tiempos de corte.
    """
    print(f"INFO: Iniciando descarga de video desde: {url}")
    os.makedirs(CARPETA_VIDEOS, exist_ok=True)
    
    archivos_antes = set(os.listdir(CARPETA_VIDEOS))
    
    if start_time and end_time:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo_plantilla = f"Fragmento1_{timestamp}.%(ext)s"
        plantilla_salida = os.path.join(CARPETA_VIDEOS, nombre_archivo_plantilla)
    else:
        plantilla_salida = os.path.join(CARPETA_VIDEOS, '%(title)s.%(ext)s')

    comando = ['yt-dlp', '-f', 'best', '-o', plantilla_salida]

    if start_time and end_time:
        # Formato para yt-dlp: *START-END
        # Usar ffmpeg para el corte es más preciso que --download-sections
        comando.extend(['--downloader', 'ffmpeg'])
        downloader_args = f"ffmpeg_i:-ss {start_time} -to {end_time}"
        comando.extend(['--downloader-args', downloader_args])

    comando.append(url)
    
    try:
        print(f"INFO: Ejecutando comando: {' '.join(comando)}")
        resultado = subprocess.run(comando, check=True, capture_output=True, text=True, encoding='utf-8')
        print("SUCCESS: Proceso de descarga de yt-dlp finalizado.")

    except subprocess.CalledProcessError as e:
        print(f"ERROR: yt-dlp falló con el código de salida {e.returncode}.")
        print("--- Salida de yt-dlp (stdout) ---")
        print(e.stdout)
        print("--- Salida de yt-dlp (stderr) ---")
        print(e.stderr)
        print("---------------------------------")
        return None
    except FileNotFoundError:
        print("ERROR: El comando 'yt-dlp' no fue encontrado. Asegúrate de que esté instalado y en tu PATH.")
        return None

    # Para depuración, siempre mostramos la salida de yt-dlp
    print("--- Salida de yt-dlp (stdout) ---")
    print(resultado.stdout)
    print("--- Salida de yt-dlp (stderr) ---")
    print(resultado.stderr)
    print("---------------------------------")

    # Estrategia 1: Detectar un archivo nuevo en la carpeta de destino.
    archivos_despues = set(os.listdir(CARPETA_VIDEOS))
    nuevos_archivos = archivos_despues - archivos_antes
    if nuevos_archivos:
        nombre_nuevo_archivo = nuevos_archivos.pop()
        ruta_video = os.path.join(CARPETA_VIDEOS, nombre_nuevo_archivo)
        print(f"INFO: Archivo nuevo detectado por estrategia 1: '{ruta_video}'")
        return ruta_video

    # Estrategia 2: Si no hay archivo nuevo, analizar la salida de yt-dlp.
    print("INFO: No se detectó un archivo nuevo. Analizando salida de yt-dlp (estrategia 2)...")
    for line in resultado.stdout.splitlines():
        # Caso 1: Descarga directa
        if "[download] Destination:" in line:
            ruta_video = line.split("Destination:")[-1].strip()
            if os.path.exists(ruta_video):
                print(f"INFO: Archivo encontrado en 'Destination': '{ruta_video}'")
                return ruta_video
        # Caso 2: Fusión de formatos
        if "[Merger] Merging formats into" in line:
            try:
                ruta_video = line.split('"')[1]
                if os.path.exists(ruta_video):
                    print(f"INFO: Archivo encontrado en 'Merger': '{ruta_video}'")
                    return ruta_video
            except IndexError:
                continue # La línea no tiene el formato esperado
        # Caso 3: El archivo ya ha sido descargado
        if "has already been downloaded" in line:
            try:
                # La ruta está entre el prefijo '[download] ' y el sufijo ' has already been downloaded'
                ruta_video = line.removeprefix('[download] ').removesuffix(' has already been downloaded').strip()
                if os.path.exists(ruta_video):
                    print(f"INFO: Archivo encontrado porque ya existía: '{ruta_video}'")
                    return ruta_video
            except Exception:
                continue # La línea no tiene el formato esperado

    print("ERROR: No se pudo determinar la ruta del archivo descargado. yt-dlp finalizó pero no se encontró el archivo.")
    return None

# --- FUNCIONES DE TRANSCRIPCIÓN ---

def transcribir_y_diarizar(ruta_audio, diarizar=True, model_size="medium"):
    """Transcribe un archivo de audio utilizando Whisper y opcionalmente realiza diarización."""
    if diarizar and not HUGGING_FACE_TOKEN:
        print("ERROR: El token de Hugging Face no está configurado para la diarización.")
        print("Por favor, añádelo a tu archivo config.py como HUGGING_FACE_TOKEN = 'tu_token_aqui'")
        return None

    token = HUGGING_FACE_TOKEN

    print(f"INFO: Cargando modelo de Whisper ({model_size})...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    modelo_whisper = whisper.load_model(model_size, device=device)
    print(f"INFO: Usando dispositivo: {device}")
    
    try:
        # La transcripción siempre se realiza
        print(f"STEP 1/2: Transcripción para: {ruta_audio}")
        transcription_result = modelo_whisper.transcribe(ruta_audio, word_timestamps=True)

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
            print("STEP 2/2: Diarización omitida. Formateando transcripción.")
            final_transcript_text = transcription_result["text"]

        os.makedirs(CARPETA_TRANSCRIPCIONES, exist_ok=True)
        nombre_base = os.path.splitext(os.path.basename(ruta_audio))[0]
        ruta_salida_txt = os.path.join(CARPETA_TRANSCRIPCIONES, f"{nombre_base}_transcripcion.txt")

        with open(ruta_salida_txt, "w", encoding='utf-8') as f:
            f.write(final_transcript_text)

        print(f"SUCCESS: Transcripción guardada en: {ruta_salida_txt}")
        return ruta_salida_txt

    except Exception as e:
        print(f"ERROR durante el proceso de IA: {e}")
        import traceback
        traceback.print_exc()
        return None

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

# --- FUNCIONES DE SÍNTESIS DE VOZ ---

def sintetizar_audio_gtts(ruta_transcripcion):
    """
    Lee un archivo de transcripción, extrae solo el texto hablado y lo sintetiza usando gTTS.
    Devuelve la ruta del archivo de audio sintetizado.
    """
    if not os.path.exists(ruta_transcripcion):
        print(f"ERROR: El archivo de transcripción '{ruta_transcripcion}' no fue encontrado.")
        return None

    print(f"INFO: Leyendo transcripción de '{ruta_transcripcion}' para sintetizar...")
    texto_a_sintetizar = ""
    try:
        with open(ruta_transcripcion, "r", encoding='utf-8') as f:
            for line in f:
                if not line.strip().startswith('[') and not line.strip().startswith('(') and line.strip():
                    texto_a_sintetizar += line.strip() + " "
        
        texto_a_sintetizar = texto_a_sintetizar.strip()
        if not texto_a_sintetizar:
            print("WARNING: No se encontró texto para sintetizar en el archivo.")
            return None

        os.makedirs(CARPETA_AUDIO_SINTETIZADO, exist_ok=True)
        nombre_base = os.path.splitext(os.path.basename(ruta_transcripcion))[0]
        ruta_salida_mp3 = os.path.join(CARPETA_AUDIO_SINTETIZADO, f"{nombre_base}_sintetizado.mp3")

        print(f"INFO: Sintetizando texto con gTTS...")
        tts = gTTS(text=texto_a_sintetizar, lang='es')
        tts.save(ruta_salida_mp3)
        print(f"SUCCESS: Audio sintetizado guardado en '{ruta_salida_mp3}'")
        return ruta_salida_mp3

    except Exception as e:
        print(f"ERROR sintetizando audio con gTTS: {e}")
        return None

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
        sintetizar_audio_gtts(args.sintetizar)
        sys.exit(0)

    if ruta_audio_final:
        print("--- INICIANDO TRANSCRIPCIÓN ---")
        transcribir_y_diarizar(ruta_audio_final, model_size=args.model_size)
    else:
        print("ERROR: No se pudo obtener un archivo de audio válido para procesar.")
        sys.exit(1)

    print("\n--- PROCESO COMPLETADO ---")
