# 3GPP RAG Chatbot — UI

A React chat interface for the 3GPP spec assistant. Designed around the
project's actual value prop: distinguishing grounded, cited answers from
general-knowledge fallback, with clause-level citations and a signal-bars
indicator that shows how grounded each answer is.

## Setup

```bash
npm install
cp .env.example .env
# edit .env if your backend runs somewhere other than localhost:8000
```

## Run

Make sure the backend (`../src/main.py`) is already running on port 8000,
then:

```bash
npm run dev
```

Opens at `http://localhost:5173`.

## Features

- **Plain chat / RAG mode switch** — before you build an index, the
  assistant answers as a normal chatbot (clearly labeled). After
  `/build-index` succeeds, answers switch to grounded RAG mode with
  citations.
- **Citation pills** — every grounded answer shows `[Spec, Clause X.Y.Z]`
  references as tappable-looking pills.
- **Signal indicator** — a small animated signal-bars icon next to each
  assistant message shows grounding strength at a glance (full bars +
  pulse = fully grounded, dim single bar = general knowledge).
- **Knowledge base sidebar** — shows indexed documents and chunk count,
  with a one-click "Build index" / "Rebuild index" action.
- Responsive down to mobile (sidebar becomes a slide-out drawer below
  860px).

## Notes

The backend must have CORS enabled for `http://localhost:5173` (already
configured in `src/main.py`).
