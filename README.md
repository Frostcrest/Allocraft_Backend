# Allocraft Backend

This is the **Allocraft Backend** – a FastAPI-based backend for managing portfolio positions and tickers.  
_Note: This is only the backend. If you are looking for the main Allocraft project, see the relevant directory in your repository._

## Features

- REST API for managing stocks, options, and wheel strategies
- Ticker info fetching via Twelve Data API and yfinance
- User authentication (JWT-based)
- CSV upload/download for bulk data management
- Simple web UI at `/` for manual testing

## Prerequisites

- Python 3.10+ installed ([Download Python](https://www.python.org/downloads/windows/))
- [pip](https://pip.pypa.io/en/stable/installation/) (comes with Python)

## Setup Instructions (Windows)

1. **Clone the repository** (if you haven't already):

    ```sh
    git clone <your-repo-url>
    cd Allocraft_Backend
    ```

2. **Create a virtual environment** (recommended):

    ```sh
    py -m venv venv
    venv\Scripts\activate
    ```

3. **Install dependencies**:

    ```sh
    pip install -r requirements.txt
    ```
    If `requirements.txt` is not present, use:
    ```sh
    pip install fastapi uvicorn sqlalchemy pydantic twelvedata yfinance python-multipart pydantic[email] passlib jose
    ```

4. **(Optional) Set up environment variables**:

    - If you want to use your own Twelve Data API key or set a custom secret key, create a `.env` file or set environment variables as needed.
    - Example `.env`:
      ```
      TWELVE_DATA_API_KEY=your_api_key
      SECRET_KEY=your_secret_key
      ```

5. **Initialize the database**:

    - The SQLite database (`test.db`) will be created automatically on first run in the `fastapi_project` directory.

## Running the Backend

1. **Start the FastAPI server**:

    ```sh
    cd fastapi_project
    uvicorn app.main:app --reload
    ```

    - The API and web UI will be available at: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

2. **Access the web UI**:

    - Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in your browser to use the portfolio manager.

3. **API Documentation**:

    - Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
    - Alternative docs: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

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

- **Bulk upload via CSV:**
    - Use the web UI or POST to `/stocks/upload`, `/options/upload`, or `/wheels/upload` with a `multipart/form-data` file.

## Notes

- The SQLite database file (`test.db`) will be created in the `fastapi_project` directory.
- The backend uses the [Twelve Data API](https://twelvedata.com/) and yfinance for ticker and price info.
- For any issues, check the FastAPI logs in your terminal.

---

**Allocraft Backend**  
For the main Allocraft project, see the corresponding directory in your repository.