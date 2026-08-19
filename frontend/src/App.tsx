import { FormEvent, useEffect, useState } from 'react'

type AnalysisStatus = 'processing' | 'done' | 'error'

type Analysis = {
  id: string
  status: AnalysisStatus
  accent: string | null
  confidence: number | null
  language: string | null
  reason: string | null
}

type RestTrace = {
  method: 'POST' | 'GET'
  endpoint: string
  status: number
  statusText: string
  durationMs: number
  requestId: string
  quotaRemaining: string | null
  quotaReset: string | null
  request: Record<string, unknown> | null
  response: unknown
}

const languageNames = new Intl.DisplayNames(['en'], { type: 'language' })

function readableLabel(value: string) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function resultMessage(analysis: Analysis) {
  if (analysis.reason === 'youtube_access_blocked') {
    return ['YouTube access blocked', 'YouTube refused the server request before audio could be analyzed. Try another public video later.']
  }
  if (analysis.reason === 'live_stream_skipped') {
    return ['Live stream', 'Live videos are not analyzed. Try a recorded video.']
  }
  if (analysis.reason === 'non_english') {
    const language = analysis.language
      ? languageNames.of(analysis.language) || analysis.language.toUpperCase()
      : 'another language'
    return ['Non-English speech', `${language} was detected, so accent analysis was skipped.`]
  }
  if (analysis.status === 'error') {
    return ['Analysis unsuccessful', 'We could not process this video. Check that it is public and try again.']
  }
  return [
    `${readableLabel(analysis.accent || 'Unknown')} accent`,
    'English detected · analysis complete',
  ]
}

