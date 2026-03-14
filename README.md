# PDFTranslate

> AI-powered PDF translator that preserves the original layout — images, diagrams, and structure intact.

## Features

- 📄 Translate PDFs from English → Spanish (configurable)
- 🖼️ Preserves images and diagrams using semantic extraction
- 💻 Code-aware: source code blocks are never translated
- 📐 HTML Reconstruction: prevents text overlapping by regenerating a clean document flow
- 🌐 Modern dark-mode web UI with drag-and-drop upload
- ⚡ Async processing with real-time progress polling

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python · FastAPI · Uvicorn |
| PDF Engine | PyMuPDF (fitz) |
| HTML Processor | BeautifulSoup4 |
| PDF Generator | xhtml2pdf (ReportLab) |
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

1. User uploads a PDF via the web UI.
2. FastAPI starts a background translation task.
3. The engine extracts semantic blocks from the PDF using PyMuPDF:
   - Images are captured as PNGs.
   - Text is classified as (code / title / paragraph).
   - A structured HTML intermediate document is created.
4. BeautifulSoup parses the HTML, and only the text content is sent for translation.
5. Code blocks are kept in `<pre>` tags to preserve formatting and skip translation.
6. `xhtml2pdf` renders the translated HTML into a brand new, clean PDF document.
7. The result is a readable, professionally formatted document without the layout bugs of the original PDF.

## License

[MIT](LICENSE)