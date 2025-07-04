import gradio as gr
import os
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
import uvicorn

from extractor import (
    crear_carpetas_necesarias,
    descargar_video_youtube,
    extraer_audio,
    transcribir_y_diarizar,
    sintetizar_gtts,
    traducir_texto,
    traducir_y_sintetizar_audio,
    detectar_idioma
)

# --- Modelos de Pydantic para la API ---
class DownloadRequest(BaseModel):
    url: str
    start_time: str | None = None
    end_time: str | None = None

class FilePathRequest(BaseModel):
    file_path: str

class TranslateTextRequest(BaseModel):
    text: str
    target_language: str = 'es'

class TranscriptionRequest(BaseModel):
    file_path: str
    model_size: str = "medium"
    diarize: bool = True

class SynthesisRequest(BaseModel):
    file_path: str

class AudioRequest(BaseModel):
    file_path: str

# --- Inicialización ---
crear_carpetas_necesarias()


# --- Lógica de la API de FastAPI ---
app = FastAPI(title="Extractor API", description="API para procesar y generar multimedia.")

# --- Modelos de Datos para la API ---
class SynthesisRequest(BaseModel):
    texto: str
    idioma_origen: str = 'es'
    idioma_destino: str = 'en'

# --- Endpoints de la API ---
@app.post("/api/sintetizar/", 
          tags=["Síntesis"],
          summary="Traduce y sintetiza texto a voz",
          response_class=FileResponse)
async def api_sintetizar(request: SynthesisRequest):
    """
    Recibe un texto y lo convierte en un archivo de audio.

    - **texto**: El texto que quieres convertir a voz.
    - **idioma_origen**: El idioma del texto original (ej. 'es').
    - **idioma_destino**: El idioma en el que quieres generar el audio (ej. 'en').

    Si los idiomas son diferentes, el texto se traducirá primero. 
    La API devuelve directamente el archivo de audio MP3.
    """
    texto_a_sintetizar = request.texto
    
    # 1. Traducir si es necesario
    if request.idioma_origen != request.idioma_destino:
        print(f"API: Traduciendo de '{request.idioma_origen}' a '{request.idioma_destino}'...")
        texto_traducido = traducir_texto(
            request.texto, 
            idioma_origen=request.idioma_origen, 
            idioma_destino=request.idioma_destino
        )
        if not texto_traducido:
            raise HTTPException(status_code=500, detail="La traducción falló.")
        texto_a_sintetizar = texto_traducido
    
    # 2. Sintetizar
    print(f"API: Sintetizando texto en '{request.idioma_destino}'...")
    ruta_audio = sintetizar_gtts(
        texto_a_sintetizar, 
        es_ruta_archivo=False, 
        lang=request.idioma_destino
    )
    
    if not ruta_audio or not os.path.exists(ruta_audio):
        raise HTTPException(status_code=500, detail="La síntesis de audio falló.")
        
    # 3. Devolver el archivo de audio
    return FileResponse(path=ruta_audio, media_type='audio/mpeg', filename=os.path.basename(ruta_audio))

@app.get("/")
def root():
    return RedirectResponse(url="/gradio")

@app.post("/api/download")
def api_download(request: DownloadRequest):
    path, error_msg = descargar_video_youtube(request.url, request.start_time, request.end_time)
    if error_msg:
        raise HTTPException(status_code=500, detail=f"Error al descargar el video: {error_msg}")
    return {"message": "Video descargado con éxito", "path": path}

@app.post("/api/extract_audio")
def api_extract_audio(request: FilePathRequest):
    path = extraer_audio(request.file_path)
    if not path:
        raise HTTPException(status_code=500, detail="Error al extraer el audio.")
    return {"message": "Audio extraído con éxito", "path": path}

@app.post("/api/transcribe")
def api_transcribe(request: TranscriptionRequest):
    path, _ = transcribir_y_diarizar(request.file_path, diarizar=request.diarize, model_size=request.model_size)
    if not path:
        raise HTTPException(status_code=500, detail="Error al transcribir.")
    with open(path, 'r', encoding='utf-8') as f:
        transcription = f.read()
    return {"message": "Transcripción completada", "path": path, "transcription": transcription}

