from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import Any, Dict
import os
from pathlib import Path

from ..database import get_db
from ..dependencies import require_role

from ..services.importer_service import ImporterService

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
        summary = ImporterService.upload_wheel_tracker_csv(data, db, filename=file.filename or "upload.csv")
        return {"status": "ok", "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/scan", dependencies=[Depends(require_role("admin"))])
def scan_seed_folder(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Scan SEED_DROP_DIR or default seed_drop for wheels/stocks/options subfolders and import.

    Returns: { folder, counts: {wheels, stocks, options, total}, results: {wheels:[], stocks:[], options:[]} }
    """
    try:
        return ImporterService.scan_seed_folder(db)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset", dependencies=[Depends(require_role("admin"))])
def reset_portfolio_and_reimport(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Purge portfolio data (stocks/options/wheels) and re-import from seed_drop.

    Does not delete users. Use carefully in development.
    """
    try:
        return ImporterService.reset_portfolio_and_reimport(db)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
