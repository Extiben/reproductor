# LocalTune

Reproductor de música local de escritorio, ligero y sin Electron/Chromium. Está inspirado en la organización visual de los reproductores modernos, pero no usa logos ni assets de Spotify.

## Características MVP

- Escaneo recursivo de carpetas locales: **MP3, FLAC, OGG y OGA**.
- Metadatos mediante [Mutagen](https://mutagen.readthedocs.io/): título, artista, álbum, artista del álbum, género, pista y duración.
- Lectura de carátulas embebidas ID3/APIC, FLAC y Vorbis; se convierten a miniaturas JPEG de 320 px y se guardan en caché en disco.
- Botón **Carátulas online** para buscar automáticamente artwork y etiquetas de artista/álbum usando metadatos locales. Consulta la iTunes Search API para enriquecer la biblioteca, descarga sólo imágenes de portada y nunca modifica los archivos originales.
- Las descargas de canciones usan Internet Archive y sólo muestran elementos cuyo registro expone licencia Creative Commons o dominio público; el usuario inicia cada descarga manualmente.
- Biblioteca con vistas por álbum, artista y canción.
- Búsqueda local instantánea con un pequeño debounce y consultas SQLite.
- Si no hay coincidencias locales, búsqueda online de hasta 8 resultados legales de Internet Archive con carátula, artista, álbum y archivo descargable.
- Descarga opcional del resultado seleccionado a `LocalTune Downloads` dentro de la primera carpeta de música configurada; después se escanea automáticamente.
- Playlists creadas por el usuario, persistidas en SQLite.
- Cola de reproducción, reproducción aleatoria, repetir cola/canción, volumen y búsqueda de posición.
- Barra inferior fija con carátula, transporte y progreso.
- Interfaz en español, tema oscuro (#121212, #181818, #1DB954), sin animaciones pesadas.

## Requisitos

- Python **3.10 o posterior**.
- PySide6 6.6+.
- Mutagen 1.47+.
- Un backend de audio compatible con Qt Multimedia. En la mayoría de instalaciones de Windows/macOS viene con Qt; en Linux conviene tener PipeWire/PulseAudio y los codecs de la distribución instalados.

No se utiliza Electron, QtWebEngine, Chromium ni una interfaz web. La reproducción la hace `QMediaPlayer`/`QAudioOutput` de Qt Multimedia.

## Ejecutar desde código fuente

```bash
cd localtune
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
# .venv\\Scripts\\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

También se puede instalar como paquete editable:

```bash
python -m pip install -e .
python main.py
```

Al abrir la aplicación:

1. Pulsa **Añadir carpeta de música**.
2. Selecciona una o más carpetas raíz.
3. El escaneo se ejecutará en segundo plano; la ventana sigue respondiendo.
4. Haz doble clic en un álbum o canción para reproducirla.

La ruta de datos se crea automáticamente:

- Linux: `~/.local/share/LocalTune/`
- macOS: `~/Library/Application Support/LocalTune/`
- Windows: `%LOCALAPPDATA%\\LocalTune\\`

Contiene `library.sqlite3` y `covers/`. Para pruebas o una instalación portable se puede cambiar con `LOCALTUNE_DATA_DIR=/ruta/localtune-data`.

## Crear un ejecutable distribuible

Instala PyInstaller en el entorno virtual:

```bash
python -m pip install pyinstaller
pyinstaller --clean --noconfirm LocalTune.spec
```

El resultado estará en `dist/LocalTune/` (o en `dist/LocalTune.exe` según la configuración de PyInstaller). La primera ejecución todavía necesitará acceso a la carpeta de música elegida por el usuario.

## Estructura

```text
localtune/
├── main.py                  # punto de entrada
├── requirements.txt
├── pyproject.toml
├── LocalTune.spec           # empaquetado opcional con PyInstaller
└── localtune/
    ├── config.py            # rutas, extensiones y directorios de datos
    ├── database.py          # SQLite, biblioteca, settings y playlists
    ├── metadata.py          # Mutagen + caché de carátulas de baja resolución
    ├── scanner.py           # escaneo en QThread
    ├── online.py            # búsqueda de metadatos y descargas CC/PD
    ├── models.py            # QAbstract*Model; tabla de canciones paginada
    ├── player.py            # QMediaPlayer, cola, shuffle y repeat
    ├── widgets.py           # tema, sidebar, delegate de álbum y player bar
    └── window.py            # composición de la ventana y señales
```

## Decisiones de bajo consumo

- **Qt Widgets nativo**: no hay motor Chromium ni DOM en memoria.
- **Modelo/vista**: álbumes se pintan con un `QStyledItemDelegate`; no se crea un widget por tarjeta.
- **Carga perezosa**: carátulas se leen sólo cuando una tarjeta entra en el viewport y se mantienen en una caché LRU limitada a 128 pixmaps. Las canciones usan páginas de 250 filas y `fetchMore()` al acercarse al final.
- **Caché en disco**: Mutagen sólo procesa la carátula durante el escaneo y guarda un JPEG de 320 px, evitando mantener bytes de portadas grandes en RAM.
- **SQLite WAL + consultas**: la biblioteca no se serializa entera en cada interacción; la búsqueda filtra en la base local.
- **Escaneo en segundo plano**: la GUI no bloquea el arranque ni el hilo de eventos mientras se leen archivos.
- **Red bajo demanda**: la búsqueda de carátulas sólo se inicia al pulsar el botón; agrupa por álbum, usa coincidencia de artista/álbum y no descarga audio.
- **Sin animaciones**: no se usan fondos animados, sombras costosas ni transiciones.

En un equipo concreto, el uso real depende del backend multimedia, los codecs y el tamaño de la biblioteca. El objetivo del diseño es mantener el proceso de la aplicación por debajo de aproximadamente 150 MB en reposo con una biblioteca grande y caché limitada.

## Solución de problemas

- **No se oye audio**: verifica el dispositivo de salida del sistema y que Qt Multimedia tenga un backend instalado. En Linux prueba PipeWire/PulseAudio y los paquetes de codecs de la distribución.
- **Una carátula no aparece**: el archivo puede no contener una imagen embebida compatible; la pista seguirá reproduciéndose con el placeholder.
- **Cambios de tags**: pulsa **Escanear** de nuevo para actualizar título, artista y carátula.
- **Reinicio limpio**: cierra la app y elimina sólo `library.sqlite3` y la carpeta `covers` dentro de la ruta de datos; la música original no se modifica.
