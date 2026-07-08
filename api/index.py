"""CV-Matcher API — FastAPI backend (Vercel Serverless-ready).

Endpoints:
  GET  /api/health        — Statuscheck
  POST /api/analyze       — CV-PDF + Stelleninserat -> Match-Analyse (JSON)
  POST /api/cover-letter  — CV-Text + Inserat -> Anschreiben-Entwurf
"""

import io
import json
import os
import re

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pypdf import PdfReader

app = FastAPI(title="CV Matcher API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"
MAX_CHARS = 24000  # Schutz gegen zu lange Prompts


# ---------------------------------------------------------------- helpers

def groq_chat(messages: list, json_mode: bool = True, temperature: float = 0.3) -> str:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(500, "GROQ_API_KEY ist nicht gesetzt (siehe .env.example).")
    payload = {"model": MODEL, "messages": messages, "temperature": temperature}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        r = httpx.post(
            GROQ_URL,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Groq nicht erreichbar: {exc}") from exc
    if r.status_code != 200:
        raise HTTPException(502, f"LLM-Fehler ({r.status_code}): {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


def extract_pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:
        raise HTTPException(400, f"PDF konnte nicht gelesen werden: {exc}") from exc
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) < 100:
        raise HTTPException(
            400,
            "Aus dem PDF liess sich kaum Text extrahieren. "
            "Ist es ein gescanntes Bild? Bitte ein text-basiertes PDF verwenden.",
        )
    return text[:MAX_CHARS]


def fetch_job_url(url: str) -> str:
    if not re.match(r"^https?://", url):
        raise HTTPException(400, "Ungültige URL (muss mit http(s):// beginnen).")
    try:
        r = httpx.get(
            url,
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CV-Matcher/1.0)"},
        )
        r.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            422,
            "Die URL konnte nicht geladen werden (viele Jobportale blockieren das). "
            "Bitte den Text des Inserats direkt einfügen.",
        ) from exc
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n")).strip()
    if len(text) < 200:
        raise HTTPException(
            422,
            "Auf der Seite wurde kaum Text gefunden (vermutlich JavaScript-Rendering). "
            "Bitte den Text des Inserats direkt einfügen.",
        )
    return text[:MAX_CHARS]


def parse_llm_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        raise HTTPException(502, "LLM lieferte kein gültiges JSON — bitte erneut versuchen.")


# ---------------------------------------------------------------- prompts

ANALYZE_SYSTEM = """Du bist ein erfahrener Schweizer HR-Experte und Recruiting-Coach.
Du vergleichst einen Lebenslauf (CV) mit einem Stelleninserat und antwortest NUR mit gültigem JSON.

Schema:
{
  "score": <int 0-100, realistischer Match-Score>,
  "language": "<de|en — Sprache des Inserats>",
  "job_title": "<Stellentitel aus dem Inserat>",
  "summary": "<2-3 Sätze: ehrliche Gesamteinschätzung des Matches>",
  "strengths": ["<konkrete Stärke des CV bezogen auf DIESES Inserat>", ...],  // 3-5 Einträge
  "gaps": ["<fehlende oder schwach belegte Anforderung>", ...],  // 2-5 Einträge
  "missing_keywords": ["<Keyword/Skill aus dem Inserat, das im CV fehlt>", ...],  // max 8
  "tips": ["<konkreter, umsetzbarer Tipp zur Verbesserung von CV oder Bewerbung>", ...]  // 3-5 Einträge
}

Regeln:
- Sei ehrlich und differenziert, kein Schönreden. Score 90+ nur bei nahezu perfektem Match.
- Antworte in der Sprache des Inserats (Feld "language").
- Bei Deutsch: Schweizer Rechtschreibung, KEIN ß (immer ss).
- Beziehe dich auf konkrete Inhalte aus CV und Inserat, keine Allgemeinplätze."""

COVER_LETTER_SYSTEM = """Du bist ein erfahrener Schweizer Bewerbungscoach.
Schreibe einen Entwurf für ein Bewerbungsschreiben (Motivationsschreiben) auf Basis von CV und Stelleninserat.

Regeln:
- Sprache = Sprache des Inserats. Bei Deutsch: Schweizer Rechtschreibung, KEIN ß (immer ss).
- Länge: 200-280 Wörter, 3-4 Absätze, keine Floskeln wie "hiermit bewerbe ich mich".
- Konkret: Beziehe dich auf 2-3 echte Punkte aus dem CV, die zum Inserat passen.
- Selbstbewusst aber ehrlich — nichts erfinden, was nicht im CV steht.
- Beginne direkt mit der Anrede ("Sehr geehrte..." / "Dear..."), ende mit Grussformel.
- Antworte NUR mit dem Brieftext, ohne Kommentare davor oder danach."""


# ---------------------------------------------------------------- routes

@app.get("/api/health")
def health():
    return {"status": "ok", "model": MODEL, "key_set": bool(os.environ.get("GROQ_API_KEY"))}


@app.post("/api/analyze")
async def analyze(
    cv: UploadFile = File(...),
    job_text: str = Form(""),
    job_url: str = Form(""),
):
    if cv.content_type not in ("application/pdf", "application/x-pdf") and not (
        cv.filename or ""
    ).lower().endswith(".pdf"):
        raise HTTPException(400, "Bitte ein PDF hochladen.")
    data = await cv.read()
    if len(data) > 4 * 1024 * 1024:
        raise HTTPException(400, "PDF ist grösser als 4 MB.")
    cv_text = extract_pdf_text(data)

    job = job_text.strip()
    if not job and job_url.strip():
        job = fetch_job_url(job_url.strip())
    if len(job) < 100:
        raise HTTPException(400, "Bitte das Stelleninserat einfügen (mind. 100 Zeichen) oder eine URL angeben.")
    job = job[:MAX_CHARS]

    raw = groq_chat(
        [
            {"role": "system", "content": ANALYZE_SYSTEM},
            {"role": "user", "content": f"=== LEBENSLAUF ===\n{cv_text}\n\n=== STELLENINSERAT ===\n{job}"},
        ]
    )
    result = parse_llm_json(raw)
    result["score"] = max(0, min(100, int(result.get("score", 0))))
    # CV- und Job-Text zurückgeben, damit das Frontend sie für das Anschreiben
    # wiederverwenden kann (kein zweiter Upload nötig).
    result["cv_text"] = cv_text
    result["job_text"] = job
    return result


class CoverLetterRequest(BaseModel):
    cv_text: str
    job_text: str
    tone: str = "professionell"


@app.post("/api/cover-letter")
def cover_letter(req: CoverLetterRequest):
    if len(req.cv_text) < 100 or len(req.job_text) < 100:
        raise HTTPException(400, "CV-Text und Inserat werden benötigt — bitte zuerst analysieren.")
    letter = groq_chat(
        [
            {"role": "system", "content": COVER_LETTER_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Gewünschter Ton: {req.tone}\n\n"
                    f"=== LEBENSLAUF ===\n{req.cv_text[:MAX_CHARS]}\n\n"
                    f"=== STELLENINSERAT ===\n{req.job_text[:MAX_CHARS]}"
                ),
            },
        ],
        json_mode=False,
        temperature=0.5,
    )
    return {"letter": letter.strip()}
