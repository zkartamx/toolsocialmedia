import gradio as gr
import os
from datetime import datetime
from extractor import (
    crear_carpetas_necesarias,
    descargar_video_youtube,
    extraer_audio,
    transcribir_y_diarizar,
    sintetizar_audio_gtts
)

# Nos aseguramos de que todas las carpetas necesarias existan al iniciar la app.
crear_carpetas_necesarias()

# --- Funciones de la Interfaz ---

def descargar_video_action(url, start_time, end_time, progress=gr.Progress(track_tqdm=True)):
    """Acción para descargar el video. Devuelve la ruta y actualiza la UI."""
    if not url:
        raise gr.Error("Por favor, introduce una URL de YouTube.")

    start_time = start_time.strip() if start_time else None
    end_time = end_time.strip() if end_time else None
    
    progress(0, desc="Descargando video...")
    ruta_video = descargar_video_youtube(url, start_time, end_time)
    
    if not ruta_video:
        progress(1)
        raise gr.Error("No se pudo descargar el video. Revisa la URL y los registros.")
    
    progress(1, desc="¡Descarga completada!")
    # Retorna la ruta del video para el estado, un mensaje de estado, y hace visible el siguiente botón.
    return ruta_video, f"Video descargado con éxito en: {ruta_video}", gr.update(visible=True)

def extraer_audio_action(ruta_video, progress=gr.Progress(track_tqdm=True)):
    """Acción para extraer el audio. Devuelve la ruta del audio y actualiza la UI."""
    if not ruta_video:
        raise gr.Error("No hay un video descargado desde el cual extraer audio.")

    progress(0, desc="Extrayendo audio...")
    ruta_audio = extraer_audio(ruta_video)

    if not ruta_audio:
        progress(1)
        raise gr.Error("No se pudo extraer el audio del video.")
    
    progress(1, desc="¡Audio extraído!")
    # Retorna estado, ruta para el reproductor y hace visibles los controles de transcripción.
    return f"Audio extraído con éxito en: {ruta_audio}", ruta_audio, ruta_audio, gr.update(visible=True), gr.update(visible=True), gr.update(visible=True)

def transcribir_action(ruta_audio, model_size, diarizar, progress=gr.Progress(track_tqdm=True)):
    """Acción para transcribir el audio y mostrar el resultado."""
    if not ruta_audio:
        raise gr.Error("No hay un archivo de audio para transcribir.")

    desc_progreso = f"Transcribiendo con modelo '{model_size}'"
    if diarizar:
        desc_progreso += " y diarizando"
    desc_progreso += " (puede tardar)..."

    progress(0, desc=desc_progreso)
    ruta_transcripcion = transcribir_y_diarizar(ruta_audio, diarizar=diarizar, model_size=model_size)

    if not ruta_transcripcion:
        progress(1)
        raise gr.Error("No se pudo generar la transcripción. Revisa tu token de Hugging Face si la diarización está activa.")

    with open(ruta_transcripcion, 'r', encoding='utf-8') as f:
        texto_transcrito = f.read()

    progress(1, desc="¡Transcripción completada!")
    return f"Transcripción guardada en {ruta_transcripcion}", texto_transcrito, ruta_transcripcion, gr.update(visible=True)

def sintetizar_action(ruta_transcripcion, progress=gr.Progress(track_tqdm=True)):
    """Acción para sintetizar el audio desde una transcripción."""
    if not ruta_transcripcion:
        raise gr.Error("No hay un archivo de transcripción para sintetizar.")

    progress(0, desc="Sintetizando audio con gTTS...")
    ruta_audio_sintetizado = sintetizar_audio_gtts(ruta_transcripcion)

    if not ruta_audio_sintetizado:
        progress(1)
        raise gr.Error("No se pudo sintetizar el audio.")
    
    progress(1, desc="¡Audio sintetizado!")
    return f"Audio sintetizado con éxito en: {ruta_audio_sintetizado}", ruta_audio_sintetizado

def listar_archivos(directorio):
    """Lista los archivos en un directorio dado, devolviendo un mensaje si está vacío."""
    try:
        files = [f for f in os.listdir(directorio) if not f.startswith('.')]
        if not files:
            return f"No hay archivos en la carpeta '{directorio}'."
        return "\n".join(files)
    except FileNotFoundError:
        return f"El directorio '{directorio}' no existe."
    except Exception as e:
        return f"Error al leer el directorio: {e}"

def sintetizar_manual_action(texto_manual, progress=gr.Progress(track_tqdm=True)):
    """Sintetiza texto introducido manualmente."""
    if not texto_manual or not texto_manual.strip():
        raise gr.Error("El campo de texto no puede estar vacío.")

    progress(0, desc="Preparando texto para síntesis...")
    
    # Crear un archivo de transcripción temporal
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"manual_input_{timestamp}.txt"
    ruta_temporal = os.path.join("transcripciones", nombre_archivo)

    try:
        with open(ruta_temporal, 'w', encoding='utf-8') as f:
            f.write(texto_manual)
    except Exception as e:
        raise gr.Error(f"No se pudo crear el archivo temporal: {e}")

    progress(0.5, desc="Sintetizando audio con gTTS...")
    ruta_audio_sintetizado = sintetizar_audio_gtts(ruta_temporal)

    if not ruta_audio_sintetizado:
        progress(1)
        raise gr.Error("No se pudo sintetizar el audio.")
    
    progress(1, desc="¡Audio sintetizado con éxito!")
    return f"Audio sintetizado con éxito en: {ruta_audio_sintetizado}", ruta_audio_sintetizado

