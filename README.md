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
| PDF Read & Overlay | PyMuPDF (fitz) - v2 Architecture |
| Primary Translation | LLMs via OpenAI / Google Generative AI SDK |
| Translator Fallback | Google Translate (deep-translator) with Circuit Breaker |
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
│   ├── config.py          # Settings & directories (data/ uploads/outputs)
│   ├── translator.py      # Core PDF translation engine
│   └── classifiers.py     # Code / title / text detection logic
├── data/                  # Dynamic data (ignored in git)
│   ├── uploads/           # Temporary input PDFs
│   └── outputs/           # Translated PDF outputs
├── static/                # Web Frontend
│   ├── index.html         # User Interface
│   ├── css/style.css      # Premium dark-mode styles
│   └── js/app.js          # Async logic
├── tests/                 # Automated QA tests
│   └── test_basic.py      # Basic sanity checks
├── agents.md              # IA: Roles y Agentes consolidados
├── skills.md              # IA: Super-Skills de procesamiento
├── .env.example
├── requirements.txt
└── README.md
```

## Configuration

Edit `.env`:

```env
SOURCE_LANG=en   # Input language
TARGET_LANG=es   # Output language

# LLM Configuration (Optional, falls back to Google Translate if empty/fails)
# Example for Groq
LLM_PROVIDER=openai
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
```

Any language code supported by Google Translate/LLM works (e.g. `fr`, `de`, `pt`).

## How It Works (v2 Architecture)

1. User uploads a PDF via the web UI.
2. FastAPI starts a background translation task.
3. **Pass 1: Extraction**. **PyMuPDF** reads each page, extracting text blocks, fonts, and exact bounding boxes.
    - Text is classified: `code` (never translated), `title`, or `body`.
4. **Pass 2: Translation**.
    - The text is grouped into batches and sent to the configured **LLM (OpenAI/Gemini/Groq)**.
    - **Circuit Breaker:** If the LLM hits persistent rate limits or quotas (e.g., HTTP 429), a circuit breaker triggers. The system instantly aborts the LLM and falls back to **Google Translate** to finish the document. This prevents the pipeline from hanging for hours.
5. **Pass 3: Overlay**. The translated text is carefully re-inserted onto the exact *original* coordinates on the document, automatically downscaling the font if the translation is longer than the original text. The original text underneath is redacted.
6. The exact output PDF is saved and made available for download, with 0% layout deformation.

## License

[MIT](LICENSE)