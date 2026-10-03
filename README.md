# Code Analyzer & Gemini Reviewer

A **Flask** based web application that lets you paste code snippets, have them reviewed by **Google Gemini** and returns:
- Quality score
- Time & space complexity
- A concise summary and suggestions
- Optimized version of the code
- Detected issues with severity levels

## Features
- Supports multiple languages (Python, JavaScript, Java, C, C++)
- Stores analysis history per user name
- Secure handling of your Gemini API key (stored in `.env` and/or browser local storage)
- Dynamic UI with a clean dark‑mode style

## Getting Started
1. **Prerequisites**
   - Python 3.12 (already configured via `pyrefly.toml` and VS Code settings)
   - Install dependencies:
     ```bash
     pip install -r requirements.txt
     ```
2. **Environment variables**
   - Create a `.env` file in the project root:
     ```
     GEMINI_API_KEY=your‑gemini‑key
     GEMINI_MODEL=gemini-2.0-flash   # optional, defaults to flash model
     ```
3. **Run the server**
   ```bash
   python app.py
   ```
   The app will be available at `http://localhost:5000`.

## Configuration
- `pyrefly.toml` points the editor to the correct Python interpreter and adds the site‑packages directory to the search path.
- `pyrightconfig.json` provides the same information for the Pyright language server.
- The banner in `static/index.html` now **does not display a clickable link** for the Gemini API key – it only shows the text *“Get a free key at Google AI Studio”.*

## Development
- To customize the UI, edit `static/index.html` and the accompanying CSS.
- Backend logic resides in `app.py`. API routes are:
  - `POST /api/analyze` – accept code, language, username, and optional `api_key`.
  - `POST /api/key` – save a Gemini key.
  - `GET /api/key/status` – check if a key is stored.
  - `GET /api/history` – fetch previous analyses.

## License
MIT License – feel free to fork, modify and contribute.
