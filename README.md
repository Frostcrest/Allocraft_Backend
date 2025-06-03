# Allocraft Backend

This is the **Allocraft Backend** – a FastAPI-based backend for managing portfolio positions and tickers.  
_Note: This is only the backend. If you are looking for the main Allocraft project, see the relevant directory in your repository._

## Features

- REST API for managing stock and option positions
- Ticker info fetching via Twelve Data API
- Simple web UI at `/` for manual testing

## Prerequisites

- Python 3.10+ installed (download from [python.org](https://www.python.org/downloads/windows/))
- [pip](https://pip.pypa.io/en/stable/installation/) (comes with Python)

## Setup Instructions (Windows)

1. **Clone the repository** (if you haven't already):

    ```shcd Allocraft_Backend\Allocraft_Backend
    git clone <your-repo-url>
    cd Allocraft_Backend\Allocraft_Backend
    ```

2. **Create a virtual environment** (recommended):

    ```sh
    py -m venv venv
    venv\Scripts\activate
    ```

3. **Install dependencies**:

    ```sh
    pip install fastapi uvicorn sqlalchemy pydantic twelvedata yfinance
    ```

4. **Run the backend server**:

    ```sh
    cd .\fastapi_project\
    uvicorn app.main:app --reload
    ```

    - The API and web UI will be available at: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

5. **Access the web UI**:

    - Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in your browser to use the portfolio manager.

6. **API Documentation**:

    - Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
    - Alternative docs: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

## Example API Usage

- **Get all stock positions:**

    ```sh
    curl http://127.0.0.1:8000/positions/
    ```

- **Add a new stock position:**

    ```sh
    curl -X POST http://127.0.0.1:8000/positions/ ^
      -H "Content-Type: application/json" ^
      -d "{\"symbol\": \"AAPL\", \"quantity\": 10, \"average_price\": 150.0}"
    ```

- **Get all option positions:**

    ```sh
    curl http://127.0.0.1:8000/option_positions/
    ```

- **Fetch ticker info and add to DB:**

    ```sh
    curl -X POST http://127.0.0.1:8000/tickers/ ^
      -H "Content-Type: application/json" ^
      -d "{\"symbol\": \"AAPL\"}"
    ```

## Notes

- The SQLite database file (`test.db`) will be created in the project root.
- The backend uses the [Twelve Data API](https://twelvedata.com/) for ticker info (see API key in [`app/crud.py`](app/crud.py)).
- For any issues, check the FastAPI logs in your terminal.

---

**Allocraft Backend**  
For the main Allocraft project, see the corresponding directory in your repository.