export default function App() {
  const [url, setUrl] = useState('')
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [trace, setTrace] = useState<RestTrace | null>(null)
  const [copied, setCopied] = useState(false)

  async function inspectResponse(
    response: Response,
    method: RestTrace['method'],
    endpoint: string,
    request: RestTrace['request'],
    startedAt: number,
  ) {
    const body = await response.json().catch(() => null)
    setTrace((previous) => ({
      method,
      endpoint,
      status: response.status,
      statusText: response.statusText,
      durationMs: Math.round(performance.now() - startedAt),
      requestId: response.headers.get('X-Request-ID') || 'not provided',
      quotaRemaining: response.headers.get('X-RateLimit-Remaining') ?? previous?.quotaRemaining ?? null,
      quotaReset: response.headers.get('X-RateLimit-Reset') ?? previous?.quotaReset ?? null,
      request,
      response: body,
    }))
    if (!response.ok) {
      throw new Error(body?.detail || 'Something went wrong. Please try again.')
    }
    return body as Analysis
  }

  useEffect(() => {
    if (!analysis || analysis.status !== 'processing') return
    let stopped = false
    let attempts = 0

    const poll = async () => {
      attempts += 1
      try {
        const endpoint = `/api/analyses/${analysis.id}`
        const startedAt = performance.now()
        const response = await fetch(endpoint, {
          headers: { Accept: 'application/json' },
        })
        const next = await inspectResponse(response, 'GET', endpoint, null, startedAt)
        if (!stopped) {
          setAnalysis(next)
          setError('')
        }
      } catch (pollError) {
        if (!stopped) setError(pollError instanceof Error ? pollError.message : 'Unable to check the result.')
      }
    }

    const timer = window.setInterval(() => {
      if (attempts >= 72) {
        window.clearInterval(timer)
        setError('This analysis is taking longer than expected. Please try again later.')
        return
      }
      void poll()
    }, 2500)

    return () => {
      stopped = true
      window.clearInterval(timer)
    }
  }, [analysis?.id, analysis?.status])

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    setAnalysis(null)
    try {
      const endpoint = '/api/analyses'
      const startedAt = performance.now()
      const response = await fetch('/api/analyses', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ url }),
      })
      setAnalysis(await inspectResponse(
        response,
        'POST',
        endpoint,
        { url },
        startedAt,
      ))
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to start analysis.')
    } finally {
      setSubmitting(false)
    }
  }

  const [resultTitle, resultCopy] = analysis ? resultMessage(analysis) : ['', '']
  const isProcessing = submitting || analysis?.status === 'processing'
  const confidence = analysis?.confidence == null ? null : Math.round(analysis.confidence * 100)

  async function copyResponse() {
    if (!trace) return
    await navigator.clipboard.writeText(JSON.stringify(trace.response, null, 2))
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return (
    <div className="page-shell">
      <header className="site-header">
        <a className="brand" href="/" aria-label="Accento home">
          <span className="brand-mark">A</span>
          <span>Accento</span>
        </a>
        <span className="privacy-note">FastAPI · Celery · Redis · MongoDB · ONNX</span>
      </header>

      <main>
        <section className="hero">
          <p className="eyebrow">Production REST API · ML inference</p>
          <h1>What accent do you hear?</h1>
          <p className="subtitle">
            Paste a public YouTube link. Accento samples a few seconds of English speech
            and estimates the speaker’s accent.
          </p>
          <p className="builder-line">Engineered by <a href="https://mjalili.com">Mohammad Jalili</a> · Backend Developer</p>
        </section>

        <section className="analyzer" aria-labelledby="analyzer-title">
          <h2 id="analyzer-title" className="sr-only">Analyze a YouTube video</h2>
          <form onSubmit={submit}>
            <label htmlFor="video-url">YouTube URL</label>
            <div className="form-row">
              <input
                id="video-url"
                type="url"
                inputMode="url"
                placeholder="https://www.youtube.com/watch?v=…"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                required
                disabled={isProcessing}
                aria-describedby="url-help"
              />
              <button type="submit" disabled={isProcessing}>
                {isProcessing ? <><span className="spinner" />Analyzing…</> : 'Analyze accent'}
              </button>
            </div>
            <div className="form-meta">
              <p id="url-help">Public, non-live videos only · Global quota: 4 submissions per UTC day</p>
              <span className="quota-badge">Resets 00:00 UTC</span>
            </div>
          </form>

          {error && <div className="error-message" role="alert">{error}</div>}

          {analysis && (
            <div className={`result result-${analysis.status}`} aria-live="polite">
              <div>
                <div className="result-title">
                  <span className="result-dot" />
                  <strong>{analysis.status === 'processing' ? 'Analyzing speech' : resultTitle}</strong>
                </div>
                <p>{analysis.status === 'processing' ? 'Your request is queued. This usually takes under a minute.' : resultCopy}</p>
              </div>
              {confidence !== null && analysis.status === 'done' && (
                <div className="confidence"><strong>{confidence}%</strong><span>confidence</span></div>
              )}
            </div>
          )}
        </section>

        <section className="benefits" aria-label="How Accento works">
          <article><strong>Fast result</strong><span>Queued processing keeps the page responsive.</span></article>
          <article><strong>Minimal retention</strong><span>Temporary audio is deleted immediately.</span></article>
          <article><strong>Honest limitations</strong><span>An estimate, not a claim about identity.</span></article>
        </section>

        <section className="developer-surface" aria-labelledby="api-title">
          <div className="section-heading">
            <div>
              <p className="source-kicker">Developer surface</p>
              <h2 id="api-title">REST API, fully observable</h2>
            </div>
            <span className="api-version">JSON · v1</span>
          </div>

          <div className="endpoint-list" aria-label="Public API endpoints">
            <article><span className="method method-post">POST</span><code>/api/analyses</code><p>Validate and enqueue, with a global four-per-day quota.</p><span className="status-code">202</span></article>
            <article><span className="method method-get">GET</span><code>/api/analyses/:id</code><p>Poll the cached or persisted result.</p><span className="status-code">200</span></article>
            <article><span className="method method-get">GET</span><code>/api/health/ready</code><p>Check MongoDB and Redis readiness.</p><span className="status-code">200</span></article>
          </div>

          <div className="rest-console" aria-live="polite">
            <div className="console-bar">
              <div className="console-title"><span className="live-dot" />Live transaction inspector</div>
              {trace ? (
                <div className="trace-meta">
                  <span className={trace.status < 400 ? 'trace-ok' : 'trace-error'}>{trace.status} {trace.statusText}</span>
                  <span>{trace.durationMs} ms</span>
                  {trace.quotaRemaining !== null && <span>daily-remaining: {trace.quotaRemaining}</span>}
                  <span title={trace.requestId}>request-id: {trace.requestId.slice(0, 12)}…</span>
                </div>
              ) : <span className="console-idle">Waiting for an analysis request</span>}
            </div>

            <div className="console-grid">
              <div className="code-panel">
                <div className="code-heading">
                  <span>Request</span>
                  <span>{trace ? `${trace.method} ${trace.endpoint}` : 'POST /api/analyses'}</span>
                </div>
                <pre><code>{JSON.stringify(trace?.request ?? {
                  url: 'https://www.youtube.com/watch?v=…',
                }, null, 2)}</code></pre>
              </div>
              <div className="code-panel">
                <div className="code-heading">
                  <span>Response</span>
                  <button className="copy-button" type="button" onClick={copyResponse} disabled={!trace}>
                    {copied ? 'Copied' : 'Copy JSON'}
                  </button>
                </div>
                <pre><code>{JSON.stringify(trace?.response ?? {
                  id: 'analysis_id',
                  status: 'processing',
                  accent: null,
                  confidence: null,
                  language: null,
                  reason: null,
                }, null, 2)}</code></pre>
              </div>
            </div>
          </div>

          <div className="architecture" aria-label="Backend request architecture">
            <span><strong>01</strong> Nginx</span><i>→</i>
            <span><strong>02</strong> FastAPI</span><i>→</i>
            <span><strong>03</strong> Redis + Celery</span><i>→</i>
            <span><strong>04</strong> ONNX worker</span><i>→</i>
            <span><strong>05</strong> MongoDB</span>
          </div>
        </section>

        <aside className="source-card" aria-labelledby="source-title">
          <div>
            <p className="source-kicker">Open source</p>
            <h2 id="source-title">See how Accento works</h2>
            <p>Review the code, report an issue, or contribute on GitHub.</p>
          </div>
          <a
            className="source-link"
            href="https://github.com/MJaliliT/accento"
            target="_blank"
            rel="noreferrer"
            aria-label="View Accento source code on GitHub (opens in a new tab)"
          >
            View source <span aria-hidden="true">↗</span>
          </a>
        </aside>
      </main>

      <footer>
        <span>© {new Date().getFullYear()} Accento</span>
        <div className="footer-links">
          <a href="https://github.com/MJaliliT/accento" target="_blank" rel="noreferrer">GitHub</a>
          <a href="https://mjalili.com">mjalili.com</a>
        </div>
      </footer>
    </div>
  )
}
