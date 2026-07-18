# Landau Theorminimum

Phase 5 scaffold for the mobile-first Landau card game prototype. The project now has a runnable FastAPI base, SQLite bootstrap, validated editable content, a real cookie-backed gameplay loop with answer persistence and recovery after page refresh, mobile-focused swipe interactions, and an admin area for event operations.

## What Phase 5 includes

- FastAPI app with Jinja2 templates and static assets.
- SQLite configuration with `foreign_keys`, `busy_timeout`, and `WAL`.
- `data/questions.json` as the editable source for 6 validated game scenes.
- A card-only introduction: Landau's greeting, a text footnote, the story of the theoretical minimum, and name entry.
- Name entry that creates `Participant` and `GameRun` only after the introductory cards are complete.
- One shared `/play` route that server-renders:
  - the current question card
  - the current result card
  - the final screen
- `POST /play/answer`, `POST /play/next`, and `POST /api/answers/current`.
- Cookie-backed restoration of the correct state after page refresh.
- Pure game-logic helpers for verdict mapping, scoring, and final status.
- Pointer-based swipe interaction with horizontal-lock rules and submit threshold.
- Arrow-key fallback for answering question cards.
- Focus-visible states, live region status updates, and a scrollable mobile card layout for long text.
- Final summary screen and post-run `review`.
- Admin login/logout, dashboard statistics, CSV export, and confirmed reset.
- Route and integration tests, including admin coverage.

## Project structure

```text
app/                FastAPI app package
data/questions.json Editable card content
scripts/init_db.py  Database bootstrap
tests/              Route, content, and game-logic tests
```

## Setup

1. Create a virtual environment:

   ```bash
   python3 -m venv .venv
   . .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -e .[dev]
   ```

3. Create the environment file:

   ```bash
   cp .env.example .env
   ```

4. Initialize the database:

   ```bash
   python scripts/init_db.py
   ```

## Run the app

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Then open:

- `http://127.0.0.1:8000`
- `http://127.0.0.1:8000/admin/login`

## Run tests

```bash
pytest
```

## Deploy publicly and create a QR code

The repository includes a `render.yaml` Blueprint for deploying the game to Render.
Push the repository to GitHub, create a new Blueprint on Render, and select the
repository. Render will use the Blueprint to create a free web service, HTTPS URL,
and environment variables for the app.

The free service uses ephemeral SQLite storage. Game and admin data may be lost
when the service sleeps, restarts, or redeploys. It can also take about a minute
to wake up after inactivity, so open the game once shortly before the event.

During the first Blueprint setup, Render will ask for `LANDAU_ADMIN_PASSWORD`.
Choose a strong password. `LANDAU_SECRET_KEY` is generated automatically.

After deployment, install the QR helper and generate a PNG from the public URL:

```bash
pip install -e .[dev]
python scripts/make_qr.py https://your-game.onrender.com
```

Print `landau-game-qr.png` or display it on a screen. Test the QR code with a
phone using mobile data before the event.

## Manual UI checklist

Use [MANUAL_TEST_CHECKLIST.md](/Users/ilyapetrov/Documents/Reigns like game project/MANUAL_TEST_CHECKLIST.md) for the phone and desktop smoke pass.

## Environment variables

The main variables are defined in `.env.example`:

- `LANDAU_DATABASE_URL`
- `LANDAU_SECRET_KEY`
- `LANDAU_ADMIN_PASSWORD`
- `LANDAU_HOST`
- `LANDAU_PORT`

## Local network access from a phone

Run the server on all interfaces when you want to open it from another device:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Find the laptop IP with one of these commands:

```bash
ipconfig getifaddr en0
ipconfig getifaddr en1
```

Then open `http://<YOUR_LOCAL_IP>:8000` on the phone.

Notes:

- `127.0.0.1` works only on the same machine where the server is running.
- Some guest Wi-Fi networks enable client isolation and block device-to-device traffic.
- If the phone cannot connect, verify that both devices are on the same subnet and that macOS firewall rules allow incoming local connections.

## Current limitations

- The six question cards and introductory copy can be edited in `data/questions.json` and `app/cards.py` respectively.
- The swipe gesture, keyboard fallback, and accessibility baseline are implemented, but they still need broader real-device testing and tuning.
- The admin area is intentionally simple and optimized for one local event rather than a multi-user back office.
