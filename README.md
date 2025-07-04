# 🎙️ Extractor, Transcriptor y Traductor Multimedia

Este proyecto es una completa suite de herramientas, disponible como aplicación web (Gradio) y API REST, que automatiza un completo pipeline de procesamiento de video y audio:

1.  **Descarga desde YouTube**: Permite descargar videos completos o fragmentos específicos de forma optimizada.
2.  **Extracción de Audio**: Convierte los videos descargados a formato MP3.
3.  **Transcripción Inteligente**: Utiliza `openai-whisper` para transcribir el audio, con la opción de elegir diferentes modelos para balancear velocidad y precisión.
4.  **Diarización de Hablantes**: Identifica y etiqueta quién habla en cada momento, gracias a `pyannote.audio`.
5.  **Traducción y Síntesis de Voz**: Convierte texto a voz con `gTTS`, con la capacidad de traducir entre diferentes idiomas antes de sintetizar.

![Demostración de la Aplicación](Demo.gif)

## Características Clave

-   **Interfaz Web Intuitiva**: Aplicación Gradio que guía al usuario a través de todo el proceso.
-   **Descarga de Fragmentos Optimizada**: ¿Solo necesitas una parte del video? Introduce los tiempos de inicio y fin (`HH:MM:SS`). La descarga está optimizada para ser rápida, evitando la re-codificación innecesaria. Si dejas los campos en blanco, se descarga el video completo.
-   **Sintetizador de Texto con Traducción**: Una pestaña dedicada para convertir texto a voz. Permite seleccionar un idioma de origen y destino, realizar la traducción con un clic y luego generar el audio en el idioma deseado.
-   **API REST para Síntesis**: Expone la funcionalidad de traducción y síntesis a través de un endpoint de API (`/api/sintetizar/`), permitiendo la integración con otros sistemas y flujos de trabajo automatizados.
-   **Control de Precisión vs. Velocidad**: Menú para seleccionar diferentes tamaños del modelo Whisper (`tiny`, `base`, `small`, `medium`).
-   **Diarización Opcional**: Activa o desactiva la identificación de hablantes para acelerar la transcripción.
-   **Soporte para Múltiples Fuentes**: Procesa videos de YouTube o archivos de video/audio locales.
-   **Organización Automática**: Guarda todos los archivos generados en carpetas estructuradas (`videos/`, `audios/`, `test_outputs/`, etc.).

## Requisitos

-   Python 3.9+
-   FFmpeg (debe estar instalado y accesible en el PATH del sistema).
-   Un token de acceso de Hugging Face (solo necesario para la diarización de hablantes).

## Instalación

1.  **Clona el repositorio:**
    ```bash
    git clone https://github.com/zkartamx/toolsocialmedia.git
    cd toolsocialmedia
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
    -   Crea una copia del archivo `config.py.template` y renómbrala a `config.py`.
    -   Abre tu nuevo `config.py` y reemplaza el valor de `HUGGING_FACE_TOKEN` por tu propio token.

## Uso

### 🚀 Interfaz Web (Gradio)

La forma más sencilla de usar el proyecto.

**Para iniciar:**
```bash
python app.py
```
Una vez iniciada, abre la URL proporcionada en tu navegador.

#### Pestaña: Extractor Principal

El flujo de trabajo principal para procesar videos.

1.  **Paso 1: Descarga**
    *   Introduce la **URL de YouTube**.
    *   **(Opcional)** Para descargar un fragmento, especifica **ambos**, el **Tiempo de Inicio** y **Tiempo de Fin** (formato `HH:MM:SS`). Si los dejas en blanco, se descargará el video completo.
    *   Haz clic en `1. 📥 Descargar Video`.

2.  **Paso 2: Extracción de Audio**
    *   Una vez descargado el video, haz clic en `2. 🎵 Extraer Audio` para generar el archivo MP3.

3.  **Paso 3: Transcripción**
    *   **Modelo**: Elige el modelo de Whisper (`tiny` es más rápido, `medium` es más preciso).
    *   **Diarizar**: Marca esta casilla para identificar hablantes (requiere token de Hugging Face).
    *   Haz clic en `3. ✍️ Transcribir Audio`.

4.  **Paso 4: Síntesis de Voz**
    *   Haz clic en `4. 🗣️ Sintetizar Audio` para convertir el texto transcrito en un archivo de audio.

#### Pestaña: Sintetizador de Texto

Una herramienta flexible para traducir y sintetizar cualquier texto.

1.  **Introduce el Texto Original**: Escribe o pega el texto que deseas procesar.
2.  **Selecciona Idiomas**: Elige el **Idioma de Origen** y el **Idioma de Destino** en los menús desplegables.
3.  **Traduce (Opcional)**: Si los idiomas son diferentes, haz clic en `Traducir Texto`. El resultado aparecerá en el campo "Texto Traducido".
4.  **Genera Audio**: Haz clic en `Generar Audio`. El sistema sintetizará el texto traducido si existe; de lo contrario, usará el texto original.

### 🤖 API REST de Síntesis

Para uso programático, puedes llamar directamente a la API de síntesis.

**Endpoint:** `POST /api/sintetizar/`

**Cuerpo de la Petición (JSON):**
```json
{
  "texto": "Este es un texto de prueba.",
  "idioma_origen": "es",
  "idioma_destino": "en"
}
```
La API devuelve directamente el archivo de audio MP3.

**Ejemplo con `curl`:**
```bash
curl -X POST "http://127.0.0.1:7860/api/sintetizar/" \
-H "Content-Type: application/json" \
-d '{"texto": "Hola mundo", "idioma_origen": "es", "idioma_destino": "en"}' \
-o "hola_mundo_en.mp3"
```

**Documentación Interactiva:**
Para explorar la API y realizar pruebas desde el navegador, visita: [http://127.0.0.1:7860/docs](http://127.0.0.1:7860/docs)

### 🐍 Línea de Comandos (CLI)

Para usuarios avanzados, el script `extractor.py` ofrece control desde la terminal.

-   **Procesar un video de YouTube:**
    ```bash
    python extractor.py --url "URL_DE_YOUTUBE"
    ```
-   **Elegir un modelo más pequeño:**
    ```bash
    python extractor.py --url "URL_DE_YOUTUBE" --model-size "small"
    ```

## Estructura de Carpetas

El proyecto generará las siguientes carpetas para mantener los archivos organizados:

-   `videos/`: Almacena los videos descargados.
-   `audios/`: Guarda los archivos de audio extraídos.
-   `transcripciones/`: Contiene los archivos de texto con las transcripciones.
-   `audio_sintetizado/`: Guarda los audios generados por gTTS.
-   `test_outputs/`: Almacena los archivos generados durante las pruebas (ej. desde la API).

## Contribuciones

Las contribuciones son bienvenidas. Por favor, abre un *issue* o un *pull request* para discutir cualquier cambio que te gustaría hacer.