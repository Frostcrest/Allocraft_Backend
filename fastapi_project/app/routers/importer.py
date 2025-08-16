from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import Any, Dict
import os
from pathlib import Path

from ..database import get_db
from ..dependencies import require_role
from ..importers.wheel_tracker import import_wheel_tracker_bytes
from ..importers.wheel_tracker import import_wheel_tracker_csv
from ..importers.stock_importer import import_stock_csv
from ..importers.option_importer import import_option_csv
from .. import models

router = APIRouter(prefix="/importer", tags=["Importer"])

"""
Importer Router

Beginner guide:
- Admin-only endpoints to import Wheel Tracker CSVs into the database.
- Use POST /importer/upload to upload a single CSV via the UI.
- Use POST /importer/scan to import all CSVs in the seed folder.

Auth:
- Requires admin role; local dev sets DISABLE_AUTH=1 so you can test freely.
"""


@router.post("/upload", dependencies=[Depends(require_role("admin"))])
async def upload_wheel_tracker_csv(file: UploadFile = File(...), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Upload a single Wheel Tracker CSV and import it.

    Input: multipart/form-data, field name 'file'
    Returns: { status: 'ok', summary: ImportSummary }
    Errors: 400 for bad CSV or parse failures
    """
    data = await file.read()
    try:
        summary = import_wheel_tracker_bytes(db, data, filename=file.filename or "upload.csv")
        return {"status": "ok", "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/scan", dependencies=[Depends(require_role("admin"))])
def scan_seed_folder(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Scan SEED_DROP_DIR or default seed_drop for wheels/stocks/options subfolders and import.

    Returns: { folder, counts: {wheels, stocks, options, total}, results: {wheels:[], stocks:[], options:[]} }
    """
    folder = os.getenv("SEED_DROP_DIR")
    if not folder:
        # default to a repo-local folder for convenience; compute without importing main to avoid circulars
        base_dir = Path(__file__).resolve().parent.parent  # app/
        folder = str((base_dir.parent / "seed_drop").resolve())
    p = Path(folder)
    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=404, detail=f"Seed folder not found: {folder}")

    results: Dict[str, list] = {"wheels": [], "stocks": [], "options": []}
    counts = {"wheels": 0, "stocks": 0, "options": 0}

    # Wheels
    wheels_dir = p / "wheels"
    if wheels_dir.exists() and wheels_dir.is_dir():
        for csv_path in sorted(wheels_dir.glob("*.csv")):
            try:
                summary = import_wheel_tracker_csv(db, str(csv_path))
                results["wheels"].append({"file": csv_path.name, "summary": summary})
                counts["wheels"] += 1
            except Exception as e:
                results["wheels"].append({"file": csv_path.name, "error": str(e)})

    # Stocks
    stocks_dir = p / "stocks"
    if stocks_dir.exists() and stocks_dir.is_dir():
        for csv_path in sorted(stocks_dir.glob("*.csv")):
            try:
                summary = import_stock_csv(db, str(csv_path))
                results["stocks"].append({"file": csv_path.name, "summary": summary})
                counts["stocks"] += 1
            except Exception as e:
                results["stocks"].append({"file": csv_path.name, "error": str(e)})

    # Options
    options_dir = p / "options"
    if options_dir.exists() and options_dir.is_dir():
        for csv_path in sorted(options_dir.glob("*.csv")):
            try:
                summary = import_option_csv(db, str(csv_path))
                results["options"].append({"file": csv_path.name, "summary": summary})
                counts["options"] += 1
            except Exception as e:
                results["options"].append({"file": csv_path.name, "error": str(e)})

    counts["total"] = counts["wheels"] + counts["stocks"] + counts["options"]
    return {"folder": folder, "counts": counts, "results": results}


@router.post("/reset", dependencies=[Depends(require_role("admin"))])
def reset_portfolio_and_reimport(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Purge portfolio data (stocks/options/wheels) and re-import from seed_drop.

    Does not delete users. Use carefully in development.
    """
    # Delete in FK-safe order
    try:
        db.query(models.LotLink).delete(synchronize_session=False)
        db.query(models.LotMetrics).delete(synchronize_session=False)
        db.query(models.WheelEvent).delete(synchronize_session=False)
        db.query(models.Lot).delete(synchronize_session=False)
        db.query(models.WheelCycle).delete(synchronize_session=False)
        db.query(models.WheelStrategy).delete(synchronize_session=False)
        db.query(models.Option).delete(synchronize_session=False)
        db.query(models.Stock).delete(synchronize_session=False)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to purge data: {e}")

    # Re-import from seed_drop
    return scan_seed_folder(db)
