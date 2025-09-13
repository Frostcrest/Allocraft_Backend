

from sqlalchemy.orm import Session
from .. import models, schemas, crud
from typing import List, Optional, Dict, Any
import csv
import io

class WheelService:

    # --- Detection, Analytics, and Utility Functions ---
    @staticmethod
    def calculate_days_to_expiration(expiration_date: str) -> int:
        from datetime import datetime, UTC
        try:
            if "T" in expiration_date:
                exp_date = datetime.fromisoformat(expiration_date.replace("Z", "+00:00"))
            else:
                exp_date = datetime.fromisoformat(expiration_date)
            today = datetime.now(UTC)
            diff_time = exp_date - today
            return max(0, diff_time.days)
        except Exception:
            return 0

    @staticmethod
    def calculate_confidence_score(strategy, positions, cash_required=0, cash_balance=0, market_context=None):
        score = 50
        strategy_scores = {'full_wheel': 30, 'covered_call': 20, 'cash_secured_put': 15, 'naked_stock': 10}
        score += strategy_scores.get(strategy, 0)
        if cash_required > 0:
            if cash_balance >= cash_required:
                score += 15
            elif cash_balance >= cash_required * 0.5:
                score += 5
            else:
                score -= 10
        option_positions = [p for p in positions if getattr(p, 'days_to_expiration', None) is not None]
        if option_positions:
            avg_days_to_exp = sum(p.days_to_expiration for p in option_positions) / len(option_positions)
            if avg_days_to_exp > 30:
                score += 10
            elif avg_days_to_exp < 7:
                score -= 15
        if market_context:
            if getattr(market_context, 'volatility', None) and market_context.volatility > 0.3:
                score += 5
            if getattr(market_context, 'market_trend', None) == 'bullish':
                score += 5
        score = max(0, min(100, score))
        if score >= 70:
            confidence = 'high'
        elif score >= 40:
            confidence = 'medium'
        else:
            confidence = 'low'
        return confidence, score

    @staticmethod
    def calculate_cash_required(short_puts):
        total = 0.0
        for put in short_puts:
            if getattr(put, 'type', None) == 'put' and getattr(put, 'position', None) == 'short' and getattr(put, 'strike_price', None):
                contracts = abs(getattr(put, 'raw_quantity', 0) or 0) / 100 if getattr(put, 'raw_quantity', None) else getattr(put, 'quantity', 0) / 100
                total += contracts * put.strike_price * 100
        return total

    @staticmethod
    def assess_risk(strategy, positions, options=None):
        factors = []
        level = "medium"
        assignment_risk = 50.0
        short_options = [p for p in positions if getattr(p, 'position', None) == 'short' and getattr(p, 'days_to_expiration', None) is not None]
        if short_options:
            min_days_to_exp = min(p.days_to_expiration for p in short_options)
            if min_days_to_exp < 7:
                factors.append('Options expiring within 7 days - high assignment risk')
                assignment_risk = 80.0
                level = 'high'
            elif min_days_to_exp < 21:
                factors.append('Options expiring within 3 weeks - moderate assignment risk')
                assignment_risk = 60.0
        if options and getattr(options, 'risk_tolerance', None):
            if options.risk_tolerance == 'conservative':
                factors.append('Conservative risk profile - consider safer strikes')
                if level == 'medium':
                    level = 'high'
            elif options.risk_tolerance == 'aggressive':
                factors.append('Aggressive risk profile - monitor positions closely')
        if strategy == 'cash_secured_put':
            factors.append('Assignment would result in stock ownership')
            if assignment_risk > 70:
                factors.append('High probability of assignment at current levels')
        elif strategy == 'covered_call':
            factors.append('Call assignment would result in stock sale')
        elif strategy == 'full_wheel':
            factors.append('Multiple assignment possibilities - complex management')
            if level != 'high':
                level = 'medium'
        from ..schemas import RiskAssessment
        return RiskAssessment(level=level, factors=factors, assignment_risk=assignment_risk)

    @staticmethod
    def group_positions_by_ticker(positions):
        grouped = {}
        for position in positions:
            ticker = getattr(position, 'underlying_symbol', None) if getattr(position, 'is_option', False) else getattr(position, 'symbol', None)
            if ticker not in grouped:
                grouped[ticker] = []
            grouped[ticker].append(position)
        return grouped

    @staticmethod
    def analyze_ticker_positions(ticker, positions, options=None):
        from ..schemas import EnhancedPosition, WheelDetectionResult, PotentialAction
        from .wheel_service import WheelService
        stock_positions = [p for p in positions if not getattr(p, 'is_option', False)]
        option_positions = [p for p in positions if getattr(p, 'is_option', False)]
        call_options = [p for p in option_positions if getattr(p, 'option_type', None) and p.option_type.upper() == 'CALL']
        put_options = [p for p in option_positions if getattr(p, 'option_type', None) and p.option_type.upper() == 'PUT']
        total_stock_shares = sum(getattr(p, 'shares', 0) for p in stock_positions)
        short_calls = [p for p in call_options if (getattr(p, 'contracts', 0) or 0) < 0]
        short_puts = [p for p in put_options if (getattr(p, 'contracts', 0) or 0) < 0]
        formatted_positions = []
        for p in positions:
            is_short_position = getattr(p, 'is_option', False) and (getattr(p, 'contracts', 0) or 0) < 0 or not getattr(p, 'is_option', False) and getattr(p, 'shares', 0) < 0
            raw_quantity = p.contracts if getattr(p, 'is_option', False) else getattr(p, 'shares', 0)
            days_to_expiration = WheelService.calculate_days_to_expiration(p.expiration_date) if getattr(p, 'expiration_date', None) else None
            enhanced_pos = EnhancedPosition(
                type='call' if getattr(p, 'is_option', False) and p.option_type == 'Call' else 'put' if getattr(p, 'is_option', False) and p.option_type == 'Put' else 'stock',
                symbol=p.symbol,
                quantity=abs(raw_quantity),
                position='short' if is_short_position else 'long',
                strike_price=getattr(p, 'strike_price', None),
                expiration_date=getattr(p, 'expiration_date', None),
                days_to_expiration=days_to_expiration,
                market_value=getattr(p, 'market_value', None),
                raw_quantity=raw_quantity,
                source=getattr(p, 'source', None)
            )
            formatted_positions.append(enhanced_pos)
        if WheelService.is_full_wheel(total_stock_shares, short_calls, short_puts):
            return WheelService.create_full_wheel_result(ticker, formatted_positions, short_puts, options)
        elif WheelService.is_covered_call(total_stock_shares, short_calls):
            return WheelService.create_covered_call_result(ticker, formatted_positions, total_stock_shares, short_calls, options)
        elif WheelService.is_cash_secured_put(short_puts):
            return WheelService.create_cash_secured_put_result(ticker, formatted_positions, short_puts, total_stock_shares, options)
        elif WheelService.is_naked_stock(total_stock_shares, option_positions):
            if total_stock_shares >= 100:
                return WheelService.create_naked_stock_result(ticker, formatted_positions, total_stock_shares, options)
        return None

    @staticmethod
    def is_full_wheel(stock_shares, short_calls, short_puts):
        return stock_shares >= 100 and len(short_calls) > 0 and len(short_puts) > 0

    @staticmethod
    def is_covered_call(stock_shares, short_calls):
        return stock_shares >= 100 and len(short_calls) > 0

    @staticmethod
    def is_cash_secured_put(short_puts):
        return len(short_puts) > 0

    @staticmethod
    def is_naked_stock(stock_shares, option_positions):
        return stock_shares > 0 and len(option_positions) == 0

    @staticmethod
    def create_full_wheel_result(ticker, positions, short_puts, options):
        from ..schemas import PotentialAction, WheelDetectionResult
        cash_required = WheelService.calculate_cash_required([p for p in positions if p.type == 'put' and p.position == 'short'])
        confidence, score = WheelService.calculate_confidence_score('full_wheel', positions, cash_required, getattr(options, 'cash_balance', 0) if options else 0, getattr(options, 'market_data', None) if options else None)
        risk_assessment = WheelService.assess_risk('full_wheel', positions, options)
        return WheelDetectionResult(
            ticker=ticker,
            strategy='full_wheel',
            confidence=confidence,
            confidence_score=score,
            description=f'Complete wheel strategy: {sum(p.quantity for p in positions if p.type == "stock")} shares with covered call and put-selling capability',
            cash_required=cash_required,
            cash_validated=getattr(options, 'cash_balance', 0) >= cash_required if options and getattr(options, 'cash_balance', None) else None,
            risk_assessment=risk_assessment,
            positions=positions,
            recommendations=[
                'Monitor covered call for expiration or early assignment',
                'Consider rolling call option if needed',
                'Look for opportunities to sell additional puts if assigned'
            ],
            potential_actions=[
                PotentialAction(action='roll_call', description='Roll covered call to later expiration', priority='high'),
                PotentialAction(action='close_call', description='Buy back call option for profit', priority='medium'),
                PotentialAction(action='sell_put', description='Sell additional cash-secured puts', priority='low')
            ],
            market_context=getattr(options, 'market_data', None) if options else None
        )

    @staticmethod
    def create_covered_call_result(ticker, positions, total_stock_shares, short_calls, options):
        from ..schemas import PotentialAction, WheelDetectionResult
        confidence, score = WheelService.calculate_confidence_score('covered_call', positions, 0, getattr(options, 'cash_balance', 0) if options else 0)
        risk_assessment = WheelService.assess_risk('covered_call', positions, options)
        short_call_count = len([p for p in positions if p.type == 'call' and p.position == 'short'])
        return WheelDetectionResult(
            ticker=ticker,
            strategy='covered_call',
            confidence=confidence,
            confidence_score=score,
            description=f'Covered call position: {total_stock_shares} shares with {short_call_count} short call(s)',
            risk_assessment=risk_assessment,
            positions=positions,
            recommendations=[
                'Monitor for potential assignment at expiration',
                'Consider rolling call if wanting to keep shares',
                'Could evolve into full wheel by selling puts'
            ],
            potential_actions=[
                PotentialAction(action='roll_call', description='Extend call expiration', priority='high'),
                PotentialAction(action='sell_put', description='Start wheel by selling puts below current price', priority='medium')
            ],
            market_context=getattr(options, 'market_data', None) if options else None
        )

    @staticmethod
    def create_cash_secured_put_result(ticker, positions, short_puts, total_stock_shares, options):
        from ..schemas import PotentialAction, WheelDetectionResult
        cash_required = WheelService.calculate_cash_required([p for p in positions if p.type == 'put' and p.position == 'short'])
        confidence, score = WheelService.calculate_confidence_score('cash_secured_put', positions, cash_required, getattr(options, 'cash_balance', 0) if options else 0)
        risk_assessment = WheelService.assess_risk('cash_secured_put', positions, options)
        short_put_count = len([p for p in positions if p.type == 'put' and p.position == 'short'])
        return WheelDetectionResult(
            ticker=ticker,
            strategy='cash_secured_put',
            confidence=confidence,
            confidence_score=score,
            description=f'Cash-secured put position: {short_put_count} short put(s) {f"with {total_stock_shares} existing shares" if total_stock_shares > 0 else ""}',
            cash_required=cash_required,
            cash_validated=getattr(options, 'cash_balance', 0) >= cash_required if options and getattr(options, 'cash_balance', None) else None,
            risk_assessment=risk_assessment,
            positions=positions,
            recommendations=[
                'Prepare for potential assignment',
                'Ensure sufficient cash to purchase shares',
                'Plan covered call strategy if assigned'
            ],
            potential_actions=[
                PotentialAction(action='manage_assignment', description='Prepare for potential share assignment', priority='high'),
                PotentialAction(action='roll_put', description='Roll put to avoid assignment', priority='medium')
            ],
            market_context=getattr(options, 'market_data', None) if options else None
        )

    @staticmethod
    def create_naked_stock_result(ticker, positions, total_stock_shares, options):
        from ..schemas import PotentialAction, WheelDetectionResult
        confidence, score = WheelService.calculate_confidence_score('naked_stock', positions, 0, getattr(options, 'cash_balance', 0) if options else 0)
        risk_assessment = WheelService.assess_risk('naked_stock', positions, options)
        return WheelDetectionResult(
            ticker=ticker,
            strategy='naked_stock',
            confidence=confidence,
            confidence_score=score,
            description=f'{total_stock_shares} shares ready for wheel strategy',
            risk_assessment=risk_assessment,
            positions=positions,
            recommendations=[
                'Consider selling covered calls to generate income',
                'Stock position is suitable for wheel strategy',
                'Could start with covered calls above current price'
            ],
            potential_actions=[
                PotentialAction(action='sell_call', description='Start covered call strategy', priority='high'),
                PotentialAction(action='start_wheel', description='Begin full wheel strategy', priority='medium')
            ],
            market_context=getattr(options, 'market_data', None) if options else None
        )

    @staticmethod
    def detect_wheel_strategies(request, db):
        from ..models_unified import Position
        from ..schemas import PositionForDetection
        query = db.query(Position).filter(Position.is_active == True)
        if getattr(request, 'account_id', None):
            query = query.filter(Position.account_id == request.account_id)
        positions = query.all()
        detection_positions = []
        for pos in positions:
            ticker = pos.underlying_symbol or pos.symbol
            if getattr(request, 'specific_tickers', None) and ticker.upper() not in [t.upper() for t in request.specific_tickers]:
                continue
            contracts = None
            if pos.asset_type == "OPTION":
                contracts = pos.long_quantity - pos.short_quantity
            detection_pos = PositionForDetection(
                id=str(pos.id),
                symbol=pos.symbol,
                shares=pos.long_quantity - pos.short_quantity,
                is_option=pos.asset_type == "OPTION",
                underlying_symbol=pos.underlying_symbol,
                option_type=pos.option_type,
                strike_price=pos.strike_price,
                expiration_date=pos.expiration_date.isoformat() if pos.expiration_date else None,
                contracts=contracts,
                market_value=pos.market_value or 0.0,
                source=pos.data_source or "unknown"
            )
            detection_positions.append(detection_pos)
        if not detection_positions:
            return []
        grouped_positions = WheelService.group_positions_by_ticker(detection_positions)
        results = []
        strategy_order = {'full_wheel': 0, 'covered_call': 1, 'cash_secured_put': 2, 'naked_stock': 3}
        for ticker, ticker_positions in grouped_positions.items():
            detection_result = WheelService.analyze_ticker_positions(ticker, ticker_positions, getattr(request, 'options', None))
            if detection_result:
                results.append(detection_result)
        results.sort(key=lambda x: (strategy_order.get(x.strategy, 4), -x.confidence_score))
        return results
    # --- Optimized Endpoints ---
    @staticmethod
    def get_ticker_wheel_data_optimized(db: Session, ticker: str) -> dict:
        from ..crud_optimized import BatchLoaderService
        data = BatchLoaderService.get_wheel_data_for_ticker(db, ticker)
        from .. import schemas
        return {
            "cycles": [
                schemas.WheelCycleRead(
                    id=c.id,
                    ticker=c.ticker,
                    status=c.status,
                    start_date=c.start_date,
                    end_date=c.end_date,
                    notes=c.notes,
                    detection_metadata=c.detection_metadata,
                ) for c in data["cycles"]
            ],
            "events": [
                schemas.WheelEventRead(
                    id=e.id,
                    cycle_id=e.cycle_id,
                    event_type=e.event_type,
                    trade_date=e.trade_date,
                    quantity_shares=e.quantity_shares,
                    contracts=e.contracts,
                    price=e.price,
                    strike=e.strike,
                    premium=e.premium,
                    fees=e.fees,
                    link_event_id=e.link_event_id,
                    notes=e.notes,
                ) for e in data["events"]
            ],
            "lots": [
                schemas.LotRead(
                    id=l.id,
                    cycle_id=l.cycle_id,
                    ticker=l.ticker,
                    status=l.status,
                    covered=l.covered,
                    cost_basis=l.cost_basis,
                    acquisition_date=l.acquisition_date,
                    notes=l.notes,
                ) for l in data["lots"]
            ],
            "events_by_lot": data["events_by_lot"],
            "metrics": data["metrics"],
        }
    # --- Metrics and Summary ---
    @staticmethod
    def get_wheel_metrics(db: Session, cycle_id: int):
        return crud.calculate_wheel_metrics(db, cycle_id)

    @staticmethod
    def wheels_summary(db: Session):
        open_cycles = db.query(models.WheelCycle).filter(models.WheelCycle.status == "Open").all()
        cycle_ids = [c.id for c in open_cycles]
        total_collateral = 0.0
        if cycle_ids:
            open_puts = (
                db.query(models.WheelEvent)
                .filter(models.WheelEvent.cycle_id.in_(cycle_ids))
                .filter(models.WheelEvent.event_type == "SELL_PUT_OPEN")
                .all()
            )
            for e in open_puts:
                if e.contracts and e.strike:
                    total_collateral += float(e.contracts) * float(e.strike) * 100.0
        return {"open_cycles": len(open_cycles), "total_collateral": total_collateral}
    # --- Lot Endpoints ---
    @staticmethod
    def list_cycle_lots(db: Session, cycle_id: int, status: str | None = None, covered: bool | None = None, ticker: str | None = None):
        return crud.list_lots(db, cycle_id=cycle_id, status=status, covered=covered, ticker=ticker)

    @staticmethod
    def get_lot(db: Session, lot_id: int):
        return crud.get_lot(db, lot_id)

    @staticmethod
    def patch_lot(db: Session, lot_id: int, payload: schemas.LotUpdate):
        base = crud.get_lot(db, lot_id)
        if not base:
            return None
        updated = crud.update_lot(db, lot_id, schemas.LotBase(**{**base.__dict__, **payload.model_dump(exclude_unset=True)}))
        return updated

    @staticmethod
    def get_lot_metrics(db: Session, lot_id: int):
        return crud.refresh_lot_metrics(db, lot_id)

    @staticmethod
    def rebuild_lots(db: Session, cycle_id: int):
        lots = crud.rebuild_lots_for_cycle(db, cycle_id)
        return lots

    @staticmethod
    def bind_call(db: Session, lot_id: int, option_event_id: int):
        lot = crud.get_lot(db, lot_id)
        if not lot:
            return None, "Lot not found"
        evt = crud.get_wheel_event(db, option_event_id)
        if not evt or evt.event_type != "SELL_CALL_OPEN":
            return None, "Invalid option event to bind"
        crud.create_lot_link(db, schemas.LotLinkCreate(lot_id=lot_id, linked_object_type="WHEEL_EVENT", linked_object_id=evt.id, role="CALL_OPEN"))
        lot.status = "OPEN_COVERED"
        db.commit()
        crud.refresh_lot_metrics(db, lot_id)
        return {"detail": "Bound"}, None

    @staticmethod
    def unbind_call(db: Session, lot_id: int):
        lot = crud.get_lot(db, lot_id)
        if not lot:
            return None
        links = crud.list_lot_links(db, lot_id)
        for l in links:
            if l.role in ("CALL_OPEN", "CALL_CLOSE"):
                crud.delete_lot_link(db, l.id)
        lot.status = "OPEN_UNCOVERED"
        db.commit()
        crud.refresh_lot_metrics(db, lot_id)
        return {"detail": "Unbound"}

    @staticmethod
    def bind_call_close(db: Session, lot_id: int, option_event_id: int):
        lot = crud.get_lot(db, lot_id)
        if not lot:
            return None, "Lot not found"
        evt = crud.get_wheel_event(db, option_event_id)
        if not evt or evt.event_type != "SELL_CALL_CLOSE":
            return None, "Invalid close event to bind"
        crud.create_lot_link(db, schemas.LotLinkCreate(lot_id=lot_id, linked_object_type="WHEEL_EVENT", linked_object_id=evt.id, role="CALL_CLOSE"))
        if lot.status == "OPEN_COVERED":
            lot.status = "OPEN_UNCOVERED"
            db.commit()
        crud.refresh_lot_metrics(db, lot_id)
        return {"detail": "Bound close"}, None

    @staticmethod
    def get_lot_links(db: Session, lot_id: int):
        links = crud.list_lot_links(db, lot_id)
        event_ids = [l.linked_object_id for l in links if l.linked_object_type == "WHEEL_EVENT"]
        events = []
        if event_ids:
            events = (
                db.query(models.WheelEvent)
                .filter(models.WheelEvent.id.in_(event_ids))
                .order_by(models.WheelEvent.trade_date.asc(), models.WheelEvent.id.asc())
                .all()
            )
        return {
            "links": [schemas.LotLinkRead(id=l.id, lot_id=l.lot_id, linked_object_type=l.linked_object_type, linked_object_id=l.linked_object_id, role=l.role) for l in links],
            "events": [
                schemas.WheelEventRead(
                    id=e.id,
                    cycle_id=e.cycle_id,
                    event_type=e.event_type,
                    trade_date=e.trade_date,
                    quantity_shares=e.quantity_shares,
                    contracts=e.contracts,
                    price=e.price,
                    strike=e.strike,
                    premium=e.premium,
                    fees=e.fees,
                    link_event_id=e.link_event_id,
                    notes=e.notes,
                ) for e in events
            ]
        }
    # --- Event-based Wheel Cycles ---
    @staticmethod
    def list_wheel_cycles(db: Session) -> list:
        return crud.list_wheel_cycles(db)

    @staticmethod
    def create_wheel_cycle(db: Session, payload: schemas.WheelCycleCreate):
        return crud.create_wheel_cycle(db, payload)

    @staticmethod
    def update_wheel_cycle(db: Session, cycle_id: int, payload: schemas.WheelCycleCreate):
        return crud.update_wheel_cycle(db, cycle_id, payload)

    @staticmethod
    def delete_wheel_cycle(db: Session, cycle_id: int) -> bool:
        return crud.delete_wheel_cycle(db, cycle_id)

    # --- Event-based Wheel Events ---
    @staticmethod
    def list_wheel_events(db: Session, cycle_id: Optional[int] = None) -> list:
        return crud.list_wheel_events(db, cycle_id)

    @staticmethod
    def create_wheel_event(db: Session, payload: schemas.WheelEventCreate):
        return crud.create_wheel_event(db, payload)

    @staticmethod
    def update_wheel_event(db: Session, event_id: int, payload: schemas.WheelEventCreate):
        return crud.update_wheel_event(db, event_id, payload)

    @staticmethod
    def delete_wheel_event(db: Session, event_id: int) -> bool:
        return crud.delete_wheel_event(db, event_id)
    @staticmethod
    def get_all_wheels(db: Session) -> List[models.WheelStrategy]:
        return crud.get_wheels(db)

    @staticmethod
    def create_wheel(db: Session, wheel: schemas.WheelStrategyCreate) -> models.WheelStrategy:
        return crud.create_wheel(db, wheel)

    @staticmethod
    def update_wheel(db: Session, wheel_id: int, wheel: schemas.WheelStrategyCreate) -> models.WheelStrategy:
        return crud.update_wheel(db, wheel_id, wheel)

    @staticmethod
    def delete_wheel(db: Session, wheel_id: int) -> bool:
        return crud.delete_wheel(db, wheel_id)

    @staticmethod
    def parse_wheels_csv(contents: bytes) -> List[models.WheelStrategy]:
        decoded = contents.decode("utf-8").splitlines()
        reader = csv.DictReader(decoded)
        wheels = []
        for row in reader:
            try:
                db_wheel = models.WheelStrategy(
                    wheel_id=row.get("wheel_id") or f"{row['ticker'].strip().upper()}-W",
                    ticker=row["ticker"].strip().upper(),
                    trade_date=row.get("trade_date"),
                    sell_put_strike_price=float(row["sell_put_strike_price"]) if row.get("sell_put_strike_price") else None,
                    sell_put_open_premium=float(row["sell_put_open_premium"]) if row.get("sell_put_open_premium") else None,
                    sell_put_closed_premium=float(row["sell_put_closed_premium"]) if row.get("sell_put_closed_premium") else None,
                    sell_put_status=row.get("sell_put_status"),
                    sell_put_quantity=int(row["sell_put_quantity"]) if row.get("sell_put_quantity") else None,
                    assignment_strike_price=float(row["assignment_strike_price"]) if row.get("assignment_strike_price") else None,
                    assignment_shares_quantity=int(row["assignment_shares_quantity"]) if row.get("assignment_shares_quantity") else None,
                    assignment_status=row.get("assignment_status"),
                    sell_call_strike_price=float(row["sell_call_strike_price"]) if row.get("sell_call_strike_price") else None,
                    sell_call_open_premium=float(row["sell_call_open_premium"]) if row.get("sell_call_open_premium") else None,
                    sell_call_closed_premium=float(row["sell_call_closed_premium"]) if row.get("sell_call_closed_premium") else None,
                    sell_call_status=row.get("sell_call_status"),
                    sell_call_quantity=int(row["sell_call_quantity"]) if row.get("sell_call_quantity") else None,
                    called_away_strike_price=float(row["called_away_strike_price"]) if row.get("called_away_strike_price") else None,
                    called_away_shares_quantity=int(row["called_away_shares_quantity"]) if row.get("called_away_shares_quantity") else None,
                    called_away_status=row.get("called_away_status"),
                )
                wheels.append(db_wheel)
            except Exception:
                continue
        return wheels

    @staticmethod
    def bulk_add_wheels(db: Session, wheels: List[models.WheelStrategy]) -> int:
        for wheel in wheels:
            db.add(wheel)
        db.commit()
        return len(wheels)
