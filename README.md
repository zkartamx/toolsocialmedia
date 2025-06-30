# 🎙️ Extractor y Transcriptor Multimedia

Este proyecto es una completa suite de herramientas, disponible como aplicación web (Gradio) y como script de línea de comandos (CLI), que automatiza un completo pipeline de procesamiento de video y audio:

1.  **Descarga desde YouTube**: Permite descargar videos completos o segmentos específicos.
2.  **Extracción de Audio**: Convierte los videos descargados a formato MP3.
3.  **Transcripción Inteligente**: Utiliza `openai-whisper` para transcribir el audio, con la opción de elegir diferentes modelos para balancear velocidad y precisión.
4.  **Diarización de Hablantes**: Identifica y etiqueta quién habla en cada momento, gracias a `pyannote.audio`.
5.  **Síntesis de Voz**: Convierte la transcripción resultante de nuevo en un archivo de audio usando `gTTS`.

![Demostración de la Aplicación](Demo.gif)

## Características

-   **Interfaz Web por Pasos**: Aplicación Gradio intuitiva que guía al usuario a través del proceso.
-   **Descarga de Fragmentos de Video Precisa**: ¿Solo necesitas una parte del video? Introduce los tiempos de inicio y fin (en formato `HH:MM:SS`). La herramienta utiliza `ffmpeg` para realizar cortes de alta precisión y guarda el archivo con un nombre único (`Fragmento1_FECHAHORA.mp4`) para una fácil identificación.
-   **Control de Precisión vs. Velocidad**: Menú para seleccionar diferentes tamaños del modelo Whisper (`tiny`, `base`, `small`, `medium`).
-   **Diarización Opcional**: Casilla para activar o desactivar la identificación de hablantes, permitiendo transcripciones más rápidas.
-   **Soporte para Múltiples Fuentes**: Procesa videos de YouTube o archivos de video/audio locales.
-   **Organización Automática**: Guarda todos los archivos generados en carpetas estructuradas (`videos/`, `audios/`, etc.).

## Requisitos

-   Python 3.9+
-   FFmpeg (debe estar instalado y accesible en el PATH del sistema).
-   Un token de acceso de Hugging Face (solo necesario para la diarización de hablantes).

## Instalación

1.  **Clona el repositorio:**
    ```bash
    git clone https://github.com/zkartamx/toolsocialmedia.git
    cd tu_repositorio
    ```

2.  **Crea y activa un entorno virtual (recomendado):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # En Windows: venv\Scripts\activate
    ```

3.  **Instala las dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configura tu token de Hugging Face (Opcional pero recomendado):**
    -   Este paso es **necesario** si planeas usar la función de **Diarización (identificar hablantes)**.
    -   En la raíz del proyecto, encontrarás un archivo llamado `config.py.template`.
    -   **Crea una copia** de este archivo y **renómbrala a `config.py`**.
    -   Abre tu nuevo `config.py` y reemplaza `"hf_TU_TOKEN_AQUI"` por tu propio token de Hugging Face (puedes obtener uno [aquí](https://huggingface.co/settings/tokens)).

    ```python
    # config.py
    HUGGING_FACE_TOKEN = "tu_token_real_de_hugging_face"
    ```

    > 🔒 **Nota de Seguridad**: El archivo `config.py` está incluido en el `.gitignore`, por lo que nunca se subirá a tu repositorio de GitHub. Esto mantiene tus credenciales seguras.

## Uso

### 🚀 Interfaz Web (Gradio)

La forma más recomendada e intuitiva de usar el proyecto. La interfaz te guía a través de un proceso de 4 pasos, dándote control total en cada etapa.

**Para iniciar:**
```bash
python app.py
```

Una vez iniciada, abre la URL proporcionada en tu navegador. El flujo de trabajo es el siguiente:

1.  **Paso 1: Descarga**
    *   Introduce la **URL de YouTube**.
    *   **(Opcional)** Especifica un **Tiempo de Inicio** y **Tiempo de Fin** (ej. `01:30`, `02:23`) para descargar solo un fragmento del video. Si los dejas en blanco, se descargará el video completo.
    *   Haz clic en `1. 📥 Descargar Video`.

2.  **Paso 2: Extracción de Audio**
    *   Una vez finalizada la descarga, el botón `2. 🎵 Extraer Audio` se habilitará.
    *   Haz clic en él para generar el archivo MP3.

3.  **Paso 3: Transcripción**
    *   Una vez extraído el audio, aparecerán los controles de transcripción.
    *   **Modelo (Velocidad vs. Precisión)**: Elige el modelo de Whisper que desees. `tiny` es el más rápido pero menos preciso; `medium` es más lento pero mucho más preciso.
    *   **Diarizar (Identificar hablantes)**: Marca o desmarca esta casilla. Si la desactivas, la transcripción será más rápida pero no identificará a los hablantes. (Requiere token de Hugging Face).
    *   Haz clic en `3. ✍️ Transcribir Audio`.

4.  **Paso 4: Síntesis de Voz**
    *   Una vez generada la transcripción, el botón `4. 🗣️ Sintetizar Audio` se habilitará.
    *   Haz clic en él para convertir el texto transcrito en un archivo de audio con gTTS.

Todos los resultados (audio extraído, transcripción y audio sintetizado) aparecerán en la pestaña **Resultados**.

### ✍️ Pestaña de Síntesis Manual

¿Necesitas convertir un texto a voz rápidamente sin pasar por todo el proceso? La pestaña **"Síntesis Manual"** te permite:

- **Introducir Texto Directamente**: Escribe o pega cualquier texto en el campo designado.
- **Síntesis Instantánea**: Con un solo clic, convierte tu texto en un archivo de audio `mp3`, listo para escuchar y descargar.

### 🐍 Línea de Comandos (CLI)

Para usuarios avanzados o para integrar en otros flujos de trabajo, el script `extractor.py` ofrece un control total desde la terminal.

**Ejemplos:**

-   **Procesar un video de YouTube (descarga, extracción y transcripción):**
    ```bash
    python extractor.py --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    ```

-   **Procesar un archivo de video local:**
    ```bash
    python extractor.py --file "/ruta/a/mi/video.mp4"
    ```

-   **Transcribir un archivo de audio local:**
    ```bash
    python extractor.py --file "/ruta/a/mi/audio.mp3"
    ```

-   **Elegir un modelo de Whisper más pequeño para una transcripción más rápida:**
    ```bash
    python extractor.py --url "URL_DE_YOUTUBE" --model-size "small"
    ```

-   **Sintetizar un archivo de transcripción existente:**
    ```bash
    python extractor.py --sintetizar "/ruta/a/mi/transcripcion.txt"
    ```

## Estructura de Carpetas

El proyecto generará las siguientes carpetas para mantener los archivos organizados:

-   `videos/`: Almacena los videos descargados de YouTube.
-   `audios/`: Guarda los archivos de audio extraídos.
-   `transcripciones/`: Contiene los archivos de texto con las transcripciones.
-   `audio_sintetizado/`: Guarda los audios generados por gTTS.

## Contribuciones

Las contribuciones son bienvenidas. Por favor, abre un *issue* o un *pull request* para discutir cualquier cambio que te gustaría hacer.
```

---

¡Disfruta de tu herramienta de extracción y transcripción de audio!