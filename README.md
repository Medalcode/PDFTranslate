# PDFTranslate

> AI-powered PDF translator that preserves the original layout — images, diagrams, and structure intact.

## Features

- 📄 English → Spanish Translation (configurable)
- 🖼️ Preserves images, font size, and layout using exact bounding boxes
- 💻 Code-aware: source code blocks are never translated
- ⚡ **Real-time Progress**: Powered by WebSockets (Phase 1: Extract, Phase 2: Translate, Phase 3: Overlay)
- 💾 **Deduplication Cache**: Persistent SQLite storage to avoid re-translating identical blocks (saves $$$ and time)
- 📖 **Dynamic Glossary**: Force specific translations via `data/glossary.json`
- 📏 **Semantic Autofit**: AI-powered text shortening if the translation doesn't fit the original layout
- 🌐 Modern dark-mode web UI with drag-and-drop & confetti success effects

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python · FastAPI · Uvicorn |
| Real-time | WebSockets (Bi-directional progress) |
| Cache | SQLite3 (Persistent deduplication) |
| PDF Read & Overlay | PyMuPDF (fitz) - v2 Architecture |
| Primary Translation | LLMs (OpenAI / Gemini / Anthropic / Groq) |
| UI | Vanilla HTML · CSS · JS · Canvas-Confetti |

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

1. **Upload**: User drops a PDF. FastAPI spawns a background task and establishes a **WebSocket** connection for real-time reporting.
2. **Phase 1: Extraction**: PyMuPDF extracts text, fonts, and bounding boxes.
3. **Phase 2: Intelligent Translation**: 
    - **Cache Lookup**: Skips blocks already translated in previous jobs.
    - **Glossary Injection**: Ensures business terms are translated as defined.
    - **LLM Batching**: Translates remaining blocks via chosen provider.
    - **Circuit Breaker**: Auto-switch to Google Translate if LLM fails/quota hits.
4. **Phase 3: Visual Overlay & Semantic Fit**:
    - If a translated paragraph is too long, the system **shrink-fits** the font down to 6pt.
    - If it *still* overflows, the **LLM semantically shortens** the text while keeping original meaning.
5. **Success**: The final PDF is saved in `data/outputs/` and the UI triggers a confetti celebration.

## License

[MIT](LICENSE)