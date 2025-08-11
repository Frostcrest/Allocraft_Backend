# Allocraft Backend

This is the **Allocraft Backend** – a FastAPI-based backend for managing portfolio positions and tickers.

> **Note:** Allocraft now has a production web frontend at [https://allocraft.app](https://allocraft.app).  
> This repository is for the backend API and local development/testing.  
> If you want to contribute to the frontend, see the main Allocraft repository.

---

## Quick Start (Windows)

Fastest way to run everything locally (backend + frontend):

1) From the repo root, double-click `start-dev.bat` (or run it in a terminal).
2) Two terminals open automatically:
  - Backend: FastAPI on http://127.0.0.1:8000
  - Frontend: Vite on http://localhost:5173
3) Local auth is disabled (DISABLE_AUTH=1) so you can click around freely.
4) Drop CSVs into `Allocraft_Backend/fastapi_project/seed_drop` to auto-import on startup.

Prefer manual steps? Follow the guide below.

---

## Features

- REST API for managing stocks, options, and wheel strategies
- Real-time price fetching via Twelve Data and Yahoo Finance APIs
- CSV import/export for bulk management
- User authentication and role-based access (JWT)
- Simple web UI for local testing at `/`
- Production frontend at [https://allocraft.app](https://allocraft.app)

---

## Getting Started (Local Development)

These instructions are for running the backend locally on **Windows**.  
If you are new to Python or web development, follow each step carefully.

### 1. Prerequisites

- **Python 3.10+**  
  Download from [python.org](https://www.python.org/downloads/windows/).
- **pip** (Python package manager)  
  Comes with Python by default.

### 2. Clone the Repository

Open **Command Prompt** and run:

```sh
git clone <your-repo-url>
cd Allocraft_Backend\Allocraft_Backend
```

### 3. Create a Virtual Environment (Recommended)

```sh
py -m venv venv
venv\Scripts\activate
```

### 4. Configure environment (optional, recommended)

Copy `.env.template` to `.env` and set values. For local dev, defaults are fine:

```
FRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
SECRET_KEY=change-me-in-dev
ACCESS_TOKEN_EXPIRE_MINUTES=60
TWELVE_DATA_API_KEY=
```

### 5. Install Dependencies

Install required Python packages (includes extras used by the app):

```powershell
pip install -r requirements.txt
```

### 6. Run the Backend Server

```sh
cd .\fastapi_project\
python -m uvicorn app.main:app --reload
```

- The API and web UI will be available at: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

### 7. Access the Web UI

- Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in your browser to use the portfolio manager.

### 8. API Documentation

- Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Alternative docs: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## Example API Usage

- **Get all stock positions:**

    ```sh
    curl http://127.0.0.1:8000/stocks/
    ```

- **Add a new stock position:**

    ```sh
    curl -X POST http://127.0.0.1:8000/stocks/ ^
      -H "Content-Type: application/json" ^
      -d "{\"ticker\": \"AAPL\", \"shares\": 10, \"cost_basis\": 150.0, \"status\": \"Open\"}"
    ```

- **Get all option positions:**

    ```sh
    curl http://127.0.0.1:8000/options/
    ```

- **Fetch ticker info and add to DB:**

    ```sh
    curl -X POST http://127.0.0.1:8000/tickers/ ^
      -H "Content-Type: application/json" ^
      -d "{\"symbol\": \"AAPL\"}"
    ```

---

## Notes

- The SQLite database file (`test.db`) will be created in the `fastapi_project` directory.
- The backend uses the [Twelve Data API](https://twelvedata.com/) and yfinance for ticker and price info.
- For any issues, check the FastAPI logs in your terminal.

### Seed-drop CSV imports (optional)

To quickly seed Wheels from your Wheel Tracker CSV exports without manual entry:

- Place your CSV files (e.g., `GOOG.csv`, `BBAI.csv`, `HIMS.csv`) in a folder.
- Add `SEED_DROP_DIR` to your `.env`, pointing to that folder path.
  - Windows example: `SEED_DROP_DIR=C:\\Users\\you\\Downloads\\allocraft_seed`
  - macOS/Linux: `SEED_DROP_DIR=/Users/you/allocraft_seed`
- Start the API or run the seeder:
  - API startup automatically imports all `*.csv` from `SEED_DROP_DIR` (idempotent per file/cycle). If not set, it falls back to `fastapi_project/seed_drop`.
  - Or run once: `python -m app.seed_data`

Tip: When using `start-dev.bat`, `DISABLE_AUTH=1` is set for local convenience.

Notes:
- The importer tolerates spreadsheet formulas and currency symbols.
- It creates a WheelCycle per file (cycle_key defaults to the filename) and then rebuilds lots.
- Re-running with the same files won’t duplicate events when the cycle already has events.

---

**Allocraft Backend**  
For the main Allocraft project, see the corresponding directory in your repository.