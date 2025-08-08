# Allocraft Backend

This is the **Allocraft Backend** – a FastAPI-based backend for managing portfolio positions and tickers.

> **Note:** Allocraft now has a production web frontend at [https://allocraft.app](https://allocraft.app).  
> This repository is for the backend API and local development/testing.  
> If you want to contribute to the frontend, see the main Allocraft repository.

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
uvicorn app.main:app --reload
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

---

**Allocraft Backend**  
For the main Allocraft project, see the corresponding directory in your repository.