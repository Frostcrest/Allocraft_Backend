"""
Seed-drop CSV import logic for Allocraft FastAPI app startup.
Extracted from main.py for clarity and testability.
"""
from pathlib import Path
from typing import Optional
from .database import SessionLocal

def import_seed_drop_folder(folder: Optional[str]) -> None:
    if not folder:
        return
    try:
        basedir = Path(folder)
        if not basedir.exists() or not basedir.is_dir():
            return
        db = SessionLocal()
        try:
            # Wheels: only scan wheels subfolder
            wheels_dir = basedir / "wheels"
            if wheels_dir.exists() and wheels_dir.is_dir():
                from .importers.wheel_tracker import import_wheel_tracker_csv
                for csv_path in sorted(wheels_dir.glob("*.csv")):
                    try:
                        import_wheel_tracker_csv(db, str(csv_path))
                    except Exception:
                        continue
            # Stocks: scan stocks subfolder
            stocks_dir = basedir / "stocks"
            if stocks_dir.exists() and stocks_dir.is_dir():
                from .importers.stock_importer import import_stock_csv
                for csv_path in sorted(stocks_dir.glob("*.csv")):
                    try:
                        import_stock_csv(db, str(csv_path))
                    except Exception:
                        continue
            # Options: scan options subfolder
            options_dir = basedir / "options"
            if options_dir.exists() and options_dir.is_dir():
                from .importers.option_importer import import_option_csv
                for csv_path in sorted(options_dir.glob("*.csv")):
                    try:
                        import_option_csv(db, str(csv_path))
                    except Exception:
                        continue
        finally:
            db.close()
    except Exception:
        pass
