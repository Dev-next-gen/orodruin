# Contributing to Orodruin

Thanks for wanting to help. Orodruin is an open, evolving intelligence platform and
contributions of every size are welcome — bug fixes, new data sources, new analyst
tools, translations, performance and UX work, documentation.

## Ground rules

- **Open an issue first** for anything non-trivial (a new source, a schema change, a
  big refactor) so we can agree on the approach before you write code.
- Keep pull requests focused — one concern per PR is much easier to review.
- Match the surrounding style. No new heavy dependencies without discussion.
- **Never commit secrets.** All keys live in `backend/.env` (gitignored). If you add a
  source that needs a key, add a documented, empty entry to `backend/.env.example`.
- Only **legal, public** data sources. No criminal leak forums, no scraping behind
  auth-walls, no ToS violations.

## Dev setup

See the [Self-hosting](README.md#self-hosting) section of the README. In short:

```bash
docker compose up -d db
cd backend && cp .env.example .env && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000
cd ../frontend && npm install && npm run dev
```

## Adding a data source

1. Add a proxy route under `backend/app/api/` (server-side, so keys never reach the
   browser). Return GeoJSON or a small JSON shape the frontend can map directly.
2. Register the router in `backend/app/main.py`.
3. Add the layer/toggle in `frontend/src/App.jsx` and a label in `frontend/src/i18n.js`
   (all four languages: `fr`, `en`, `ar`, `ru`).
4. If the analyst should use it, add a tool in `backend/app/api/chat.py`.
5. Add the key (empty) + a comment linking to where it's obtained to
   `backend/.env.example`.

## Translations

All UI strings live in `frontend/src/i18n.js` with dictionaries for `fr`, `en`, `ar`,
`ru`. Add your key to every language. Arabic renders right-to-left — keep that in mind.

## Commit & PR

- Write clear commit messages (present tense: "add X", "fix Y").
- Describe **what** and **why** in the PR body; screenshots help for UI changes.
- By contributing you agree your work is licensed under the project's
  **AGPL-3.0** license.

## Reporting bugs / ideas

Open a GitHub issue with steps to reproduce (for bugs) or the problem you're trying to
solve (for ideas). Live sources sometimes rate-limit or change — if a layer is empty,
check the backend logs before filing.
