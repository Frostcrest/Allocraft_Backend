from sqlalchemy.orm import Session
from typing import Any, Dict
import os
from pathlib import Path
from ..importers.wheel_tracker import import_wheel_tracker_bytes, import_wheel_tracker_csv
from ..importers.stock_importer import import_stock_csv
from ..importers.option_importer import import_option_csv
from .. import models

class ImporterService:
    @staticmethod
    def upload_wheel_tracker_csv(file_bytes: bytes, db: Session, filename: str = "upload.csv") -> Dict[str, Any]:
        return import_wheel_tracker_bytes(db, file_bytes, filename=filename)

    @staticmethod
    def scan_seed_folder(db: Session) -> Dict[str, Any]:
        folder = os.getenv("SEED_DROP_DIR")
        if not folder:
            base_dir = Path(__file__).resolve().parent.parent
            folder = str((base_dir.parent / "seed_drop").resolve())
        p = Path(folder)
        if not p.exists() or not p.is_dir():
            raise FileNotFoundError(f"Seed folder not found: {folder}")
        results: Dict[str, list] = {"wheels": [], "stocks": [], "options": []}
        counts = {"wheels": 0, "stocks": 0, "options": 0}
        wheels_dir = p / "wheels"
        if wheels_dir.exists() and wheels_dir.is_dir():
            for csv_path in sorted(wheels_dir.glob("*.csv")):
                try:
                    summary = import_wheel_tracker_csv(db, str(csv_path))
                    results["wheels"].append({"file": csv_path.name, "summary": summary})
                    counts["wheels"] += 1
                except Exception as e:
                    results["wheels"].append({"file": csv_path.name, "error": str(e)})
        stocks_dir = p / "stocks"
        if stocks_dir.exists() and stocks_dir.is_dir():
            for csv_path in sorted(stocks_dir.glob("*.csv")):
                try:
                    summary = import_stock_csv(db, str(csv_path))
                    results["stocks"].append({"file": csv_path.name, "summary": summary})
                    counts["stocks"] += 1
                except Exception as e:
                    results["stocks"].append({"file": csv_path.name, "error": str(e)})
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

    @staticmethod
    def reset_portfolio_and_reimport(db: Session) -> Dict[str, Any]:
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
            raise RuntimeError(f"Failed to purge data: {e}")
        return ImporterService.scan_seed_folder(db)
