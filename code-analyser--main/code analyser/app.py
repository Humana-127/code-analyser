import os, json, sqlite3, requests
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
ROOT_ENV_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "..", ".env"))

def reload_env():
    if os.path.exists(ROOT_ENV_PATH):
        load_dotenv(dotenv_path=ROOT_ENV_PATH, override=True)
    if os.path.exists(ENV_PATH):
        load_dotenv(dotenv_path=ENV_PATH, override=True)

reload_env()

app = Flask(__name__, static_folder="static")
DB = os.path.join(BASE_DIR, "analyses.db")

def get_api_key():
    key = os.getenv("GEMINI_API_KEY", "").strip().strip('"').strip("'")
    if key:
        return key
    for path in [ENV_PATH, ROOT_ENV_PATH]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY=") and not line.startswith("#"):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            os.environ["GEMINI_API_KEY"] = val
                            return val
    return ""


def get_model():
    reload_env()
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
    if model in ("gemini-2.0-flash", "gemini-1.5-flash"):
        model = "gemini-3.8-flash"
    return model



import hashlib

# HTTP session for connection pooling (avoids repeated SSL handshakes)
http_session = requests.Session()

# In-memory LRU cache for instant repeat analyses
analysis_cache = {}

PROMPT = """You are a senior code reviewer. Analyze the {lang} code below quickly and concisely.
Return ONLY JSON with keys:
quality_score (0-10 integer), summary (concise string, max 2 sentences),
issues (list of {{line: int or null, severity: "high"|"medium"|"low", message: string}}),
time_complexity (Big-O string), space_complexity (Big-O string),
complexity_explanation (concise string, max 2 sentences), suggestions (list of concise strings, max 4),
optimized_code (string, clean improved code).

CODE:
{code}"""

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS analyses(
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, language TEXT,
        code TEXT, result TEXT, created TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    return con

def save_api_key(key):
    key = (key or "").strip().strip('"').strip("'")
    if not key:
        return False
    os.environ["GEMINI_API_KEY"] = key
    content = f"# Google Gemini API Key\nGEMINI_API_KEY={key}\nGEMINI_MODEL=gemini-flash-latest\nPORT=5000\n"
    for path in [ENV_PATH, ROOT_ENV_PATH]:
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass
    return True

def ask_ai(lang, code, custom_key=None):
    cache_key = hashlib.sha256(f"{lang}:{code.strip()}".encode()).hexdigest()
    if cache_key in analysis_cache:
        return analysis_cache[cache_key]

    key = custom_key or get_api_key()
    if not key:
        raise ValueError("GEMINI_API_KEY is not configured.")
    
    # Priority order: ultra-fast, low-latency models first (benchmarked ~1.6s - 4s)
    candidate_models = ["gemini-3-flash-preview", "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-flash-latest", "gemini-3.8-flash"]
    configured_model = get_model()
    if configured_model and configured_model in candidate_models:
        candidate_models.remove(configured_model)
        candidate_models.insert(0, configured_model)

            
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(lang=lang, code=code)}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
            "maxOutputTokens": 2048
        }
    }
    
    last_err = None
    r = None
    for model_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        for attempt in range(2):
            try:
                r = http_session.post(url, params={"key": key}, json=body, timeout=45)
                if r.ok:
                    break
                try:
                    err_msg = r.json().get("error", {}).get("message", r.text)
                except Exception:
                    err_msg = r.text
                last_err = f"Gemini API ({r.status_code}): {err_msg}"
                if r.status_code in (503, 429) and attempt < 1:
                    import time
                    time.sleep(0.5)
                    continue
            except Exception as ex:
                last_err = str(ex)
        if r is not None and r.ok:
            break
            
    if r is None or not r.ok:
        raise RuntimeError(last_err or "Failed to connect to Gemini API.")

    candidates = r.json().get("candidates")
    if not candidates:
        raise RuntimeError("Gemini returned no candidates. Try again or check code content.")
    
    raw_text = candidates[0]["content"]["parts"][0]["text"].strip()
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw_text = "\n".join(lines).strip()
    
    parsed = json.loads(raw_text)
    # Cache result (keep cache size reasonable)
    if len(analysis_cache) > 200:
        analysis_cache.pop(next(iter(analysis_cache)))
    analysis_cache[cache_key] = parsed
    return parsed


@app.get("/")
def home():
    return send_from_directory("static", "index.html")

@app.get("/api/key/status")
def key_status():
    key = get_api_key()
    return jsonify(has_key=bool(key))

@app.post("/api/key")
def set_key():
    d = request.get_json() or {}
    key = (d.get("api_key") or "").strip()
    if not key:
        return jsonify(error="API key cannot be empty"), 400
    save_api_key(key)
    return jsonify(success=True)

@app.post("/api/analyze")
def analyze():
    d = request.get_json() or {}
    code, lang = (d.get("code") or "").strip(), d.get("language", "python")
    user = (d.get("username") or "guest").strip() or "guest"
    custom_key = (d.get("api_key") or "").strip()
    if custom_key:
        save_api_key(custom_key)
    if not code:
        return jsonify(error="Paste some code first."), 400
    active_key = custom_key or get_api_key()
    if not active_key:
        return jsonify(error="GEMINI_API_KEY is missing. Please enter your Gemini API key in the top banner or in the .env file."), 400
    try:
        result = ask_ai(lang, code, custom_key=active_key)
    except Exception as e:
        return jsonify(error=f"AI request failed: {e}"), 502
    with db() as con:
        cur = con.execute("INSERT INTO analyses(username,language,code,result) VALUES(?,?,?,?)",
                          (user, lang, code, json.dumps(result)))
    return jsonify(id=cur.lastrowid, result=result)

@app.get("/api/history")
def history():
    user = request.args.get("username", "guest")
    with db() as con:
        rows = con.execute("SELECT id,language,code,result,created FROM analyses "
                           "WHERE username=? ORDER BY id DESC LIMIT 20", (user,)).fetchall()
    return jsonify([{**dict(r), "result": json.loads(r["result"])} for r in rows])

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"Starting server on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
