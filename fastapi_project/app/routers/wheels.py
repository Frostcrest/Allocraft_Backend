
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .. import schemas, crud, models
from ..schemas import WheelDetectionRequest, WheelDetectionResult
from ..services.wheel_service import WheelService
from ..models_unified import Position
from ..database import get_db
from ..crud_optimized import BatchLoaderService, MetricsService, refresh_prices_batch
from fastapi.responses import StreamingResponse

import io
import csv
import math
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, UTC

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wheels", tags=["Wheels"])

# Alias endpoint for frontend compatibility (must be after router definition)
@router.get("/wheel-cycles")
def list_wheel_cycles_alias(db: Session = Depends(get_db)):
    """Alias for /wheels/cycles to support legacy/frontend expectations."""
    try:
        cycles = WheelService.list_wheel_cycles(db)
        return {"cycles": cycles}
    except Exception as e:
        logger.error(f"Failed to list wheel cycles (alias): {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list wheel cycles (alias)")

@router.get("/cycles")
def list_wheel_cycles(db: Session = Depends(get_db)):
    """List all wheel cycles (for API smoke test compatibility)."""
    try:
        cycles = WheelService.list_wheel_cycles(db)
        return {"cycles": cycles}
    except Exception as e:
        logger.error(f"Failed to list wheel cycles: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list wheel cycles")


@router.get("/", response_model=list[schemas.WheelStrategyRead])
def read_wheels(db: Session = Depends(get_db)):
    """Get all legacy (CSV-style) wheel strategies."""
    try:
        return WheelService.get_all_wheels(db)
    except Exception as e:
        logger.error(f"Failed to get wheels: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get wheels")

@router.post("/", response_model=schemas.WheelStrategyRead)
def create_wheel(wheel: schemas.WheelStrategyCreate, db: Session = Depends(get_db)):
    """Add a new legacy wheel strategy."""
    try:
        return WheelService.create_wheel(db, wheel)
    except ValueError as e:
        logger.error(f"Invalid wheel creation: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create wheel: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create wheel")


@router.post("/detect", response_model=List[WheelDetectionResult])
async def detect_wheel_strategies(
    request: WheelDetectionRequest,
    db: Session = Depends(get_db)
):
    """Enhanced wheel strategy detection with unified data model integration."""
    try:
        return WheelService.detect_wheel_strategies(request, db)
    except ValueError as e:
        logger.error(f"Detection error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to detect wheel strategies: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to detect wheel strategies")
@router.put("/wheel_events/{event_id}", response_model=schemas.WheelEventRead)
def update_wheel_event(event_id: int, payload: schemas.WheelEventCreate, db: Session = Depends(get_db)):
    """Update a wheel event by ID."""
    try:
        updated = WheelService.update_wheel_event(db, event_id, payload)
        if not updated:
            raise HTTPException(status_code=404, detail="Wheel event not found")
        return updated
    except ValueError as e:
        logger.error(f"Update error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update wheel event: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update wheel event")