@app.post("/api/synthesize")
def api_synthesize(request: FilePathRequest):
    path = sintetizar_gtts(request.file_path, es_ruta_archivo=True)
    if not path:
        raise HTTPException(status_code=500, detail="Error al sintetizar.")
    return {"message": "Audio sintetizado con éxito", "path": path}

@app.post("/api/translate-text")
def api_translate_text(request: TranslateTextRequest):
    translated_text = traducir_texto(request.text, request.target_language)
    if not translated_text:
        raise HTTPException(status_code=500, detail="Error durante la traducción del texto")
    return {"original_text": request.text, "translated_text": translated_text}

@app.post("/api/translate-audio")
def api_translate_audio(request: AudioRequest):
    audio_path, transcript_path = traducir_y_sintetizar_audio(request.file_path)
    if not audio_path or not transcript_path:
        raise HTTPException(status_code=500, detail="Error durante la traducción del audio")
    return {"message": "Traducción de audio completada", "translated_audio_path": audio_path, "translated_transcript_path": transcript_path}

# --- Funciones de la Interfaz de Gradio (Actualizadas para el nuevo diseño) ---

def descargar_video_action(url, start_time, end_time, progress=gr.Progress(track_tqdm=True)):
    """Acción para descargar el video. Devuelve la ruta y actualiza la UI."""
    if not url:
        raise gr.Error("Por favor, introduce una URL de YouTube.")

    start_time = start_time.strip() if start_time else None
    end_time = end_time.strip() if end_time else None
    
    progress(0, desc="Descargando video...")
    ruta_video, error_msg = descargar_video_youtube(url, start_time, end_time)
    
    if error_msg:
        progress(1)
        raise gr.Error(f"Error en la descarga: {error_msg}")
    
    progress(1, desc="¡Descarga completada!")
    return ruta_video, f"Descarga completada: {os.path.basename(ruta_video)}", gr.Video(value=ruta_video), gr.Accordion(open=False), gr.Accordion(open=True)

def process_uploaded_video(video_file):
    """Procesa un video cargado, lo muestra y prepara para el siguiente paso."""
    if not video_file:
        return None, "", None, gr.Accordion(open=True), gr.Accordion(open=False)
    return video_file.name, "Video cargado. Listo para extraer audio.", gr.Video(value=video_file.name), gr.Accordion(open=False), gr.Accordion(open=True)

def extraer_audio_action(ruta_video, progress=gr.Progress(track_tqdm=True)):
    """Acción para extraer el audio. Devuelve la ruta del audio y actualiza la UI."""
    if not ruta_video:
        raise gr.Error("No hay un video para procesar. Completa el PASO 1.")

    progress(0, desc="Extrayendo audio...")
    ruta_audio = extraer_audio(ruta_video)
    progress(1)

    if not ruta_audio:
        raise gr.Error("La extracción de audio falló. Revisa los registros.")

    return f"Audio extraído: {os.path.basename(ruta_audio)}", gr.Audio(value=ruta_audio, type="filepath"), ruta_audio, gr.Accordion(open=False), gr.Accordion(open=True)

def process_uploaded_audio(audio_file):
    """Procesa un audio cargado, lo muestra y prepara para el siguiente paso."""
    if not audio_file:
        return "", None, None, gr.Accordion(open=True), gr.Accordion(open=False)
    return "Audio cargado. Listo para transcribir.", gr.Audio(value=audio_file.name, type="filepath"), audio_file.name, gr.Accordion(open=False), gr.Accordion(open=True)

def transcribir_action(ruta_audio, model_size, diarizar, progress=gr.Progress(track_tqdm=True)):
    """Acción para transcribir el audio y mostrar el resultado."""
    if not ruta_audio:
        raise gr.Error("No hay un archivo de audio para transcribir. Completa el PASO 2.")

    progress(0, desc=f"Transcribiendo con el modelo {model_size}...")
    ruta_transcripcion, _ = transcribir_y_diarizar(ruta_audio, diarizar=diarizar, model_size=model_size)
    progress(1)
    
    if not ruta_transcripcion:
        raise gr.Error("La transcripción falló. Revisa los registros para más detalles.")

    with open(ruta_transcripcion, 'r', encoding='utf-8') as f:
        texto_transcrito = f.read()
    
    return f"Transcripción guardada en: {ruta_transcripcion}", texto_transcrito, ruta_transcripcion, gr.Accordion(open=False), gr.Accordion(open=True), gr.Accordion(open=True)

