from __future__ import annotations

"""
Wheel Tracker CSV importer

Parses the exported CSV from the Wheel Tracker sheet and stores:
- a WheelCycle (cycle_key defaults to filename stem unless provided)
- WheelEvents for option opens/closes and stock buys/sells
- Rebuilds lots for the cycle

The importer is designed to be tolerant of:
- leading/trailing blank rows
- spreadsheet formulas like =IF(...), __xludf.dummyfunction(...)
- currency strings like $200.00 and numbers embedded in text

Usage (programmatic):
    summary = import_wheel_tracker_csv(db, path_to_csv, cycle_key=None)

Returned summary contains counts by event type and lots created.
"""

from dataclasses import dataclass
from pathlib import Path
import csv
from datetime import datetime, date, UTC
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app import models, crud, schemas


@dataclass
class ImportSummary:
    cycle_id: int
    ticker: str
    events_created_by_type: Dict[str, int]
    lots_created: int
    date_range: Tuple[Optional[str], Optional[str]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "ticker": self.ticker,
            "events_created_by_type": self.events_created_by_type,
            "lots_created": self.lots_created,
            "date_range": self.date_range,
        }


def _clean_str(s: Any) -> str:
    if s is None:
        return ""
    if isinstance(s, (int, float)):
        return str(s)
    return str(s).strip()


def _parse_money(s: Any) -> Optional[float]:
    txt = _clean_str(s)
    if not txt or txt.startswith("="):
        return None
    # remove currency symbols, commas, spaces
    txt = (
        txt.replace("$", "")
        .replace(",", "")
        .replace("USD", "")
        .replace(" ", "")
    )
    # handle parentheses for negatives
    neg = False
    if txt.startswith("(") and txt.endswith(")"):
        neg = True
        txt = txt[1:-1]
    try:
        val = float(txt)
        return -val if neg else val
    except Exception:
        return None


def _parse_int(s: Any) -> Optional[int]:
    txt = _clean_str(s)
    if not txt or txt.startswith("="):
        return None
    try:
        return int(float(txt))
    except Exception:
        return None


def _parse_date(s: Any) -> Optional[str]:
    txt = _clean_str(s)
    if not txt or txt.startswith("="):
        return None
    fmts = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%m/%d/%Y %H:%M",
        "%m/%d/%y %H:%M",
    ]
    for fmt in fmts:
        try:
            d = datetime.strptime(txt, fmt).date()
            return d.isoformat()
        except Exception:
            continue
    # try to coerce like 8/8 or 8/8/25 without century
    try:
        parts = [p for p in txt.replace("-", "/").split("/") if p]
        if len(parts) >= 2:
            m = int(parts[0])
            d = int(parts[1])
            y = datetime.now(UTC).year
            if len(parts) >= 3:
                yy = int(parts[2])
                if yy < 100:
                    y = 2000 + yy
                else:
                    y = yy
            return date(y, m, d).isoformat()
    except Exception:
        pass
    return None


def _find_symbol(rows: List[List[str]]) -> Optional[str]:
    # Look for a cell with 'Symbol' and take the next non-empty cell in the same row
    for row in rows:
        for i, cell in enumerate(row):
            if _clean_str(cell).lower() == "symbol":
                # next non-empty cell to the right
                for j in range(i + 1, len(row)):
                    val = _clean_str(row[j]).upper()
                    if val and not val.startswith("="):
                        return val
    return None


