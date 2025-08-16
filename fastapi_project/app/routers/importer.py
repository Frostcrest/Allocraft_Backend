from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import Any, Dict
import os
from pathlib import Path

from ..database import get_db
from ..dependencies import require_role
from ..importers.wheel_tracker import import_wheel_tracker_bytes

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
    """Scan SEED_DROP_DIR or default seed_drop folder for *.csv and import.

    Returns: { folder, count, results: [{ file, summary|error }] }
    """
    folder = os.getenv("SEED_DROP_DIR")
    if not folder:
        from ..main import BASE_DIR  # avoid circulars
        folder = str((BASE_DIR.parent / "seed_drop").resolve())
    p = Path(folder)
    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=404, detail=f"Seed folder not found: {folder}")
    results = []
    from ..importers.wheel_tracker import import_wheel_tracker_csv
    for csv_path in sorted(p.glob("*.csv")):
        try:
            summary = import_wheel_tracker_csv(db, str(csv_path))
            results.append({"file": csv_path.name, "summary": summary})
        except Exception as e:
            results.append({"file": csv_path.name, "error": str(e)})
    return {"folder": folder, "count": len(results), "results": results}