def process_uploaded_transcript(transcript_file):
    """Procesa un archivo de transcripción cargado."""
    if not transcript_file:
        return "", None, None, gr.Accordion(open=True), gr.Accordion(open=False), gr.Accordion(open=False)
    
    with open(transcript_file.name, 'r', encoding='utf-8') as f:
        contenido = f.read()
    
    return f"Transcripción cargada desde {os.path.basename(transcript_file.name)}", contenido, transcript_file.name, gr.Accordion(open=False), gr.Accordion(open=True), gr.Accordion(open=True)

def traducir_action(ruta_audio, progress=gr.Progress(track_tqdm=True)):
    """Acción para traducir y sintetizar el audio, manejando la actualización de la UI."""
    if not ruta_audio:
        raise gr.Error("No hay un archivo de audio para traducir. Completa el PASO 2.")

    progress(0, desc="Traduciendo y sintetizando...")
    ruta_audio_traducido, ruta_transcripcion_traducida = traducir_y_sintetizar_audio(ruta_audio)
    progress(1)

    if not ruta_audio_traducido:
        raise gr.Error("El proceso de traducción y síntesis falló.")

    return "Proceso completado.", gr.Audio(value=ruta_audio_traducido, type="filepath"), gr.File(value=ruta_transcripcion_traducida)

def sintetizar_action(ruta_transcripcion, progress=gr.Progress(track_tqdm=True)):
    """Acción para sintetizar el audio desde una transcripción."""
    if not ruta_transcripcion:
        raise gr.Error("No hay una transcripción para sintetizar. Completa el PASO 3.")

    progress(0, desc="Sintetizando audio...")
    ruta_audio_sintetizado = sintetizar_gtts(ruta_transcripcion, es_ruta_archivo=True)
    progress(1)

    if not ruta_audio_sintetizado:
        raise gr.Error("La síntesis de audio falló.")

    return "Síntesis completada.", gr.Audio(value=ruta_audio_sintetizado, type="filepath")

def traducir_manual_action(texto_manual, idioma_origen, idioma_destino, progress=gr.Progress(track_tqdm=True)):
    """Traduce el texto manualmente de un idioma de origen a uno de destino."""
    if not texto_manual.strip():
        raise gr.Error("El campo de texto original no puede estar vacío.")

    if idioma_origen == idioma_destino:
        progress(1, desc="El idioma de origen y destino son los mismos.")
        return f"(No se requiere traducción)\n\n{texto_manual}"

    progress(0.5, desc=f"Traduciendo de '{idioma_origen}' a '{idioma_destino}'...")
    texto_traducido = traducir_texto(texto_manual, idioma_origen=idioma_origen, idioma_destino=idioma_destino)
    progress(1)

    if not texto_traducido:
        raise gr.Error("La traducción falló.")

    return texto_traducido

def sintetizar_manual_action(texto_original, texto_traducido, lang, progress=gr.Progress(track_tqdm=True)):
    """Sintetiza el texto del campo de traducción si existe, si no, el original."""
    # Priorizar el texto traducido si existe y no está vacío; si no, usar el original.
    texto_a_sintetizar = texto_traducido if texto_traducido and texto_traducido.strip() else texto_original

    if not texto_a_sintetizar or not texto_a_sintetizar.strip():
        raise gr.Error("No hay texto para sintetizar. Escriba en el campo 'Texto Original' o traduzca primero.")

    progress(0, desc=f"Sintetizando texto en '{lang}'...")
    ruta_audio = sintetizar_gtts(texto_a_sintetizar, es_ruta_archivo=False, lang=lang)
    progress(1)

    if not ruta_audio:
        raise gr.Error("La síntesis de audio falló.")

    return f"Síntesis completada.", gr.Audio(value=ruta_audio, type="filepath")

def listar_archivos(directorio):
    """Lista los archivos en un directorio dado, devolviendo un mensaje si está vacío."""
    ruta_completa = os.path.join(os.getcwd(), directorio)
    if not os.path.exists(ruta_completa) or not os.listdir(ruta_completa):
        return f"No hay archivos en la carpeta '{directorio}'."
    return "\n".join(os.listdir(ruta_completa))

