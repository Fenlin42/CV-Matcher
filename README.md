# CV Matcher 🎯

Passt dein Lebenslauf zur Stelle? CV als PDF hochladen, Stelleninserat einfügen — und du bekommst:

- **Match-Score (0–100)** mit ehrlicher Einschätzung
- **Deine Stärken** bezogen auf genau dieses Inserat
- **Lücken & fehlende Keywords**, die im CV fehlen
- **Konkrete Tipps** zur Verbesserung
- **Anschreiben-Entwurf** auf Knopfdruck (DE/EN automatisch)

**Stack:** React + Vite · FastAPI (Python) · Groq (Llama 3.3 70B) · Vercel — 0 CHF Infrastrukturkosten.

## 🔒 Datenschutz

Hochgeladene CVs werden **nicht gespeichert** — keine Datenbank, kein Datei-Upload auf einen Server-Ordner.
Das PDF wird pro Anfrage im Arbeitsspeicher verarbeitet; der extrahierte Text wird ausschliesslich
zur Analyse an die Groq-API übermittelt und danach verworfen.

## Lokal starten

Voraussetzungen: Python 3.10+, Node 18+, kostenloser [Groq-API-Key](https://console.groq.com/keys)

```bash
# 1. Key eintragen
cp .env.example .env        # dann GROQ_API_KEY in .env eintragen

# 2. Backend (Terminal 1)
pip install -r requirements.txt
uvicorn api.index:app --reload --port 8000 --env-file .env

# 3. Frontend (Terminal 2)
npm install
npm run dev                 # öffnet http://localhost:5173
```

## Auf Vercel deployen (kostenlos)

1. Projekt als Repo auf GitHub pushen
2. Auf [vercel.com](https://vercel.com): **Add New → Project** → Repo importieren
   (Framework: Vite wird automatisch erkannt, die FastAPI-Function in `api/` auch)
3. Unter **Settings → Environment Variables**: `GROQ_API_KEY` = dein Key
4. **Deploy** — fertig. Frontend und API laufen unter derselben URL.

## Projektstruktur

```
cv-matcher/
├── api/index.py       # FastAPI: /api/analyze, /api/cover-letter, /api/health
├── src/               # React-Frontend (App.jsx, index.css)
├── index.html         # Vite-Einstieg
├── vercel.json        # Rewrite: /api/* -> FastAPI-Function
├── requirements.txt   # Python-Dependencies
└── .env.example       # Vorlage für den API-Key
```

---

Gebaut von [Fenlin Chirakkal](https://www.linkedin.com/in/fenlin-chirakkal-933952210/) · BSc Business Artificial Intelligence, FHNW