@router.delete("/wheel-events/{event_id}")
@router.delete("/wheel_events/{event_id}")
def delete_wheel_event(event_id: int, db: Session = Depends(get_db)):
    """Delete a wheel event by ID."""
    try:
        ok = WheelService.delete_wheel_event(db, event_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Wheel event not found")
        return {"detail": "Wheel event deleted"}
    except Exception as e:
        logger.error(f"Failed to delete wheel event: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete wheel event")


@router.get("/wheel-metrics/{cycle_id}", response_model=schemas.WheelMetricsRead)
@router.get("/wheel_metrics/{cycle_id}", response_model=schemas.WheelMetricsRead)
def get_wheel_metrics(cycle_id: int, db: Session = Depends(get_db)):
    """Get summary wheel metrics for a cycle."""
    try:
        return WheelService.get_wheel_metrics(db, cycle_id)
    except Exception as e:
        logger.error(f"Failed to get wheel metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get wheel metrics")


@router.post("/refresh-prices")
def refresh_wheel_prices(db: Session = Depends(get_db)):
    """Refresh real-time prices for all active wheel cycles."""
    try:
        from ..services.wheel_pnl_service import WheelPnLCalculator
        calculator = WheelPnLCalculator(db)
        result = calculator.refresh_all_wheel_pnl()
        return result
    except Exception as e:
        logger.error(f"Failed to refresh wheel prices: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to refresh wheel prices")


# --- Lot endpoints ---
@router.get("/cycles/{cycle_id}/lots", response_model=list[schemas.LotRead])
def list_cycle_lots(cycle_id: int, status: str | None = None, covered: bool | None = None, ticker: str | None = None, db: Session = Depends(get_db)):
    """List 100-share lots for a cycle with optional filters."""
    try:
        return WheelService.list_cycle_lots(db, cycle_id, status, covered, ticker)
    except Exception as e:
        logger.error(f"Failed to list lots: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list lots")


@router.get("/lots/{lot_id}", response_model=schemas.LotRead)
def get_lot(lot_id: int, db: Session = Depends(get_db)):
    """Get a single lot by ID."""
    lot = WheelService.get_lot(db, lot_id)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    return lot


@router.patch("/lots/{lot_id}", response_model=schemas.LotRead)
def patch_lot(lot_id: int, payload: schemas.LotUpdate, db: Session = Depends(get_db)):
    """Patch mutable fields of a lot (status, notes, cost basis, acquisition_date)."""
    updated = WheelService.patch_lot(db, lot_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Lot not found")
    return updated


@router.get("/lots/{lot_id}/metrics", response_model=schemas.LotMetricsRead)
def get_lot_metrics(lot_id: int, db: Session = Depends(get_db)):
    """Compute/refresh lot metrics and return them."""
    return WheelService.get_lot_metrics(db, lot_id)


@router.post("/lots/rebuild")
def rebuild_lots(cycle_id: int, db: Session = Depends(get_db)):
    """Rebuild lots deterministically from events for the given cycle."""
    lots = WheelService.rebuild_lots(db, cycle_id)
    return {"created": len(lots)}


class BindCallPayload(BaseModel):
    option_event_id: int


@router.post("/lots/{lot_id}/bind-call")
def bind_call(lot_id: int, payload: BindCallPayload, db: Session = Depends(get_db)):
    """Link an option SELL_CALL_OPEN event to a lot and mark it covered."""
    result, error = WheelService.bind_call(db, lot_id, payload.option_event_id)
    if error == "Lot not found":
        raise HTTPException(status_code=404, detail=error)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return result


@router.post("/lots/{lot_id}/unbind-call")
def unbind_call(lot_id: int, db: Session = Depends(get_db)):
    """Remove call links from a lot and mark it uncovered."""
    result = WheelService.unbind_call(db, lot_id)
    if not result:
        raise HTTPException(status_code=404, detail="Lot not found")
    return result


@router.post("/lots/{lot_id}/bind-call-close")
def bind_call_close(lot_id: int, payload: BindCallPayload, db: Session = Depends(get_db)):
    """Bind a SELL_CALL_CLOSE event to a covered lot and mark it uncovered."""
    result, error = WheelService.bind_call_close(db, lot_id, payload.option_event_id)
    if error == "Lot not found":
        raise HTTPException(status_code=404, detail=error)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return result


@router.get("/lots/{lot_id}/links")
def get_lot_links(lot_id: int, db: Session = Depends(get_db)):
    """Return lot links and their linked wheel events to aid the UI."""
    return WheelService.get_lot_links(db, lot_id)


# ===== OPTIMIZED ENDPOINTS FOR PERFORMANCE =====

@router.get("/tickers/{ticker}/wheel-data")
def get_ticker_wheel_data_optimized(
    ticker: str, 
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get comprehensive wheel data for a ticker in optimized queries.
    
    This endpoint replaces multiple individual calls with a single optimized request
    that fetches cycles, events, lots, and metrics in minimal database queries.
    
    Returns:
        - cycles: List of wheel cycles for the ticker
        - events: All events across all cycles
        - lots: All lots with their events pre-loaded
        - events_by_lot: Dict mapping lot_id to list of events
        - metrics: Aggregated metrics across all cycles
    """
    try:
        data = BatchLoaderService.get_wheel_data_for_ticker(db, ticker)
        
        # Convert to API response format
        return {
            "cycles": [
                schemas.WheelCycleRead(
                    id=c.id,
                    ticker=c.ticker,
                    cycle_key=c.cycle_key,
                    started_at=c.started_at,
                    ended_at=c.ended_at,
                    status=c.status,
                    initial_stock_price=c.initial_stock_price,
                    put_strike=c.put_strike,
                    capital_at_risk=c.capital_at_risk,
                    notes=c.notes
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
                    notes=e.notes
                ) for e in data["events"]
            ],
            "lots": [
                schemas.LotRead(
                    id=lot.id,
                    cycle_id=lot.cycle_id,
                    lot_id=lot.lot_id,
                    acquisition_method=lot.acquisition_method,
                    acquisition_date=lot.acquisition_date,
                    acquisition_price=lot.acquisition_price,
                    quantity_initial=lot.quantity_initial,
                    status=lot.status,
                    cost_basis=lot.cost_basis,
                    realized_pl=lot.realized_pl,
                    notes=lot.notes
                ) for lot in data["lots"]
            ],
            "events_by_lot": {
                str(lot_id): [
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
                        notes=e.notes
                    ) for e in events
                ] for lot_id, events in data["events_by_lot"].items()
            },
            "metrics": data["metrics"]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to load wheel data for ticker {ticker}: {str(e)}"
        )


@router.post("/refresh-prices")
def refresh_ticker_prices(
    tickers: list[str],
    db: Session = Depends(get_db)
) -> Dict[str, Optional[float]]:
    """
    Refresh current prices for multiple tickers efficiently.
    
    This endpoint batches price fetching and database updates to minimize
    API calls and database transactions.
    
    Args:
        tickers: List of ticker symbols to refresh
        
    Returns:
        Dict mapping ticker to current price (or None if failed)
    """
    try:
        # Convert to uppercase for consistency
        tickers_upper = [t.upper() for t in tickers]
        
        # Batch refresh prices
        results = refresh_prices_batch(db, tickers_upper)
        
        return results
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh prices: {str(e)}"
        )


class CycleMetricsRequest(BaseModel):
    cycle_ids: list[int]


@router.post("/metrics/aggregate")
def get_ticker_wheel_data_optimized(
    ticker: str, 
    db: Session = Depends(get_db)
) -> dict:
    """Get comprehensive wheel data for a ticker in optimized queries."""
    try:
        return WheelService.get_ticker_wheel_data_optimized(db, ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        for lot in lots:
            cycle_id = lot.cycle_id
            if cycle_id not in lots_by_cycle:
                lots_by_cycle[cycle_id] = []
            lots_by_cycle[cycle_id].append(lot)
        
        return {
            "cycles": [
                schemas.WheelCycleRead(
                    id=c.id,
                    ticker=c.ticker,
                    cycle_key=c.cycle_key,
                    started_at=c.started_at,
                    ended_at=c.ended_at,
                    status=c.status,
                    initial_stock_price=c.initial_stock_price,
                    put_strike=c.put_strike,
                    capital_at_risk=c.capital_at_risk,
                    notes=c.notes
                ) for c in cycles
            ],
            "lots_by_cycle": {
                str(cycle_id): [
                    schemas.LotRead(
                        id=lot.id,
                        cycle_id=lot.cycle_id,
                        lot_id=lot.lot_id,
                        acquisition_method=lot.acquisition_method,
                        acquisition_date=lot.acquisition_date,
                        acquisition_price=lot.acquisition_price,
                        quantity_initial=lot.quantity_initial,
                        status=lot.status,
                        cost_basis=lot.cost_basis,
                        realized_pl=lot.realized_pl,
                        notes=lot.notes
                    ) for lot in lots
                ] for cycle_id, lots in lots_by_cycle.items()
            },
            "events_by_lot": {
                str(lot_id): [
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
                        notes=e.notes
                    ) for e in events
                ] for lot_id, events in events_by_lot.items()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load cycles with lots: {str(e)}"
        )


# ===== ENHANCED WHEEL DETECTION ENDPOINTS =====

class WheelDetectionOptions(BaseModel):
    """Enhanced detection options for wheel strategy detection"""
    cash_balance: Optional[float] = None
    account_type: Optional[str] = None
    risk_tolerance: Optional[str] = "moderate"  # conservative, moderate, aggressive
    include_historical: Optional[bool] = False
    market_data: Optional[Dict[str, Any]] = None

class MarketContextData(BaseModel):
    """Market context for enhanced confidence scoring"""
    volatility: Optional[float] = None
    market_trend: Optional[str] = None  # bullish, bearish, neutral
    sector: Optional[str] = None
    market_cap: Optional[str] = None  # small, mid, large

class WheelDetectionRequest(BaseModel):
    """Request body for wheel detection"""
    options: Optional[WheelDetectionOptions] = None
    account_id: Optional[int] = None
    specific_tickers: Optional[List[str]] = None

class PositionForDetection(BaseModel):
    """Position data formatted for detection algorithm"""
    id: str
    symbol: str
    shares: float
    is_option: bool = False
    underlying_symbol: Optional[str] = None
    option_type: Optional[str] = None  # Call, Put
    strike_price: Optional[float] = None
    expiration_date: Optional[str] = None
    contracts: Optional[float] = None
    market_value: float
    source: str

class RiskAssessment(BaseModel):
    """Risk assessment for detected wheel strategies"""
    level: str  # low, medium, high
    factors: List[str]
    max_loss: Optional[float] = None
    assignment_risk: Optional[float] = None  # 0-100 probability

class EnhancedPosition(BaseModel):
    """Enhanced position data with detection metadata"""
    type: str  # stock, call, put
    symbol: str
    quantity: float  # Absolute quantity for display
    position: str  # long, short
    strike_price: Optional[float] = None
    expiration_date: Optional[str] = None
    days_to_expiration: Optional[int] = None
    market_value: float
    raw_quantity: Optional[float] = None  # Preserve signed quantity for logic
    source: str

class PotentialAction(BaseModel):
    """Action recommendation with priority"""
    action: str
    description: str
    priority: str  # high, medium, low

class WheelDetectionResult(BaseModel):
    """Enhanced wheel detection result"""
    ticker: str
    strategy: str  # cash_secured_put, covered_call, full_wheel, naked_stock
    confidence: str  # high, medium, low
    confidence_score: float  # 0-100 numerical score
    description: str
    cash_required: Optional[float] = None  # Required cash for CSP strategies
    cash_validated: Optional[bool] = None  # Whether cash requirements are met
    risk_assessment: RiskAssessment
    positions: List[EnhancedPosition]
    recommendations: Optional[List[str]] = None
    potential_actions: Optional[List[PotentialAction]] = None
    market_context: Optional[MarketContextData] = None

def calculate_days_to_expiration(expiration_date: str) -> int:
    """Calculate days to expiration from date string"""
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

def calculate_confidence_score(
    strategy: str,
    positions: List[EnhancedPosition],
    cash_required: float = 0,
    cash_balance: float = 0,
    market_context: Optional[MarketContextData] = None
) -> tuple[str, float]:
    """Calculate confidence score based on multiple factors"""
    score = 50  # Base score

    # Strategy completeness
    strategy_scores = {
        'full_wheel': 30,
        'covered_call': 20,
        'cash_secured_put': 15,
        'naked_stock': 10
    }
    score += strategy_scores.get(strategy, 0)

    # Cash validation (for CSP strategies)
    if cash_required > 0:
        if cash_balance >= cash_required:
            score += 15  # Sufficient cash
        elif cash_balance >= cash_required * 0.5:
            score += 5   # Partial cash coverage
        else:
            score -= 10  # Insufficient cash

    # Days to expiration factor
    option_positions = [p for p in positions if p.days_to_expiration is not None]
    if option_positions:
        avg_days_to_exp = sum(p.days_to_expiration for p in option_positions) / len(option_positions)
        if avg_days_to_exp > 30:
            score += 10  # Good time horizon
        elif avg_days_to_exp < 7:
            score -= 15  # Close to expiration

    # Market context (if available)
    if market_context:
        if market_context.volatility and market_context.volatility > 0.3:
            score += 5  # Higher volatility = better premiums
        if market_context.market_trend == 'bullish':
            score += 5  # Bullish trend favors wheels

    # Ensure score is within bounds
    score = max(0, min(100, score))

    # Determine confidence level
    if score >= 70:
        confidence = 'high'
    elif score >= 40:
        confidence = 'medium'
    else:
        confidence = 'low'

    return confidence, score

def calculate_cash_required(short_puts: List[EnhancedPosition]) -> float:
    """Calculate cash required for CSP strategy"""
    total = 0.0
    for put in short_puts:
        if put.type == 'put' and put.position == 'short' and put.strike_price:
            contracts = abs(put.raw_quantity or 0) / 100 if put.raw_quantity else put.quantity / 100
            total += contracts * put.strike_price * 100  # 100 shares per contract
    return total

def assess_risk(
    strategy: str,
    positions: List[EnhancedPosition],
    options: Optional[WheelDetectionOptions] = None
) -> RiskAssessment:
    """Assess risk factors for a strategy"""
    factors = []
    level = "medium"
    assignment_risk = 50.0  # Default 50%

    # Check days to expiration
    short_options = [p for p in positions if p.position == 'short' and p.days_to_expiration is not None]
    if short_options:
        min_days_to_exp = min(p.days_to_expiration for p in short_options)
        if min_days_to_exp < 7:
            factors.append('Options expiring within 7 days - high assignment risk')
            assignment_risk = 80.0
            level = 'high'
        elif min_days_to_exp < 21:
            factors.append('Options expiring within 3 weeks - moderate assignment risk')
            assignment_risk = 60.0

    # Risk tolerance adjustment
    if options and options.risk_tolerance:
        if options.risk_tolerance == 'conservative':
            factors.append('Conservative risk profile - consider safer strikes')
            if level == 'medium':
                level = 'high'
        elif options.risk_tolerance == 'aggressive':
            factors.append('Aggressive risk profile - monitor positions closely')

    # Strategy-specific risk factors
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

    return RiskAssessment(
        level=level,
        factors=factors,
        assignment_risk=assignment_risk
    )

def group_positions_by_ticker(positions: List[PositionForDetection]) -> Dict[str, List[PositionForDetection]]:
    """Group positions by their underlying ticker symbol"""
    grouped = {}
    for position in positions:
        ticker = position.underlying_symbol if position.is_option else position.symbol
        if ticker not in grouped:
            grouped[ticker] = []
        grouped[ticker].append(position)
    return grouped

def analyze_ticker_positions(
    ticker: str,
    positions: List[PositionForDetection],
    options: Optional[WheelDetectionOptions] = None
) -> Optional[WheelDetectionResult]:
    """Analyze positions for a specific ticker to detect wheel strategies"""
    
    stock_positions = [p for p in positions if not p.is_option]
    option_positions = [p for p in positions if p.is_option]
    call_options = [p for p in option_positions if p.option_type and p.option_type.upper() == 'CALL']
    put_options = [p for p in option_positions if p.option_type and p.option_type.upper() == 'PUT']

    logger.info("    4ca %s: %d stocks, %d calls, %d puts", ticker, len(stock_positions), len(call_options), len(put_options))

    # Calculate total stock holdings
    total_stock_shares = sum(p.shares for p in stock_positions)

    # Debug contracts for puts
    for p in put_options:
        logger.info("    4cd PUT %s: contracts=%s", p.symbol, p.contracts)

    # Separate long/short options - Use signed values
    short_calls = [p for p in call_options if (p.contracts or 0) < 0]
    short_puts = [p for p in put_options if (p.contracts or 0) < 0]
    
    logger.info("    50d Short puts found: %d", len(short_puts))
    logger.info("    50d Short calls found: %d", len(short_calls))
    logger.info("    50d Stock shares: %s", total_stock_shares)
    
    # Debug detection results
    csp_result = is_cash_secured_put(short_puts)
    cc_result = is_covered_call(total_stock_shares, short_calls)
    logger.info("    3af CSP Detection: %s (short_puts=%d)", csp_result, len(short_puts))
    logger.info("    3af CC Detection: %s (shares=%s, short_calls=%d)", cc_result, total_stock_shares, len(short_calls))

    # Enhanced position formatting
    formatted_positions = []
    for p in positions:
        is_short_position = p.is_option and (p.contracts or 0) < 0 or not p.is_option and p.shares < 0
        raw_quantity = p.contracts or 0 if p.is_option else p.shares
        days_to_expiration = calculate_days_to_expiration(p.expiration_date) if p.expiration_date else None

        enhanced_pos = EnhancedPosition(
            type='call' if p.is_option and p.option_type == 'Call' else 'put' if p.is_option and p.option_type == 'Put' else 'stock',
            symbol=p.symbol,
            quantity=abs(raw_quantity),
            position='short' if is_short_position else 'long',
            strike_price=p.strike_price,
            expiration_date=p.expiration_date,
            days_to_expiration=days_to_expiration,
            market_value=p.market_value,
            raw_quantity=raw_quantity,
            source=p.source
        )
        formatted_positions.append(enhanced_pos)

    # Detection logic
    if is_full_wheel(total_stock_shares, short_calls, short_puts):
        return create_full_wheel_result(ticker, formatted_positions, short_puts, options)
    elif is_covered_call(total_stock_shares, short_calls):
        return create_covered_call_result(ticker, formatted_positions, total_stock_shares, short_calls, options)
    elif is_cash_secured_put(short_puts):
        return create_cash_secured_put_result(ticker, formatted_positions, short_puts, total_stock_shares, options)
    elif is_naked_stock(total_stock_shares, option_positions):
        if total_stock_shares >= 100:
            return create_naked_stock_result(ticker, formatted_positions, total_stock_shares, options)

    return None

def is_full_wheel(stock_shares: float, short_calls: List, short_puts: List) -> bool:
    """Detect full wheel: 100+ shares + short call + evidence of put selling"""
    return stock_shares >= 100 and len(short_calls) > 0 and len(short_puts) > 0

def is_covered_call(stock_shares: float, short_calls: List) -> bool:
    """Detect covered call: 100+ shares + short call(s)"""
    return stock_shares >= 100 and len(short_calls) > 0

def is_cash_secured_put(short_puts: List) -> bool:
    """Detect cash-secured put: short put(s)"""
    return len(short_puts) > 0

def is_naked_stock(stock_shares: float, option_positions: List) -> bool:
    """Detect naked stock: stock holdings with no options"""
    return stock_shares > 0 and len(option_positions) == 0

def create_full_wheel_result(
    ticker: str,
    positions: List[EnhancedPosition],
    short_puts: List,
    options: Optional[WheelDetectionOptions]
) -> WheelDetectionResult:
    """Create enhanced Full Wheel result"""
    cash_required = calculate_cash_required([p for p in positions if p.type == 'put' and p.position == 'short'])
    confidence, score = calculate_confidence_score(
        'full_wheel',
        positions,
        cash_required,
        options.cash_balance if options else 0,
        options.market_data if options else None
    )
    risk_assessment = assess_risk('full_wheel', positions, options)

    return WheelDetectionResult(
        ticker=ticker,
        strategy='full_wheel',
        confidence=confidence,
        confidence_score=score,
        description=f'Complete wheel strategy: {sum(p.quantity for p in positions if p.type == "stock")} shares with covered call and put-selling capability',
        cash_required=cash_required,
        cash_validated=options.cash_balance >= cash_required if options and options.cash_balance else None,
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
        market_context=options.market_data if options else None
    )

def create_covered_call_result(
    ticker: str,
    positions: List[EnhancedPosition],
    total_stock_shares: float,
    short_calls: List,
    options: Optional[WheelDetectionOptions]
) -> WheelDetectionResult:
    """Create enhanced Covered Call result"""
    confidence, score = calculate_confidence_score('covered_call', positions, 0, options.cash_balance if options else 0)
    risk_assessment = assess_risk('covered_call', positions, options)
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
        market_context=options.market_data if options else None
    )

def create_cash_secured_put_result(
    ticker: str,
    positions: List[EnhancedPosition],
    short_puts: List,
    total_stock_shares: float,
    options: Optional[WheelDetectionOptions]
) -> WheelDetectionResult:
    """Create enhanced Cash-Secured Put result"""
    cash_required = calculate_cash_required([p for p in positions if p.type == 'put' and p.position == 'short'])
    confidence, score = calculate_confidence_score('cash_secured_put', positions, cash_required, options.cash_balance if options else 0)
    risk_assessment = assess_risk('cash_secured_put', positions, options)
    short_put_count = len([p for p in positions if p.type == 'put' and p.position == 'short'])

    return WheelDetectionResult(
        ticker=ticker,
        strategy='cash_secured_put',
        confidence=confidence,
        confidence_score=score,
        description=f'Cash-secured put position: {short_put_count} short put(s) {f"with {total_stock_shares} existing shares" if total_stock_shares > 0 else ""}',
        cash_required=cash_required,
        cash_validated=options.cash_balance >= cash_required if options and options.cash_balance else None,
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
        market_context=options.market_data if options else None
    )

def create_naked_stock_result(
    ticker: str,
    positions: List[EnhancedPosition],
    total_stock_shares: float,
    options: Optional[WheelDetectionOptions]
) -> WheelDetectionResult:
    """Create enhanced Naked Stock result"""
    confidence, score = calculate_confidence_score('naked_stock', positions, 0, options.cash_balance if options else 0)
    risk_assessment = assess_risk('naked_stock', positions, options)

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
        market_context=options.market_data if options else None
    )

@router.post("/detect", response_model=List[WheelDetectionResult])
async def detect_wheel_strategies(
    request: WheelDetectionRequest,
    db: Session = Depends(get_db)
):
    """
    Enhanced wheel strategy detection with unified data model integration.
    
    Analyzes positions to identify potential wheel strategies:
    1. Cash-Secured Put: Short put option only
    2. Covered Call: 100+ shares of stock + short call option  
    3. Full Wheel: 100+ shares + short call + potential assignment history
    4. Naked Stock: Stock positions suitable for wheel strategies
    
    Features:
    - Cash balance validation for CSP strategies
    - Numerical confidence scoring (0-100)
    - Risk assessment with assignment probability
    - Days to expiration calculation
    - Priority-based action recommendations
    - Market context integration
    """
    try:
        # Get positions from unified tables
        query = db.query(Position).filter(Position.is_active == True)
        
        if request.account_id:
            query = query.filter(Position.account_id == request.account_id)
            
        positions = query.all()
        
        # Convert to detection format
        detection_positions = []
        for pos in positions:
            # Skip if specific tickers requested and this isn't one of them
            ticker = pos.underlying_symbol or pos.symbol
            if request.specific_tickers and ticker.upper() not in [t.upper() for t in request.specific_tickers]:
                continue
                
            # Calculate contracts for options
            contracts = None
            if pos.asset_type == "OPTION":
                # Net contracts = long - short quantity
                contracts = pos.long_quantity - pos.short_quantity
                
            detection_pos = PositionForDetection(
                id=str(pos.id),
                symbol=pos.symbol,
                shares=pos.long_quantity - pos.short_quantity,  # Net shares
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
        
        # Group by ticker and analyze
        grouped_positions = group_positions_by_ticker(detection_positions)
        results = []
        
        logger.debug("50d DEBUG: Found %d tickers to analyze", len(grouped_positions))
        for ticker in grouped_positions.keys():
            logger.debug("  - %s: %d positions", ticker, len(grouped_positions[ticker]))
        
        for ticker, ticker_positions in grouped_positions.items():
            logger.info("\n3af Analyzing %s with %d positions...", ticker, len(ticker_positions))
            detection_result = analyze_ticker_positions(ticker, ticker_positions, request.options)
            if detection_result:
                logger.info("197 Found opportunity: %s for %s", detection_result.strategy, ticker)
                results.append(detection_result)
            else:
                logger.info("6ab No opportunity found for %s", ticker)
        
        logger.info("\n4ca Total opportunities found: %d", len(results))
        
        # Sort by strategy complexity and confidence score
        strategy_order = {'full_wheel': 0, 'covered_call': 1, 'cash_secured_put': 2, 'naked_stock': 3}
        results.sort(key=lambda x: (strategy_order.get(x.strategy, 4), -x.confidence_score))
        
        return results
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to detect wheel strategies: {str(e)}"
        )


# ===== ADDITIONAL API ENDPOINTS FOR PHASE 2 INTEGRATION =====

@router.get("/{ticker}/data")
def get_wheel_ticker_data(ticker: str, db: Session = Depends(get_db)):
    """
    Get comprehensive wheel data for a specific ticker.
    
    This endpoint provides all wheel-related information for a ticker including:
    - Active wheel cycles
    - Performance metrics
    - Current positions
    - Opportunities
    
    Args:
        ticker: Stock symbol to get wheel data for
        
    Returns:
        WheelTickerData object with comprehensive ticker information
    """
    try:
        ticker = ticker.upper()
        
        # Get all cycles for this ticker
        cycles = db.query(models.WheelCycle).filter(
            models.WheelCycle.ticker == ticker
        ).all()
        
        # Get performance metrics if cycles exist
        total_premium = 0.0
        total_realized_pnl = 0.0
        active_cycles = 0
        
        for cycle in cycles:
            if cycle.status == "active":
                active_cycles += 1
                # Get cycle events to calculate performance
                events = db.query(models.WheelEvent).filter(
                    models.WheelEvent.cycle_id == cycle.id
                ).all()
                
                for event in events:
                    if event.event_type in ["SELL_PUT_OPEN", "SELL_CALL_OPEN"]:
                        if event.premium_received:
                            total_premium += float(event.premium_received)
                    elif event.event_type in ["SELL_PUT_CLOSED", "SELL_CALL_CLOSED"]:
                        if event.premium_paid:
                            total_realized_pnl += float(event.premium_received or 0) - float(event.premium_paid)
        
        # Get current positions for this ticker from unified model
        positions = db.query(Position).filter(
            Position.symbol == ticker
        ).all()
        
        return {
            "ticker": ticker,
            "active_cycles": active_cycles,
            "total_cycles": len(cycles),
            "total_premium_collected": total_premium,
            "realized_pnl": total_realized_pnl,
            "current_positions": [
                {
                    "id": pos.id,
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "market_value": pos.market_value,
                    "position_type": pos.position_type,
                    "option_type": pos.option_type,
                    "strike_price": pos.strike_price,
                    "expiration_date": pos.expiration_date.isoformat() if pos.expiration_date else None
                }
                for pos in positions
            ],
            "cycles": [
                {
                    "id": cycle.id,
                    "cycle_key": cycle.cycle_key,
                    "status": cycle.status,
                    "started_at": cycle.started_at.isoformat() if cycle.started_at else None,
                    "strategy_type": cycle.strategy_type,
                    "notes": cycle.notes
                }
                for cycle in cycles
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get wheel data for ticker {ticker}: {str(e)}"
        )


@router.post("/events/", response_model=schemas.WheelEventRead)
def create_wheel_event_alt(payload: schemas.WheelEventCreate, db: Session = Depends(get_db)):
    """
    Alternative endpoint for creating wheel events (matches frontend expectation).
    
    This endpoint provides the same functionality as POST /wheels/wheel-events
    but with a slightly different URL pattern that matches frontend calls.
    
    Input: WheelEventCreate
    Returns: WheelEventRead
    Errors: 404 if cycle not found
    """
    return crud.create_wheel_event(db, payload)


@router.get("/performance", response_model=Dict[str, Any])
def get_wheel_performance(
    ticker: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get performance analytics for wheels.
    
    This endpoint provides comprehensive performance metrics including:
    - Total P&L across all wheels
    - Performance by ticker
    - Time-based performance analysis
    - Success rates and metrics
    
    Args:
        ticker: Optional ticker to filter by
        start_date: Optional start date for filtering (YYYY-MM-DD)
        end_date: Optional end date for filtering (YYYY-MM-DD)
        
    Returns:
        Performance analytics object
    """
    try:
        # Build base query
        query = db.query(models.WheelCycle)
        
        # Filter by ticker if provided
        if ticker:
            query = query.filter(models.WheelCycle.ticker == ticker.upper())
        
        # Date filtering would go here if we had date fields on cycles
        cycles = query.all()
        
        # Calculate performance metrics
        total_cycles = len(cycles)
        active_cycles = len([c for c in cycles if c.status == "Open"])
        completed_cycles = len([c for c in cycles if c.status == "Closed"])
        
        # For now, return basic metrics without event-based calculations
        # since the WheelEvent model is incomplete
        tickers_performance = {}
        
        for cycle in cycles:
            if cycle.ticker not in tickers_performance:
                tickers_performance[cycle.ticker] = {
                    "cycles": 0,
                    "active": 0,
                    "completed": 0
                }
            
            tickers_performance[cycle.ticker]["cycles"] += 1
            if cycle.status == "Open":
                tickers_performance[cycle.ticker]["active"] += 1
            elif cycle.status == "Closed":
                tickers_performance[cycle.ticker]["completed"] += 1
        
        return {
            "summary": {
                "total_cycles": total_cycles,
                "active_cycles": active_cycles,
                "completed_cycles": completed_cycles,
                "total_premium_collected": 0.0,  # TODO: Implement when WheelEvent model is complete
                "total_realized_pnl": 0.0,  # TODO: Implement when WheelEvent model is complete
                "success_rate": completed_cycles / total_cycles if total_cycles > 0 else 0
            },
            "by_ticker": tickers_performance,
            "filters": {
                "ticker": ticker,
                "start_date": start_date,
                "end_date": end_date
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get performance analytics: {str(e)}"
        )


@router.put("/cycles/{cycle_id}/status")
def update_wheel_cycle_status(
    cycle_id: int,
    status: str,
    db: Session = Depends(get_db)
):
    """
    Update the status of a wheel cycle.
    
    This endpoint allows for manual status changes of wheel cycles
    which is important for management functionality.
    
    Args:
        cycle_id: ID of the cycle to update
        status: New status (active, completed, closed, etc.)
        
    Returns:
        Updated cycle information
    """
    try:
        cycle = db.query(models.WheelCycle).filter(
            models.WheelCycle.id == cycle_id
        ).first()
        
        if not cycle:
            raise HTTPException(status_code=404, detail="Wheel cycle not found")
        
        # Expanded valid statuses for comprehensive status tracking
        valid_statuses = ["pending", "active", "monitoring", "assigned", "rolling", "covered", "expired", "closed", "paused"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        
        # Store previous status for history
        previous_status = cycle.status
        
        # Update status and metadata
        cycle.status = status
        cycle.last_status_update = datetime.now(UTC)
        db.commit()
        db.refresh(cycle)
        return {
            "id": cycle.id,
            "cycle_key": cycle.cycle_key,
            "ticker": cycle.ticker,
            "status": cycle.status,
            "previous_status": previous_status,
            "last_status_update": cycle.last_status_update.isoformat() if cycle.last_status_update else None,
            "started_at": cycle.started_at.isoformat() if cycle.started_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating wheel cycle status: {str(e)}")


@router.get("/cycles/{cycle_id}/status/history")
def get_wheel_cycle_status_history(
    cycle_id: int,
    db: Session = Depends(get_db)
):
    """
    Get the complete status history for a wheel cycle.
    
    Returns a chronological list of all status changes with metadata.
    
    Args:
        cycle_id: ID of the cycle
        
    Returns:
        List of status history entries
    """
    try:
        # Check if cycle exists
        cycle = db.query(models.WheelCycle).filter(
            models.WheelCycle.id == cycle_id
        ).first()
        
        if not cycle:
            raise HTTPException(status_code=404, detail="Wheel cycle not found")
        
        # Get status history (if table exists, otherwise return basic info)
        try:
            history = db.query(models.WheelStatusHistory).filter(
                models.WheelStatusHistory.cycle_id == cycle_id
            ).order_by(models.WheelStatusHistory.timestamp.desc()).all()
            
            history_data = []
            for entry in history:
                history_data.append({
                    "id": entry.id,
                    "cycle_id": entry.cycle_id,
                    "previous_status": entry.previous_status,
                    "new_status": entry.new_status,
                    "trigger_event": entry.trigger_event,
                    "automated": entry.automated,
                    "metadata": entry.event_metadata,
                    "updated_by": entry.updated_by,
                    "timestamp": entry.timestamp.isoformat() if entry.timestamp else None
                })
                
        except Exception as e:
            # Fallback: return current status as single history entry
            history_data = [{
                "id": 1,
                "cycle_id": cycle_id,
                "previous_status": None,
                "new_status": cycle.status,
                "trigger_event": "initial",
                "automated": False,
                "metadata": "{}",
                "updated_by": "system",
                "timestamp": cycle.started_at.isoformat() if cycle.started_at else None
            }]
        
        return {
            "cycle_id": cycle_id,
            "current_status": cycle.status,
            "history": history_data,
            "total_entries": len(history_data)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching status history: {str(e)}")


@router.post("/cycles/{cycle_id}/status/auto-detect")
def auto_detect_wheel_status(
    cycle_id: int,
    db: Session = Depends(get_db)
):
    """
    Automatically detect the appropriate status for a wheel cycle based on current positions.
    
    This endpoint analyzes current positions and market conditions to recommend
    the most appropriate status for the wheel cycle.
    
    Args:
        cycle_id: ID of the cycle to analyze
        
    Returns:
        Recommended status with confidence level and reasoning
    """
    try:
        cycle = db.query(models.WheelCycle).filter(
            models.WheelCycle.id == cycle_id
        ).first()
        
        if not cycle:
            raise HTTPException(status_code=404, detail="Wheel cycle not found")
        
        # Simple auto-detection logic (can be enhanced)
        current_status = cycle.status
        recommended_status = current_status
        confidence = 0.5
        trigger_events = []
        recommendations = []
        
        # Basic status detection based on time and current status
        if current_status == "pending":
            recommended_status = "active"
            confidence = 0.8
            trigger_events.append("time_based_activation")
            recommendations.append("Activate wheel strategy")
        
        elif current_status == "active":
            # Check if should be monitoring (near expiration logic would go here)
            recommended_status = "monitoring"
            confidence = 0.6
            trigger_events.append("time_based_monitoring")
            recommendations.append("Monitor for assignment risk")
        
        return {
            "cycle_id": cycle_id,
            "current_status": current_status,
            "recommended_status": recommended_status,
            "confidence": confidence,
            "trigger_events": trigger_events,
            "recommendations": recommendations,
            "analysis_timestamp": datetime.now(UTC).isoformat(),
            "position_analysis": {
                "total_positions": 0,  # Would be calculated from actual positions
                "has_stock_positions": False,
                "has_option_positions": False,
                "options_near_expiration": False
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in auto-detection: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update cycle status: {str(e)}"
        )