# --- Diseño de la Interfaz de Gradio ---
with gr.Blocks(theme=gr.themes.Soft(primary_hue="sky")) as demo:
    gr.Markdown("""
    # 🎙️ Extractor, Transcriptor y Traductor Multimedia
    Una herramienta completa para descargar, procesar y traducir contenido de video y audio.
    """)
    
    video_path_state = gr.State(None)
    audio_path_state = gr.State(None)
    transcription_path_state = gr.State(None)

    with gr.Tabs():
        with gr.TabItem("🛠️ Extractor Principal"):
            gr.Markdown("## Flujo de Trabajo Completo")
            status_text = gr.Textbox(label="Estado del Proceso", interactive=False, lines=1, max_lines=1)
            with gr.Row():
                with gr.Column(scale=1):
                    with gr.Accordion("PASO 1: 📥 Video", open=True) as download_accordion:
                        gr.Markdown("Descarga desde YouTube")
                        youtube_url = gr.Textbox(label="URL de YouTube", placeholder="https://www.youtube.com/watch?v=...")
                        with gr.Row():
                            start_time_input = gr.Textbox(label="Inicio (HH:MM:SS)", placeholder="Opcional")
                            end_time_input = gr.Textbox(label="Fin (HH:MM:SS)", placeholder="Opcional")
                        descargar_btn = gr.Button("Descargar Video", variant="secondary")
                        gr.Markdown("<div style='text-align: center;'>--- O ---</div>")
                        upload_video_btn = gr.UploadButton("📁 Cargar Video", file_types=["video"], variant="primary")

                    with gr.Accordion("PASO 2: 🎵 Audio", open=False) as audio_accordion:
                        extraer_btn = gr.Button("Extraer Audio del Video", variant="secondary")
                        gr.Markdown("<div style='text-align: center;'>--- O ---</div>")
                        upload_audio_btn = gr.UploadButton("📁 Cargar Audio", file_types=["audio"], variant="primary")

                    with gr.Accordion("PASO 3: ✍️ Transcripción", open=False) as transcribe_accordion:
                        transcribir_btn = gr.Button("Transcribir Audio", variant="secondary")
                        with gr.Row():
                            modelo_whisper_input = gr.Dropdown(["tiny", "base", "small", "medium", "large"], value="medium", label="Modelo Whisper")
                            diarizar_checkbox = gr.Checkbox(label="Diarizar", value=True)
                        gr.Markdown("<div style='text-align: center;'>--- O ---</div>")
                        upload_transcript_btn = gr.UploadButton("📁 Cargar Transcripción (.txt)", file_types=[".txt"], variant="primary")

                    with gr.Accordion("PASO 4: 🇪🇸 Traducir y Sintetizar", open=False) as translate_accordion:
                        traducir_btn = gr.Button("Traducir Audio a Español", variant="primary")

                    with gr.Accordion("PASO 5 (Opcional): 🗣️ Sintetizar Original", open=False) as synthesize_accordion:
                        sintetizar_btn = gr.Button("Sintetizar Transcripción Original", variant="secondary")

                with gr.Column(scale=2):
                    gr.Markdown("### Resultados del Proceso")
                    video_player = gr.Video(label="🎬 Video")
                    audio_original = gr.Audio(label="🎵 Audio", type="filepath")
                    transcripcion_texto = gr.Textbox(label="📝 Transcripción", lines=10, interactive=False)
                    with gr.Row():
                        audio_traducido = gr.Audio(label="🇪🇸 Audio Traducido", type="filepath")
                        transcripcion_traducida = gr.File(label="📄 Descargar Transcripción Traducida")
                    audio_sintetizado = gr.Audio(label="🗣️ Audio Sintetizado (Original)", type="filepath")

        with gr.TabItem("✍️ Sintetizador de Texto"):
            gr.Markdown("## Convertir Texto a Voz")
            with gr.Row():
                with gr.Column(scale=2):
                    manual_text_input = gr.Textbox(label="Texto Original", lines=5, placeholder="Escribe aquí...")
                    translated_text_output = gr.Textbox(label="Texto Traducido", lines=5, interactive=False)
                    with gr.Row():
                        source_lang_dropdown = gr.Dropdown(
                            [('Español', 'es'), ('Inglés', 'en'), ('Francés', 'fr'), ('Alemán', 'de'), ('Portugués', 'pt')], 
                            value='es', 
                            label="Idioma de Origen"
                        )
                        lang_dropdown = gr.Dropdown(
                            [('Español', 'es'), ('Inglés', 'en'), ('Francés', 'fr'), ('Alemán', 'de'), ('Portugués', 'pt')], 
                            value='en', 
                            label="Idioma de Destino"
                        )
                    with gr.Row():
                        traducir_manual_btn = gr.Button("Traducir Texto")
                        sintetizar_manual_btn = gr.Button("Generar Audio", variant="primary")
                with gr.Column(scale=1):
                    manual_status_text = gr.Textbox(label="Estado", interactive=False)
                    manual_audio_output = gr.Audio(label="Audio Generado", type="filepath")

        with gr.TabItem("📂 Visor de Archivos"):
            gr.Markdown("## Explorar Archivos Generados")
            with gr.Row():
                ver_videos_btn = gr.Button("🎬 Videos")
                ver_audios_btn = gr.Button("🎵 Audios")
                ver_sintetizados_btn = gr.Button("🗣️ Sintetizados")
                ver_transcripciones_btn = gr.Button("📝 Transcripciones")
            file_list_display = gr.Textbox(label="Archivos", lines=15, interactive=False)

    # --- Lógica de la Interfaz ---
    descargar_btn.click(fn=descargar_video_action, inputs=[youtube_url, start_time_input, end_time_input], outputs=[video_path_state, status_text, video_player, download_accordion, audio_accordion])
    upload_video_btn.upload(fn=process_uploaded_video, inputs=[upload_video_btn], outputs=[video_path_state, status_text, video_player, download_accordion, audio_accordion])

    extraer_btn.click(fn=extraer_audio_action, inputs=[video_path_state], outputs=[status_text, audio_original, audio_path_state, audio_accordion, transcribe_accordion])
    upload_audio_btn.upload(fn=process_uploaded_audio, inputs=[upload_audio_btn], outputs=[status_text, audio_original, audio_path_state, audio_accordion, transcribe_accordion])

    transcribir_btn.click(fn=transcribir_action, inputs=[audio_path_state, modelo_whisper_input, diarizar_checkbox], outputs=[status_text, transcripcion_texto, transcription_path_state, transcribe_accordion, translate_accordion, synthesize_accordion])
    upload_transcript_btn.upload(fn=process_uploaded_transcript, inputs=[upload_transcript_btn], outputs=[status_text, transcripcion_texto, transcription_path_state, transcribe_accordion, translate_accordion, synthesize_accordion])

    traducir_btn.click(fn=traducir_action, inputs=[audio_path_state], outputs=[status_text, audio_traducido, transcripcion_traducida])
    sintetizar_btn.click(fn=sintetizar_action, inputs=[transcription_path_state], outputs=[status_text, audio_sintetizado])

    # Lógica de traducción y síntesis manual
    traducir_manual_btn.click(
        fn=traducir_manual_action,
        inputs=[manual_text_input, source_lang_dropdown, lang_dropdown],
        outputs=[translated_text_output]
    )

    sintetizar_manual_btn.click(
        fn=sintetizar_manual_action,
        inputs=[manual_text_input, translated_text_output, lang_dropdown],
        outputs=[manual_status_text, manual_audio_output]
    )

    # Lógica del visor de archivos
    ver_videos_btn.click(fn=lambda: listar_archivos("videos"), outputs=file_list_display)
    ver_audios_btn.click(fn=lambda: listar_archivos("audios"), outputs=file_list_display)
    ver_sintetizados_btn.click(fn=lambda: listar_archivos("audio_sintetizado"), outputs=file_list_display)
    ver_transcripciones_btn.click(fn=lambda: listar_archivos("transcripciones"), outputs=file_list_display)

# Montar la aplicación de Gradio en la API de FastAPI en la ruta /gradio
app = gr.mount_gradio_app(app, demo, path="/gradio")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