# Diseño de la interfaz de Gradio
with gr.Blocks(theme=gr.themes.Soft(primary_hue="sky")) as demo:
    gr.Markdown("""
    # 🎙️ Extractor y Transcriptor Multimedia (Por Pasos)
    Realiza el proceso de extracción y transcripción paso a paso.
    """)

    # Estados internos para almacenar las rutas de los archivos entre pasos.
    video_path_state = gr.State(value=None)
    audio_path_state = gr.State(value=None)
    transcription_path_state = gr.State(value=None)

    with gr.Row():
        youtube_url = gr.Textbox(label="URL de YouTube", placeholder="https://www.youtube.com/watch?v=...", scale=4)
    
    with gr.Row():
        start_time_input = gr.Textbox(label="Tiempo de Inicio (opcional)", placeholder="Ej: 01:30")
        end_time_input = gr.Textbox(label="Tiempo de Fin (opcional)", placeholder="Ej: 02:23")
    
    with gr.Row():
        descargar_btn = gr.Button("1. 📥 Descargar Video", variant="primary")
        extraer_btn = gr.Button("2. 🎵 Extraer Audio", variant="primary", visible=False)

    with gr.Row(visible=False) as transcribir_controls:
        transcribir_btn = gr.Button("3. ✍️ Transcribir Audio", variant="primary")
        modelo_whisper_input = gr.Dropdown(
            label="Modelo (Velocidad vs. Precisión)",
            choices=["tiny", "base", "small", "medium"],
            value="medium",
            info="Modelos más pequeños son más rápidos."
        )
        diarizar_checkbox = gr.Checkbox(label="Diarizar (Identificar hablantes)", value=True, info="Requiere token Hugging Face.")

    sintetizar_btn = gr.Button("4. 🗣️ Sintetizar Audio", variant="primary", visible=False)

    status_text = gr.Textbox(label="Estado del Proceso", interactive=False)
    progress_bar = gr.Progress()

    with gr.Tab("Resultados"):
        with gr.Row():
            with gr.Column():
                gr.Markdown("### 🔊 Audios Generados")
                audio_original = gr.Audio(label="Audio Extraído del Video", type="filepath")
                audio_sintetizado = gr.Audio(label="Audio Sintetizado (gTTS)", type="filepath")
            with gr.Column():
                gr.Markdown("### 📝 Transcripción Resultante")
                transcripcion_texto = gr.Textbox(label="Transcripción con Hablantes", lines=15, interactive=False, max_lines=20)

    with gr.Tab("✍️ Síntesis Manual"):
        gr.Markdown("### Sintetizar Texto Personalizado\nEscribe o pega el texto que deseas convertir a audio y presiona el botón.")
        with gr.Row():
            with gr.Column(scale=3):
                manual_text_input = gr.Textbox(
                    label="Texto a Sintetizar", 
                    lines=10, 
                    placeholder="Escribe aquí el texto..."
                )
            with gr.Column(scale=1):
                sintetizar_manual_btn = gr.Button("🗣️ Sintetizar Texto", variant="primary")
                manual_status_text = gr.Textbox(label="Estado", interactive=False)
                manual_audio_output = gr.Audio(label="Audio Sintetizado Manualmente", type="filepath")

    with gr.Accordion("📂 Ver Archivos Generados", open=False):
        with gr.Row():
            ver_videos_btn = gr.Button("🎬 Ver Videos Descargados")
            ver_audios_btn = gr.Button("🎵 Ver Audios Extraídos")
            ver_sintetizados_btn = gr.Button("🗣️ Ver Audios Sintetizados")
        file_list_display = gr.Textbox(
            label="Archivos Encontrados", 
            interactive=False, 
            lines=8, 
            placeholder="Haz clic en un botón para ver los archivos..."
        )

    # --- Conexión de los botones a las funciones ---
    
    # 1. Botón de Descarga
    descargar_btn.click(
        fn=descargar_video_action,
        inputs=[youtube_url, start_time_input, end_time_input],
        outputs=[video_path_state, status_text, extraer_btn]
    )

    # 2. Botón de Extracción de Audio
    extraer_btn.click(
        fn=extraer_audio_action,
        inputs=video_path_state,
        outputs=[status_text, audio_original, audio_path_state, transcribir_controls]
    )

    # 3. Botón de Transcripción
    transcribir_btn.click(
        fn=transcribir_action,
        inputs=[audio_path_state, modelo_whisper_input, diarizar_checkbox],
        outputs=[status_text, transcripcion_texto, transcription_path_state, sintetizar_btn]
    )

    # 4. Botón de Síntesis
    sintetizar_btn.click(
        fn=sintetizar_action,
        inputs=transcription_path_state,
        outputs=[status_text, audio_sintetizado]
    )

    # Acciones para ver archivos
    ver_videos_btn.click(fn=lambda: listar_archivos("videos"), outputs=file_list_display, queue=False)
    ver_audios_btn.click(fn=lambda: listar_archivos("audios"), outputs=file_list_display, queue=False)
    ver_sintetizados_btn.click(fn=lambda: listar_archivos("audio_sintetizado"), outputs=file_list_display, queue=False)

    # Acción para síntesis manual
    sintetizar_manual_btn.click(
        fn=sintetizar_manual_action,
        inputs=manual_text_input,
        outputs=[manual_status_text, manual_audio_output]
    )

if __name__ == "__main__":
    demo.launch(share=True)
