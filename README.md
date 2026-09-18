# 🎯 49ja Analytics & Real-Time Scraper

A web application and automated scraper designed for analyzing historical and real-time **Bet9ja 49ja** lottery draw data. It provides interactive visual analytics, ball frequency heatmaps, custom time/date filtering, and CSV dataset exporting.

---

## 🚀 Quick Navigation

- [Features](#-features)
- [Frontend Routes](#-frontend-routes)
- [Backend API Endpoints](#-backend-api-endpoints)
- [Tech Stack](#-tech-stack)
- [Local Development Setup](#-local-development-setup)
- [Docker & Production Deployment](#-docker--production-deployment)
- [Project Structure](#-project-structure)

---

## ✨ Features

- **Automated Real-Time Scraper**: Background Selenium worker running Firefox ESR to scrape draw numbers, color breakdown, total sums, and Hi/Lo/Mid ranges continuously.
- **Interactive Analytics Dashboard**:
  - Live 5-second polling updates without full page reload.
  - KPI summary metrics (total draws, average sum, color distribution, Hi/Lo/Mid counts).
  - Ball Frequency Heatmap for numbers 1 – 49.
  - Dominant color percentage bar (Red, Blue, Green, Yellow).
- **Draw History & Custom Range Filtering**:
  - Date & Time range lower/upper bound filter with automatic timezone conversion.
  - Color match filters (3, 4, 5 or 6 same color draws).
  - Pagination controls (10, 25, 50, or 100 draws per page).
- **CSV Data Export**: One-click export of filtered draw datasets to `.csv`.

---

## 🌐 Frontend Routes

| Route | Description | Query Parameters |
| :--- | :--- | :--- |
| `/` | **Analytics Dashboard** — Displays real-time KPIs, latest draw banner, color distribution, and frequency heatmap. | `?time=0` (All Time), `0.5` (30m), `1.0` (1h), `4.0` (4h), `24.0` (24h) |
| `/history` | **Draw History** — Paginated tabular view of scraped draws with date/time range and color match filters. | `?start_datetime=`, `?end_datetime=`, `?time=`, `?occurrence=`, `?page=`, `?per_page=` |

---

## 🔌 Backend API Endpoints

### 1. Live Stats API

- **Endpoint**: `GET /api/stats`
- **Description**: Returns JSON formatted analytics data used for dashboard real-time auto-refresh.
- **Query Parameters**: `time` (float, e.g., `0`, `0.5`, `1.0`, `4.0`, `24.0`)
- **Example Response**:

  ```json
  {
    "status": "success",
    "time_filter": 1.0,
    "total_draws": 42,
    "latest_draw": {
      "id": 5781012,
      "date": "2026-09-05T20:40:00Z",
      "balls": [12, 5, 44, 29, 31, 8],
      "colour": "Red",
      "total": 129,
      "hi_lo_mid": "Mid",
      "counts": { "Red": 3, "Green": 1, "Blue": 2, "Yellow": 0 }
    },
    "color_counts": { "Red": 18, "Blue": 12, "Green": 8, "Yellow": 4 },
    "color_percentages": { "Red": 42.9, "Blue": 28.6, "Green": 19.0, "Yellow": 9.5 },
    "hi_lo_mid": { "Hi": 15, "Lo": 10, "Mid": 17 },
    "avg_total": 142.5,
    "ball_freq": { "1": 5, "2": 3, "...": "..." }
  }
  ```

### 2. CSV Data Export

- **Endpoint**: `GET /history/export`
- **Description**: Generates and downloads a `.csv` file attachment containing all records matching the selected filter criteria.
- **Query Parameters**:
  - `start_datetime` (ISO string, e.g. `2026-09-01T00:00`)
  - `end_datetime` (ISO string, e.g. `2026-09-05T23:59`)
  - `time` (hours window)
  - `occurrence` (color match count)
  - `tz_offset` (client browser timezone offset in minutes)

---

## 🛠️ Tech Stack

- **Backend**: Python 3.11+, Flask, SQLAlchemy, Gunicorn
- **Scraper**: Selenium WebDriver, Firefox ESR, GeckoDriver
- **Database**: SQLite (default) / PostgreSQL (supported via `DB_URL` env variable)
- **Frontend**: HTML5, Vanilla CSS, JavaScript (Fetch API)
- **Deployment & Proxy**: Docker, Docker Compose, Caddy 2

---

## 💻 Local Development Setup

### Prerequisites

- Python 3.11+
- Firefox browser & GeckoDriver (or run via Docker)

### Step-by-Step Setup

1. **Clone the Repository**:

   ```bash
   git clone https://github.com/BenFaruna/49ja_game.git
   cd 49ja_game
   ```

2. **Create & Activate Virtual Environment**:

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration (Optional)**:
   By default, the app uses local SQLite (`sqlite:///game_data.db`). To use a custom database (e.g., PostgreSQL):

   ```bash
   export DB_URL='postgresql://user:password@localhost:5432/game_data'
   ```

5. **Start Development Server**:

   ```bash
   python app.py
   ```

   The Flask server will launch at `http://localhost:5050` (or `http://127.0.0.1:5050`) and automatically start the background scraper thread.

---

## 🐳 Docker & Production Deployment

For production, run the application containerized with **Gunicorn** and **Caddy** reverse proxy.

### Start Containers with Docker Compose

```bash
docker compose up -d --build
```

### How Production Architecture Works

- **Gunicorn Master Hook**: Configured in `gunicorn.conf.py` using `on_starting(server)` to ensure only **one** background scraper instance runs across Gunicorn workers.
- **Caddy Reverse Proxy**: Listens on ports `80` / `443`, proxies traffic to `app:5000`, and handles gzip/zstd compression.

---

## 📁 Project Structure

```
49ja_game/
├── app.py                 # Flask application & routes (/, /history, /api/stats, /history/export)
├── scraper.py             # Selenium background scraper worker
├── driver_functions.py    # Headless Firefox driver initialization
├── gunicorn.conf.py       # Gunicorn server config & master process lifecycle hook
├── Caddyfile              # Caddy reverse proxy configuration
├── Dockerfile             # Container definition (Python + Firefox ESR + GeckoDriver)
├── docker-compose.yml     # Multi-container orchestration (App + Caddy)
├── models/
│   ├── base.py            # SQLAlchemy base & datetime model
│   ├── engine.py          # DBStorage engine (filter_draws, time_diff, save)
│   └── game_data.py       # GameData ORM schema
├── helper_functions.py    # Analytics computation & color rules
├── static/
│   └── style.css
└── templates/
    ├── base.html          # Layout template with live script & local time formatting
    ├── dashboard.html     # Analytics dashboard template
    └── history.html       # Draw history table, filter bar, & CSV export
```
