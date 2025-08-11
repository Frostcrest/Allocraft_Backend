from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import Any, Dict
import os
from pathlib import Path

from app.database import get_db
from app.dependencies import require_role
from app.importers.wheel_tracker import import_wheel_tracker_bytes

router = APIRouter(prefix="/importer", tags=["Importer"])


@router.post("/upload", dependencies=[Depends(require_role("admin"))])
async def upload_wheel_tracker_csv(file: UploadFile = File(...), db: Session = Depends(get_db)) -> Dict[str, Any]:
    data = await file.read()
    try:
        summary = import_wheel_tracker_bytes(db, data, filename=file.filename or "upload.csv")
        return {"status": "ok", "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/scan", dependencies=[Depends(require_role("admin"))])
def scan_seed_folder(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Scan SEED_DROP_DIR or default seed_drop folder for *.csv and import.
    Returns a list of results per file.
    """
    folder = os.getenv("SEED_DROP_DIR")
    if not folder:
        from app.main import BASE_DIR  # avoid circulars
        folder = str((BASE_DIR.parent / "seed_drop").resolve())
    p = Path(folder)
    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=404, detail=f"Seed folder not found: {folder}")
    results = []
    from app.importers.wheel_tracker import import_wheel_tracker_csv
    for csv_path in sorted(p.glob("*.csv")):
        try:
            summary = import_wheel_tracker_csv(db, str(csv_path))
            results.append({"file": csv_path.name, "summary": summary})
        except Exception as e:
            results.append({"file": csv_path.name, "error": str(e)})
    return {"folder": folder, "count": len(results), "results": results}