def _import_rows(db: Session, raw_rows: List[List[str]], *, filename: str, cycle_key: Optional[str] = None) -> Dict[str, Any]:
    # Determine symbol
    ticker = _find_symbol(raw_rows) or Path(filename).stem.split("_")[0].upper()
    if not ticker:
        raise ValueError("Unable to determine ticker symbol from CSV")

    # Establish a cycle
    key = (cycle_key or Path(filename).stem).upper()
    cycle = db.query(models.WheelCycle).filter(models.WheelCycle.cycle_key == key).first()
    if not cycle:
        cycle = models.WheelCycle(
            cycle_key=key,
            ticker=ticker,
            started_at=None,
            status="Open",
            notes=f"Imported from {Path(filename).name}",
        )
        db.add(cycle)
        db.flush()

    # If events already exist for this cycle, do nothing to keep idempotent behavior
    if db.query(models.WheelEvent).filter(models.WheelEvent.cycle_id == cycle.id).count() > 0:
        return ImportSummary(cycle_id=cycle.id, ticker=ticker, events_created_by_type={}, lots_created=0, date_range=(None, None)).to_dict()

    # Column indices (0-based) inferred from provided CSVs
    opened_idx = 4
    cp_idx = 5
    bs_idx = 6
    exp_idx = 7
    strike_idx = 8
    qty_idx = 9
    price_idx = 10
    status_idx = 12  # Closed/Expired/Rolled
    date_closed_idx = 13
    closing_cost_idx = 14

    stock_date_idx = 19
    stock_bs_idx = 21
    shares_idx = 22
    cost_idx = 23

    created_by_type: Dict[str, int] = {}
    first_date: Optional[str] = None
    last_date: Optional[str] = None

    def bump(et: str):
        created_by_type[et] = created_by_type.get(et, 0) + 1

    # Keep stacks of opens for linking
    open_stack: Dict[str, List[models.WheelEvent]] = {"PUT": [], "CALL": []}

    def record_date(d: Optional[str]):
        nonlocal first_date, last_date
        if not d:
            return
        if not first_date or d < first_date:
            first_date = d
        if not last_date or d > last_date:
            last_date = d

    # Iterate rows and try both option and stock segments
    for row in raw_rows:
        # Option segment
        if len(row) > price_idx:
            opened = _parse_date(row[opened_idx] if len(row) > opened_idx else None)
            cp = _clean_str(row[cp_idx] if len(row) > cp_idx else "").upper()
            bs = _clean_str(row[bs_idx] if len(row) > bs_idx else "").upper()
            strike = _parse_money(row[strike_idx] if len(row) > strike_idx else None)
            qty = _parse_int(row[qty_idx] if len(row) > qty_idx else None)
            price = _parse_money(row[price_idx] if len(row) > price_idx else None)
            status = _clean_str(row[status_idx] if len(row) > status_idx else "").upper()
            closed_date = _parse_date(row[date_closed_idx] if len(row) > date_closed_idx else None)
            closing_cost = _parse_money(row[closing_cost_idx] if len(row) > closing_cost_idx else None)

            # Create open event
            if opened and cp in {"PUT", "CALL"} and bs in {"SELL", "BUY"} and qty and price is not None:
                if bs == "BUY":
                    # We only track sell-side cashflows for now; skip buy-to-open
                    pass
                else:
                    et = "SELL_PUT_OPEN" if cp == "PUT" else "SELL_CALL_OPEN"
                    evt = models.WheelEvent(
                        cycle_id=cycle.id,
                        event_type=et,
                        trade_date=opened,
                        contracts=qty,
                        strike=strike,
                        premium=price,
                        fees=0.0,
                    )
                    db.add(evt)
                    db.flush()
                    open_stack[cp].append(evt)
                    bump(et)
                    record_date(opened)

            # Create close/expire/rolled event if present
            if closed_date and cp in {"PUT", "CALL"} and closing_cost is not None and status in {"CLOSED", "ROLLED", "EXPIRED", "CLOSED/EXPIRED/ROLLED", "PENDING"}:
                etc = "SELL_PUT_CLOSE" if cp == "PUT" else "SELL_CALL_CLOSE"
                link_id: Optional[int] = None
                # Try to link to the most recent open
                stack = open_stack.get(cp) or []
                if stack:
                    link_id = stack[-1].id
                evtc = models.WheelEvent(
                    cycle_id=cycle.id,
                    event_type=etc,
                    trade_date=closed_date,
                    contracts=qty or 1,
                    premium=closing_cost,
                    fees=0.0,
                    link_event_id=link_id,
                )
                db.add(evtc)
                db.flush()
                bump(etc)
                record_date(closed_date)

        # Stock segment
        if len(row) > cost_idx:
            sdate = _parse_date(row[stock_date_idx] if len(row) > stock_date_idx else None)
            sbs = _clean_str(row[stock_bs_idx] if len(row) > stock_bs_idx else "").upper()
            shares = _parse_int(row[shares_idx] if len(row) > shares_idx else None)
            cost = _parse_money(row[cost_idx] if len(row) > cost_idx else None)

            if sdate and sbs in {"BUY", "SELL"} and shares and cost is not None:
                if sbs == "BUY":
                    et = "BUY_SHARES"
                    evt = models.WheelEvent(
                        cycle_id=cycle.id,
                        event_type=et,
                        trade_date=sdate,
                        quantity_shares=shares,
                        price=cost,
                        fees=0.0,
                    )
                else:
                    et = "SELL_SHARES"
                    evt = models.WheelEvent(
                        cycle_id=cycle.id,
                        event_type=et,
                        trade_date=sdate,
                        quantity_shares=shares,
                        price=cost,
                        fees=0.0,
                    )
                db.add(evt)
                db.flush()
                bump(et)
                record_date(sdate)

    db.commit()

    # Set started_at if we captured any dates
    if first_date and not cycle.started_at:
        cycle.started_at = first_date
        db.commit()

    # Rebuild lots for the cycle
    lots = crud.rebuild_lots_for_cycle(db, cycle.id)

    return ImportSummary(
        cycle_id=cycle.id,
        ticker=ticker,
        events_created_by_type=created_by_type,
        lots_created=len(lots),
        date_range=(first_date, last_date),
    ).to_dict()


def import_wheel_tracker_csv(db: Session, csv_path: str, cycle_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Import a Wheel Tracker CSV file from disk and rebuild lots.
    """
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(csv_path)
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        raw_rows = [[c for c in row] for row in reader]
    return _import_rows(db, raw_rows, filename=p.name, cycle_key=cycle_key)


def import_wheel_tracker_bytes(db: Session, data: bytes, filename: str = "upload.csv", cycle_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Import a Wheel Tracker CSV from in-memory bytes (for uploads) and rebuild lots.
    """
    text = data.decode("utf-8-sig", errors="ignore")
    reader = csv.reader(text.splitlines())
    raw_rows = [[c for c in row] for row in reader]
    return _import_rows(db, raw_rows, filename=filename, cycle_key=cycle_key)
