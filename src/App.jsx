import { useRef, useState } from 'react'

const API = '/api'

function ScoreRing({ score }) {
  const r = 52
  const c = 2 * Math.PI * r
  const color = score >= 70 ? '#2dd4bf' : score >= 45 ? '#f59e0b' : '#f87171'
  return (
    <div className="ring">
      <svg width="120" height="120">
        <circle cx="60" cy="60" r={r} fill="none" stroke="rgba(255,255,255,.08)" strokeWidth="9" />
        <circle
          cx="60" cy="60" r={r} fill="none"
          stroke={color} strokeWidth="9" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c - (c * score) / 100}
          style={{ transition: 'stroke-dashoffset 1s cubic-bezier(.22,1,.36,1)' }}
        />
      </svg>
      <div className="val" style={{ color }}>{score}</div>
    </div>
  )
}

export default function App() {
  const [file, setFile] = useState(null)
  const [jobText, setJobText] = useState('')
  const [jobUrl, setJobUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [letterLoading, setLetterLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [letter, setLetter] = useState('')
  const [copied, setCopied] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef(null)

  const pickFile = (f) => {
    if (f && f.name.toLowerCase().endsWith('.pdf')) { setFile(f); setError('') }
    else setError('Bitte ein PDF auswählen.')
  }

  const analyze = async () => {
    setError(''); setResult(null); setLetter('')
    if (!file) { setError('Bitte zuerst dein CV als PDF hochladen.'); return }
    if (jobText.trim().length < 100 && !jobUrl.trim()) {
      setError('Bitte das Stelleninserat einfügen (mind. 100 Zeichen) oder eine URL angeben.')
      return
    }
    setLoading(true)
    try {
      const fd = new FormData()
      fd.append('cv', file)
      fd.append('job_text', jobText)
      fd.append('job_url', jobUrl)
      const res = await fetch(`${API}/analyze`, { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Analyse fehlgeschlagen.')
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const generateLetter = async () => {
    if (!result) return
    setLetterLoading(true); setError('')
    try {
      const res = await fetch(`${API}/cover-letter`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cv_text: result.cv_text, job_text: result.job_text }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Anschreiben fehlgeschlagen.')
      setLetter(data.letter)
    } catch (e) {
      setError(e.message)
    } finally {
      setLetterLoading(false)
    }
  }

  const copyLetter = async () => {
    await navigator.clipboard.writeText(letter)
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }

  return (
    <div className="wrap">
      <header className="top">
        <a className="logo" href="https://fenlin.ch" target="_blank" rel="noopener">FC. / CV MATCHER</a>
        <h1>Passt dein CV <span className="grad">zur Stelle?</span></h1>
        <p>CV hochladen, Inserat einfügen — ehrlicher Match-Score, fehlende Keywords und ein Anschreiben-Entwurf. Dein CV wird nicht gespeichert.</p>
      </header>

      <div className="grid">
        <div className="card">
          <h2><span className="step">1</span>CV &amp; Stelleninserat</h2>

          <div
            className={`drop ${dragOver ? 'over' : ''} ${file ? 'has-file' : ''}`}
            onClick={() => inputRef.current.click()}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); pickFile(e.dataTransfer.files[0]) }}
          >
            <input ref={inputRef} type="file" accept=".pdf" onChange={(e) => pickFile(e.target.files[0])} />
            {file ? <>✓ {file.name}</> : <>📄 CV als PDF hierher ziehen oder klicken</>}
          </div>

          <label className="lbl">Stelleninserat (Text einfügen)</label>
          <textarea
            value={jobText}
            onChange={(e) => setJobText(e.target.value)}
            placeholder="Den vollständigen Text des Stelleninserats hier einfügen…"
          />

          <label className="lbl">… oder URL des Inserats (Versuch — viele Portale blockieren das)</label>
          <input
            type="url"
            value={jobUrl}
            onChange={(e) => setJobUrl(e.target.value)}
            placeholder="https://…"
          />

          <div className="btn-row">
            <button className="btn btn-primary" onClick={analyze} disabled={loading}>
              {loading ? <><span className="spinner" />Analysiere…</> : 'Match analysieren'}
            </button>
          </div>

          {error && <div className="error">{error}</div>}
        </div>

        <div className="card">
          <h2><span className="step">2</span>Ergebnis</h2>

          {!result && !loading && (
            <div className="placeholder">
              <span className="icon">🎯</span>
              Lade dein CV hoch und füge ein Inserat ein —<br />hier erscheint deine Auswertung.
            </div>
          )}
          {loading && (
            <div className="placeholder">
              <span className="icon">🤖</span>
              CV und Inserat werden verglichen…
            </div>
          )}

          {result && (
            <>
              <div className="score-row">
                <ScoreRing score={result.score} />
                <div className="score-meta">
                  <h3>{result.job_title || 'Match-Ergebnis'}</h3>
                  <p>{result.summary}</p>
                </div>
              </div>

              {result.strengths?.length > 0 && (
                <div className="res-block">
                  <h4 className="ok">Deine Stärken für diese Stelle</h4>
                  <ul>{result.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
                </div>
              )}

              {result.gaps?.length > 0 && (
                <div className="res-block">
                  <h4 className="warn">Lücken &amp; schwache Punkte</h4>
                  <ul>{result.gaps.map((g, i) => <li key={i}>{g}</li>)}</ul>
                </div>
              )}

              {result.missing_keywords?.length > 0 && (
                <div className="res-block">
                  <h4 className="warn">Fehlende Keywords im CV</h4>
                  <div className="kw">{result.missing_keywords.map((k, i) => <span key={i}>{k}</span>)}</div>
                </div>
              )}

              {result.tips?.length > 0 && (
                <div className="res-block">
                  <h4 className="tip">Konkrete Tipps</h4>
                  <ul>{result.tips.map((t, i) => <li key={i}>{t}</li>)}</ul>
                </div>
              )}

              <div className="btn-row">
                <button className="btn btn-ghost" onClick={generateLetter} disabled={letterLoading}>
                  {letterLoading ? <><span className="spinner" />Schreibe…</> : '✍️ Anschreiben-Entwurf generieren'}
                </button>
                {letter && (
                  <button className="btn btn-ghost" onClick={copyLetter}>
                    {copied ? '✓ Kopiert' : 'Kopieren'}
                  </button>
                )}
              </div>

              {letter && <div className="letter">{letter}</div>}
            </>
          )}
        </div>
      </div>

      <footer className="foot">
        🔒 Datenschutz: Dein CV wird ausschliesslich im Arbeitsspeicher verarbeitet und nirgends gespeichert —
        der Text wird nur für die Analyse an die Groq-API übermittelt. ·
        Gebaut von <a href="https://www.linkedin.com/in/fenlin-chirakkal-933952210/" target="_blank" rel="noopener">Fenlin Chirakkal</a>
      </footer>
    </div>
  )
}
