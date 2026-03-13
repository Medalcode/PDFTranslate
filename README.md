# PDFTranslate

> AI-powered PDF translator that preserves the original layout — images, diagrams, and structure intact.

## Features

- 📄 Translate PDFs from English → Spanish (configurable)
- 🖼️ Preserves images and diagrams in their original positions
- 💻 Code-aware: source code blocks are never translated
- 📐 Block-by-block text placement maintains original layout
- 🌐 Modern dark-mode web UI with drag-and-drop upload
- ⚡ Async processing with real-time progress polling

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python · FastAPI · Uvicorn |
| PDF Engine | PyMuPDF (fitz) |
| Translation | deep-translator (Google Translate) |
| Frontend | Vanilla HTML · CSS · JavaScript |

## Quick Start

```bash
# 1. Clone and enter the project
git clone https://github.com/Medalcode/PDFTranslate.git
cd PDFTranslate

# 2. Create a virtual environment
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure (optional)
cp .env.example .env
# Edit .env to change source/target language

# 5. Run the app
uvicorn app.main:app --reload
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Web UI |
| `POST` | `/translate` | Upload PDF, start translation |
| `GET` | `/status/{job_id}` | Poll translation status |
| `GET` | `/download/{job_id}` | Download translated PDF |

## Project Structure

```text
PDFTranslate/
├── app/
│   ├── main.py            # FastAPI routes
│   ├── config.py          # Settings & directories
│   ├── translator.py      # Core PDF translation engine
│   └── text_classifier.py # Code / title / text detection
├── static/
│   ├── index.html         # Web UI
│   ├── css/style.css      # Premium dark-mode styles
│   └── js/app.js          # Upload / polling / download logic
├── uploads/               # Temporary input PDFs
├── outputs/               # Translated PDF outputs
├── agents.md              # Documentación y roles de IA
├── skills.md              # Documentación de Super-Skills de IA
├── .env.example
├── requirements.txt
└── README.md
```

## Configuration

Edit `.env`:

```env
SOURCE_LANG=en   # Input language
TARGET_LANG=es   # Output language
```

Any language code supported by Google Translate works (e.g. `fr`, `de`, `pt`).

## How It Works

1. User uploads a PDF via the web UI
2. FastAPI saves the file and starts a background translation task
3. PyMuPDF opens the PDF and iterates over each page:
   - Images are extracted and re-inserted at their original coordinates
   - Text blocks are classified (code / title / paragraph)
   - Non-code text is translated with Google Translate
   - Translated text is placed back at the same position
4. The translated PDF is saved and made available for download
5. The frontend polls `/status/{job_id}` every 2 seconds until done

## License

[MIT](LICENSE)