"""
Schwab API Router for FastAPI Backend
Handles Schwab OAuth and API calls server-side
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
import httpx
import os
from typing import Dict, Any, Optional
import base64
from urllib.parse import urlencode
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from ..dependencies import get_current_user
from ..database import get_db
from .. import models
from ..models import User, SchwabAccount, SchwabPosition
from ..services.mock_data_service import MockDataService
# from ..services.schwab_sync_service import SchwabSyncService  # TODO: Enable when SchwabClient is implemented

router = APIRouter(prefix="/schwab", tags=["schwab"])
logger = logging.getLogger(__name__)

# Schwab API Configuration
SCHWAB_CONFIG = {
    "auth_url": "https://api.schwabapi.com/v1/oauth/authorize",
    "token_url": "https://api.schwabapi.com/v1/oauth/token",
    "accounts_url": "https://api.schwabapi.com/trader/v1/accounts",
    "account_numbers_url": "https://api.schwabapi.com/trader/v1/accounts/accountNumbers",
    "client_id": os.getenv("SCHWAB_CLIENT_ID", ""),
    "client_secret": os.getenv("SCHWAB_CLIENT_SECRET", ""),
    "redirect_uri": os.getenv("SCHWAB_REDIRECT_URI", "https://allocraft-backend.onrender.com/schwab/callback")
}

@router.get("/auth-url")
async def get_auth_url(
    current_user: models.User = Depends(get_current_user)
):
    """Generate Schwab OAuth authorization URL with user state"""
    if not SCHWAB_CONFIG["client_id"]:
        raise HTTPException(status_code=500, detail="Schwab Client ID not configured")
    
    # Use user ID as state parameter to maintain session
    state = str(current_user.id)
    
    params = {
        "response_type": "code",
        "client_id": SCHWAB_CONFIG["client_id"],
        "redirect_uri": SCHWAB_CONFIG["redirect_uri"],
        "scope": "AccountAccess",
        "state": state
    }
    
    auth_url = f"{SCHWAB_CONFIG['auth_url']}?{urlencode(params)}"
    return {"auth_url": auth_url}

@router.get("/callback")
async def oauth_callback(
    code: Optional[str] = None, 
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Handle OAuth callback from Schwab"""
    if error:
        logger.error(f"OAuth error: {error}")
        frontend_url = os.getenv("FRONTEND_URL", "https://allocraft.app")
        return RedirectResponse(
            url=f"{frontend_url}/stocks?error={error}",
            status_code=302
        )
    
    if not code:
        frontend_url = os.getenv("FRONTEND_URL", "https://allocraft.app")
        return RedirectResponse(
            url=f"{frontend_url}/stocks?error=no_authorization_code",
            status_code=302
        )
    
    if not state:
        frontend_url = os.getenv("FRONTEND_URL", "https://allocraft.app")
        return RedirectResponse(
            url=f"{frontend_url}/stocks?error=no_state_parameter",
            status_code=302
        )
    
    try:
        # Get user by ID from state parameter
        user_id = int(state)
        user = db.query(models.User).filter(models.User.id == user_id).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Exchange code for tokens
        tokens = await exchange_code_for_tokens(code)
        
        # Store tokens with the user
        await store_user_schwab_tokens(db, user, tokens)
        
        # Redirect back to frontend with success
        frontend_url = os.getenv("FRONTEND_URL", "https://allocraft.app")
        return RedirectResponse(
            url=f"{frontend_url}/stocks?schwab_connected=true",
            status_code=302
        )
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        frontend_url = os.getenv("FRONTEND_URL", "https://allocraft.app")
        return RedirectResponse(
            url=f"{frontend_url}/stocks?error={str(e)}",
            status_code=302
        )

async def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    """Exchange authorization code for access tokens"""
    auth_header = base64.b64encode(
        f"{SCHWAB_CONFIG['client_id']}:{SCHWAB_CONFIG['client_secret']}".encode()
    ).decode()
    
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SCHWAB_CONFIG["redirect_uri"]
    }
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_header}"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            SCHWAB_CONFIG["token_url"],
            data=data,
            headers=headers
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Token exchange failed: {response.text}"
            )
        
        return response.json()

async def store_user_schwab_tokens(db: Session, user: models.User, tokens: Dict[str, Any]):
    """Store Schwab tokens with the user in the database"""
    user.schwab_access_token = tokens.get("access_token")
    user.schwab_refresh_token = tokens.get("refresh_token")
    
    # Calculate expiration time (Schwab tokens typically expire in 30 minutes)
    expires_in = tokens.get("expires_in", 1800)  # Default 30 minutes
    user.schwab_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    user.schwab_account_linked = True  # Mark account as linked
    
    db.commit()
    db.refresh(user)
    logger.info(f"Stored Schwab tokens for user {user.id}")

async def get_user_schwab_token(db: Session, user: models.User) -> Optional[str]:
    """Get valid Schwab access token for user, refreshing if needed"""
    # Check if we have a valid token
    if (user.schwab_access_token and 
        user.schwab_token_expires_at and 
        user.schwab_token_expires_at > datetime.utcnow()):
        return user.schwab_access_token
    
    # Try to refresh the token if we have a refresh token
    if user.schwab_refresh_token:
        try:
            tokens = await refresh_schwab_token(user.schwab_refresh_token)
            await store_user_schwab_tokens(db, user, tokens)
            return tokens.get("access_token")
        except Exception as e:
            logger.error(f"Failed to refresh Schwab token for user {user.id}: {e}")
            # Clear invalid tokens
            user.schwab_access_token = None
            user.schwab_refresh_token = None
            user.schwab_token_expires_at = None
            db.commit()
    
    return None

async def refresh_schwab_token(refresh_token: str) -> Dict[str, Any]:
    """Refresh Schwab access token using refresh token"""
    auth_header = base64.b64encode(
        f"{SCHWAB_CONFIG['client_id']}:{SCHWAB_CONFIG['client_secret']}".encode()
    ).decode()
    
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_header}"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            SCHWAB_CONFIG["token_url"],
            data=data,
            headers=headers
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Token refresh failed: {response.text}"
            )
        
        return response.json()

@router.get("/accounts")
async def get_accounts(
    refresh: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get account summaries from database with optional refresh"""
    try:
        if refresh:
            # TODO: Implement sync functionality when SchwabClient is available
            logger.warning("Refresh requested but sync service not implemented yet")
        
        # Try to get from database first
        stored_accounts = db.query(SchwabAccount).all()
        
        if stored_accounts:
            return [
                {
                    "accountNumber": account.account_number,
                    "hashValue": account.hash_value
                }
                for account in stored_accounts
            ]
        
        # Fallback to API if no stored accounts
        # schwab_client = SchwabClient()  # TODO: Implement SchwabClient
        # return await schwab_client.get_account_summaries()
        return []  # Temporary: return empty list until SchwabClient is implemented
        
    except Exception as e:
        logger.error(f"Error getting accounts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/accounts/{account_hash}")
async def get_account_by_hash(
    account_hash: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get full account details using account hash"""
    access_token = await get_user_schwab_token(db, current_user)
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated with Schwab")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    url = f"{SCHWAB_CONFIG['accounts_url']}/{account_hash}?fields=positions"
    
    logger.info(f"Fetching account details for hash {account_hash}")
    logger.info(f"Full URL with positions field: {url}")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        
        logger.info(f"Account details response status: {response.status_code}")
        logger.info(f"Account details response content: {response.text}")
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to fetch account details: {response.text}"
            )
        
        return response.json()

@router.get("/accounts/{account_id}/positions")
async def get_positions(
    account_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get positions for a specific account"""
    access_token = await get_user_schwab_token(db, current_user)
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated with Schwab")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    url = f"{SCHWAB_CONFIG['accounts_url']}/{account_id}?fields=positions"
    
    # Add detailed logging
    logger.info(f"Fetching positions for account {account_id}")
    logger.info(f"Full URL: {url}")
    logger.info(f"Headers: {headers}")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response content: {response.text}")
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to fetch positions: {response.text}"
            )
        
        return response.json()

@router.get("/accounts-with-positions")
async def get_accounts_with_positions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get user's Schwab accounts with positions included"""
    access_token = await get_user_schwab_token(db, current_user)
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated with Schwab")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    # Try to get accounts with positions field
    url = f"{SCHWAB_CONFIG['accounts_url']}?fields=positions"
    
    logger.info(f"Fetching accounts with positions: {url}")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        
        logger.info(f"Accounts with positions response status: {response.status_code}")
        logger.info(f"Accounts with positions response: {response.text}")
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to fetch accounts with positions: {response.text}"
            )
        
        return response.json()

@router.post("/refresh-token")
async def refresh_access_token(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Refresh access token using refresh token"""
    if not current_user.schwab_refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token available")
    
    try:
        tokens = await refresh_schwab_token(current_user.schwab_refresh_token)
        await store_user_schwab_tokens(db, current_user, tokens)
        return {"message": "Token refreshed successfully"}
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(status_code=400, detail=f"Token refresh failed: {str(e)}")

@router.delete("/disconnect")
async def disconnect_schwab(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Disconnect Schwab account by clearing stored tokens"""
    current_user.schwab_access_token = None
    current_user.schwab_refresh_token = None
    current_user.schwab_token_expires_at = None
    db.commit()
    return {"message": "Schwab account disconnected successfully"}

@router.get("/status")
async def get_schwab_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get Schwab connection status for the current user"""
    has_valid_token = (
        current_user.schwab_access_token and 
        current_user.schwab_token_expires_at and 
        current_user.schwab_token_expires_at > datetime.utcnow()
    )
    
    return {
        "connected": has_valid_token or bool(current_user.schwab_refresh_token),
        "has_access_token": bool(current_user.schwab_access_token),
        "has_refresh_token": bool(current_user.schwab_refresh_token),
        "token_expires_at": current_user.schwab_token_expires_at.isoformat() if current_user.schwab_token_expires_at else None
    }

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "schwab_config": {
            "client_id_configured": bool(SCHWAB_CONFIG["client_id"]),
            "client_secret_configured": bool(SCHWAB_CONFIG["client_secret"]),
            "redirect_uri": SCHWAB_CONFIG["redirect_uri"]
        }
    }

@router.get("/positions")
async def get_stored_positions(
    fresh: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get positions from database with optional fresh sync"""
    try:
        # Check if we should fetch fresh data from Schwab
        if fresh or not db.query(SchwabAccount).first():
            logger.info("Fetching fresh data from Schwab API and storing in database")
            fresh_data = await fetch_fresh_positions_from_schwab(db, current_user)
            await store_schwab_data_in_database(db, fresh_data, current_user)
            return fresh_data
        
        # Get stored positions from database
        accounts = db.query(SchwabAccount).all()
        
        if not accounts:
            logger.info("No stored accounts found, fetching from Schwab API")
            fresh_data = await fetch_fresh_positions_from_schwab(db, current_user)
            await store_schwab_data_in_database(db, fresh_data, current_user)
            return fresh_data
        
        result = []
        for account in accounts:
            active_positions = db.query(SchwabPosition).filter(
                and_(
                    SchwabPosition.account_id == account.id,
                    SchwabPosition.is_active == True
                )
            ).all()
            
            # Transform to expected format
            account_data = {
                "accountNumber": account.account_number,
                "accountType": account.account_type,
                "lastSynced": account.last_synced.isoformat() if account.last_synced else None,
                "totalValue": account.total_value,
                "positions": [transform_position_to_frontend(pos) for pos in active_positions]
            }
            result.append(account_data)
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting stored positions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync")
async def sync_positions(
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manually trigger position synchronization"""
    try:
        logger.info(f"Manual sync requested by user {current_user.id}, force={force}")
        
        # Fetch fresh data from Schwab
        fresh_data = await fetch_fresh_positions_from_schwab(db, current_user)
        
        # Store the fresh data in database
        await store_schwab_data_in_database(db, fresh_data, current_user)
        
        return {
            "message": "Synchronization completed successfully",
            "result": {
                "status": "success", 
                "force": force,
                "accounts_synced": len(fresh_data),
                "positions_total": sum(len(account.get("positions", [])) for account in fresh_data),
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error during manual sync: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sync-status")
async def get_sync_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get synchronization status for all accounts"""
    try:
        accounts = db.query(SchwabAccount).all()
        
        status = []
        for account in accounts:
            last_sync = account.last_synced
            is_recent = False
            
            if last_sync:
                threshold = datetime.utcnow() - timedelta(minutes=5)
                is_recent = last_sync > threshold
            
            position_count = db.query(SchwabPosition).filter(
                and_(
                    SchwabPosition.account_id == account.id,
                    SchwabPosition.is_active == True
                )
            ).count()
            
            status.append({
                "accountNumber": account.account_number,
                "lastSynced": last_sync.isoformat() if last_sync else None,
                "isRecentlySynced": is_recent,
                "positionCount": position_count,
                "totalValue": account.total_value
            })
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting sync status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def transform_position_to_frontend(position: SchwabPosition) -> Dict[str, Any]:
    """Transform database position to frontend format"""
    
    # Determine if it's a long or short position
    net_quantity = (position.long_quantity or 0.0) - (position.short_quantity or 0.0)
    is_short = net_quantity < 0
    
    result = {
        "symbol": position.symbol,
        "quantity": abs(net_quantity),
        "marketValue": position.market_value or 0.0,
        "averagePrice": position.average_long_price if not is_short else position.average_short_price,
        "profitLoss": (position.long_open_profit_loss or 0.0) + (position.short_open_profit_loss or 0.0),
        "profitLossPercentage": position.current_day_profit_loss_percentage or 0.0,
        "assetType": position.asset_type,
        "lastUpdated": position.last_updated.isoformat() if position.last_updated else None,
        "accountNumber": position.account.account_number,
        "source": "schwab"
    }
    
    # Add option-specific fields
    if position.asset_type == "OPTION":
        result.update({
            "isOption": True,
            "underlyingSymbol": position.underlying_symbol,
            "optionType": position.option_type,
            "strikePrice": position.strike_price,
            "expirationDate": position.expiration_date.isoformat() if position.expiration_date else None,
            "contracts": abs(net_quantity),
            "isShort": is_short
        })
    else:
        result.update({
            "isOption": False,
            "shares": abs(net_quantity),
            "isShort": is_short
        })
    
    return result

async def fetch_fresh_positions_from_schwab(db: Session, current_user: User):
    """Fetch fresh positions directly from Schwab API and optionally store them"""
    access_token = await get_user_schwab_token(db, current_user)
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated with Schwab")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    try:
        # First get account summaries
        async with httpx.AsyncClient() as client:
            accounts_response = await client.get(
                f"{SCHWAB_CONFIG['account_numbers_url']}", 
                headers=headers
            )
            
            if accounts_response.status_code != 200:
                raise HTTPException(
                    status_code=accounts_response.status_code,
                    detail=f"Failed to fetch accounts: {accounts_response.text}"
                )
            
            accounts_data = accounts_response.json()
            result = []
            
            # For each account, get positions
            for account in accounts_data:
                account_hash = account.get("hashValue")
                account_number = account.get("accountNumber")
                
                if account_hash:
                    positions_url = f"{SCHWAB_CONFIG['accounts_url']}/{account_hash}?fields=positions"
                    
                    positions_response = await client.get(positions_url, headers=headers)
                    
                    if positions_response.status_code == 200:
                        account_data = positions_response.json()
                        
                        # Extract positions from the response
                        positions = []
                        securities_account = account_data.get("securitiesAccount", {})
                        raw_positions = securities_account.get("positions", [])
                        
                        for pos in raw_positions:
                            # Transform Schwab position to our format
                            instrument = pos.get("instrument", {})
                            position_data = {
                                "symbol": instrument.get("symbol", ""),
                                "description": instrument.get("description", ""),
                                "quantity": pos.get("longQuantity", 0) - pos.get("shortQuantity", 0),
                                "marketValue": pos.get("marketValue", 0),
                                "averagePrice": pos.get("averagePrice", 0),
                                "unrealizedPL": pos.get("currentDayProfitLoss", 0),
                                "assetType": instrument.get("assetType", "EQUITY"),
                                "isOption": instrument.get("assetType") == "OPTION"
                            }
                            
                            # Add option-specific fields if it's an option
                            if position_data["isOption"]:
                                option_details = instrument.get("optionDeliverables", [{}])
                                if option_details:
                                    position_data.update({
                                        "underlyingSymbol": option_details[0].get("symbol", ""),
                                        "optionType": instrument.get("putCall", ""),
                                        "strikePrice": instrument.get("strikePrice", 0),
                                        "expirationDate": instrument.get("expirationDate", ""),
                                        "contracts": abs(position_data["quantity"]),
                                        "isShort": position_data["quantity"] < 0
                                    })
                            else:
                                position_data.update({
                                    "shares": abs(position_data["quantity"]),
                                    "isShort": position_data["quantity"] < 0
                                })
                            
                            positions.append(position_data)
                        
                        account_result = {
                            "accountNumber": account_number,
                            "accountType": securities_account.get("type", ""),
                            "lastSynced": datetime.utcnow().isoformat(),
                            "totalValue": securities_account.get("currentBalances", {}).get("liquidationValue", 0),
                            "positions": positions
                        }
                        result.append(account_result)
            
            return result
            
    except Exception as e:
        logger.error(f"Error fetching fresh positions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch positions from Schwab: {str(e)}")
    return result


async def store_schwab_data_in_database(db: Session, accounts_data: list, current_user: User):
    """Store Schwab accounts and positions data in the database"""
    try:
        for account_data in accounts_data:
            account_number = account_data.get("accountNumber")
            if not account_number:
                continue
                
            # Check if account already exists
            existing_account = db.query(SchwabAccount).filter(
                SchwabAccount.account_number == account_number
            ).first()
            
            if not existing_account:
                # Create new account
                new_account = SchwabAccount(
                    account_number=account_number,
                    hash_value=account_number,  # We'll use account_number as hash for now
                    account_type=account_data.get("accountType", ""),
                    total_value=account_data.get("totalValue", 0),
                    last_synced=datetime.utcnow()
                )
                db.add(new_account)
                db.flush()  # Get the ID
                account_id = new_account.id
            else:
                # Update existing account
                existing_account.total_value = account_data.get("totalValue", 0)
                existing_account.last_synced = datetime.utcnow()
                account_id = existing_account.id
            
            # Mark all existing positions as inactive first
            db.query(SchwabPosition).filter(
                SchwabPosition.account_id == account_id
            ).update({"is_active": False})
            
            # Add/update positions
            positions = account_data.get("positions", [])
            for position_data in positions:
                symbol = position_data.get("symbol")
                if not symbol:
                    continue
                    
                # Check if position already exists
                existing_position = db.query(SchwabPosition).filter(
                    SchwabPosition.account_id == account_id,
                    SchwabPosition.symbol == symbol,
                    SchwabPosition.asset_type == position_data.get("assetType", "EQUITY")
                ).first()
                
                if existing_position:
                    # Update existing position
                    existing_position.long_quantity = max(0, position_data.get("quantity", 0))
                    existing_position.short_quantity = max(0, -position_data.get("quantity", 0))
                    existing_position.market_value = position_data.get("marketValue", 0)
                    existing_position.average_price = position_data.get("averagePrice", 0)
                    existing_position.current_day_profit_loss = position_data.get("unrealizedPL", 0)
                    existing_position.is_active = True
                    existing_position.last_updated = datetime.utcnow()
                    
                    # Update option-specific fields
                    if position_data.get("isOption"):
                        existing_position.underlying_symbol = position_data.get("underlyingSymbol", "")
                        existing_position.option_type = position_data.get("optionType", "")
                        existing_position.strike_price = position_data.get("strikePrice", 0)
                        if position_data.get("expirationDate"):
                            existing_position.expiration_date = datetime.fromisoformat(position_data["expirationDate"].replace("Z", "+00:00"))
                else:
                    # Create new position
                    new_position = SchwabPosition(
                        account_id=account_id,
                        symbol=symbol,
                        asset_type=position_data.get("assetType", "EQUITY"),
                        long_quantity=max(0, position_data.get("quantity", 0)),
                        short_quantity=max(0, -position_data.get("quantity", 0)),
                        market_value=position_data.get("marketValue", 0),
                        average_price=position_data.get("averagePrice", 0),
                        current_day_profit_loss=position_data.get("unrealizedPL", 0),
                        is_active=True,
                        last_updated=datetime.utcnow()
                    )
                    
                    # Add option-specific fields
                    if position_data.get("isOption"):
                        new_position.underlying_symbol = position_data.get("underlyingSymbol", "")
                        new_position.option_type = position_data.get("optionType", "")
                        new_position.strike_price = position_data.get("strikePrice", 0)
                        if position_data.get("expirationDate"):
                            new_position.expiration_date = datetime.fromisoformat(position_data["expirationDate"].replace("Z", "+00:00"))
                    
                    db.add(new_position)
            
        db.commit()
        logger.info(f"Successfully stored Schwab data for {len(accounts_data)} accounts")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error storing Schwab data: {str(e)}")
        raise

# ========================================
# MOCK DATA ENDPOINTS FOR DEVELOPMENT
# ========================================

@router.get("/mock/positions")
async def get_mock_positions():
    """Get mock positions for development (matches exact Schwab API structure)"""
    logger.info("Serving mock positions for development")
    return MockDataService.generate_mock_accounts_with_positions()

@router.post("/mock/sync")
async def mock_sync_positions():
    """Mock synchronization endpoint for development"""
    logger.info("Mock sync requested for development")
    return MockDataService.generate_mock_sync_response()

@router.get("/mock/sync-status")
async def get_mock_sync_status():
    """Get mock sync status for development"""
    return MockDataService.generate_mock_sync_status()

@router.post("/mock/load-data")
async def load_mock_data(
    db: Session = Depends(get_db)
):
    """Load mock data into database for development (creates mock accounts and positions)"""
    try:
        logger.info("🎭 MOCK DATA ENDPOINT CALLED - Loading mock data for development")
        print("🎭 MOCK DATA ENDPOINT CALLED - Loading mock data for development")
        
        # For development, we'll create or use a mock user
        mock_user = db.query(User).filter(User.email == "mock@dev.local").first()
        if not mock_user:
            mock_user = User(
                username="mock_dev_user",
                email="mock@dev.local",
                hashed_password="mock_password_hash"
            )
            db.add(mock_user)
            db.commit()
            db.refresh(mock_user)
        
        # Get mock data
        mock_accounts = MockDataService.generate_mock_accounts_with_positions()
        
        # Clear existing mock data for this user (clear ALL mock accounts, not just those matching pattern)
        existing_accounts = db.query(SchwabAccount).filter(
            SchwabAccount.account_number.like("MOCK_%")
        ).all()
        
        for account in existing_accounts:
            # Delete positions first
            db.query(SchwabPosition).filter(
                SchwabPosition.account_id == account.id
            ).delete()
            # Delete account
            db.delete(account)
        
        # Commit the deletions before adding new data
        db.commit()
        
        # Create mock accounts and positions
        created_accounts = 0
        created_positions = 0
        
        for account_data in mock_accounts:
            # Create mock account
            mock_account = SchwabAccount(
                account_number=f"MOCK_{account_data['accountNumber']}",
                hash_value=f"mock_hash_{account_data['accountNumber']}",
                account_type=account_data["accountType"],
                is_day_trader=False,
                last_synced=datetime.utcnow(),
                cash_balance=25000.0,
                buying_power=50000.0,
                total_value=account_data["totalValue"],
                day_trading_buying_power=0.0
            )
            db.add(mock_account)
            db.flush()  # Get the ID
            created_accounts += 1
            
            # Create positions for this account
            for pos_data in account_data["positions"]:
                mock_position = SchwabPosition(
                    account_id=mock_account.id,
                    symbol=pos_data["symbol"],
                    instrument_cusip=f"mock_cusip_{pos_data['symbol']}",
                    asset_type=pos_data["assetType"],
                    long_quantity=pos_data["quantity"] if not pos_data.get("isShort", False) else 0.0,
                    short_quantity=pos_data["quantity"] if pos_data.get("isShort", False) else 0.0,
                    settled_long_quantity=pos_data["quantity"] if not pos_data.get("isShort", False) else 0.0,
                    settled_short_quantity=pos_data["quantity"] if pos_data.get("isShort", False) else 0.0,
                    market_value=pos_data["marketValue"],
                    average_price=pos_data["averagePrice"],
                    average_long_price=pos_data["averagePrice"] if not pos_data.get("isShort", False) else 0.0,
                    average_short_price=pos_data["averagePrice"] if pos_data.get("isShort", False) else 0.0,
                    current_day_profit_loss=pos_data["profitLoss"],
                    current_day_profit_loss_percentage=pos_data["profitLossPercentage"],
                    long_open_profit_loss=pos_data["profitLoss"] if not pos_data.get("isShort", False) else 0.0,
                    short_open_profit_loss=pos_data["profitLoss"] if pos_data.get("isShort", False) else 0.0,
                    last_updated=datetime.utcnow(),
                    is_active=True
                )
                
                # Add option-specific fields
                if pos_data.get("isOption"):
                    mock_position.underlying_symbol = pos_data.get("underlyingSymbol", "")
                    mock_position.option_type = pos_data.get("optionType", "")
                    mock_position.strike_price = pos_data.get("strikePrice", 0.0)
                    if pos_data.get("expirationDate"):
                        mock_position.expiration_date = datetime.fromisoformat(
                            pos_data["expirationDate"].replace("Z", "+00:00")
                        )
                
                db.add(mock_position)
                created_positions += 1
        
        db.commit()
        
        return {
            "message": "Mock data loaded successfully",
            "result": {
                "accounts_created": created_accounts,
                "positions_created": created_positions,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error loading mock data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to load mock data: {str(e)}")


@router.get("/export/positions")
async def export_positions(
    db: Session = Depends(get_db)
):
    """
    Export all Schwab accounts and positions to a JSON file format.
    Use this on production to export real Schwab data for development use.
    No authentication required - exports all accounts/positions.
    """
    try:
        # Get all Schwab accounts (all users)
        accounts = db.query(SchwabAccount).all()
        
        if not accounts:
            raise HTTPException(status_code=404, detail="No Schwab accounts found")
        
        export_data = {
            "export_info": {
                "export_timestamp": datetime.utcnow().isoformat(),
                "total_accounts": len(accounts)
            },
            "accounts": []
        }
        
        total_positions = 0
        
        for account in accounts:
            # Get all positions for this account
            positions = db.query(SchwabPosition).filter(
                SchwabPosition.account_id == account.id
            ).all()
            
            account_data = {
                "account_number": account.account_number,
                "account_type": account.account_type,
                "hash_value": account.hash_value,
                "is_day_trader": account.is_day_trader,
                "is_closing_only_restricted": account.is_closing_only_restricted,
                "buying_power": float(account.buying_power) if account.buying_power else 0.0,
                "cash_balance": float(account.cash_balance) if account.cash_balance else 0.0,
                "total_positions": len(positions),
                "positions": []
            }
            
            for position in positions:
                position_data = {
                    "symbol": position.symbol,
                    "quantity": float(position.quantity),
                    "market_value": float(position.market_value) if position.market_value else 0.0,
                    "average_price": float(position.average_price) if position.average_price else 0.0,
                    "day_change": float(position.day_change) if position.day_change else 0.0,
                    "day_change_percent": float(position.day_change_percent) if position.day_change_percent else 0.0,
                    "position_type": position.position_type,
                    "asset_type": position.asset_type,
                    "schwab_position_id": position.schwab_position_id,
                    "last_updated": position.last_updated.isoformat() if position.last_updated else None,
                    # Option-specific fields
                    "underlying_symbol": position.underlying_symbol,
                    "option_type": position.option_type,
                    "strike_price": float(position.strike_price) if position.strike_price else None,
                    "expiration_date": position.expiration_date.isoformat() if position.expiration_date else None
                }
                
                account_data["positions"].append(position_data)
                total_positions += 1
            
            export_data["accounts"].append(account_data)
        
        export_data["export_info"]["total_positions"] = total_positions
        
        logger.info(f"Exported {len(accounts)} accounts with {total_positions} positions")
        
        return export_data
        
    except Exception as e:
        logger.error(f"Error exporting positions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to export positions: {str(e)}")


@router.post("/import/positions")
async def import_positions(
    import_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Import positions from an exported JSON file.
    Use this on development to import real Schwab data exported from production.
    """
    try:
        if "accounts" not in import_data or "export_info" not in import_data:
            raise HTTPException(status_code=400, detail="Invalid import data format")
        
        # Clear existing positions for this user to avoid duplicates
        existing_accounts = db.query(SchwabAccount).filter(
            SchwabAccount.user_id == current_user.id
        ).all()
        
        for account in existing_accounts:
            # Delete positions first (foreign key constraint)
            db.query(SchwabPosition).filter(
                SchwabPosition.account_id == account.id
            ).delete()
            # Then delete the account
            db.delete(account)
        
        db.commit()
        
        imported_accounts = 0
        imported_positions = 0
        
        # Import accounts and positions
        for account_data in import_data["accounts"]:
            # Create new account
            new_account = SchwabAccount(
                user_id=current_user.id,
                account_number=account_data["account_number"],
                account_type=account_data.get("account_type", ""),
                hash_value=account_data.get("hash_value", ""),
                is_day_trader=account_data.get("is_day_trader", False),
                is_closing_only_restricted=account_data.get("is_closing_only_restricted", False),
                buying_power=account_data.get("buying_power", 0.0),
                cash_balance=account_data.get("cash_balance", 0.0),
                last_updated=datetime.utcnow()
            )
            
            db.add(new_account)
            db.flush()  # Get the account ID
            imported_accounts += 1
            
            # Import positions for this account
            for position_data in account_data.get("positions", []):
                new_position = SchwabPosition(
                    account_id=new_account.id,
                    symbol=position_data["symbol"],
                    quantity=position_data.get("quantity", 0.0),
                    market_value=position_data.get("market_value", 0.0),
                    average_price=position_data.get("average_price", 0.0),
                    day_change=position_data.get("day_change", 0.0),
                    day_change_percent=position_data.get("day_change_percent", 0.0),
                    position_type=position_data.get("position_type", ""),
                    asset_type=position_data.get("asset_type", ""),
                    schwab_position_id=position_data.get("schwab_position_id", ""),
                    last_updated=datetime.utcnow()
                )
                
                # Handle option-specific fields
                if position_data.get("underlying_symbol"):
                    new_position.underlying_symbol = position_data["underlying_symbol"]
                if position_data.get("option_type"):
                    new_position.option_type = position_data["option_type"]
                if position_data.get("strike_price"):
                    new_position.strike_price = position_data["strike_price"]
                if position_data.get("expiration_date"):
                    new_position.expiration_date = datetime.fromisoformat(
                        position_data["expiration_date"].replace("Z", "+00:00")
                    )
                
                db.add(new_position)
                imported_positions += 1
        
        db.commit()
        
        result = {
            "message": "Positions imported successfully",
            "result": {
                "source_export": import_data["export_info"],
                "accounts_imported": imported_accounts,
                "positions_imported": imported_positions,
                "import_timestamp": datetime.utcnow().isoformat()
            }
        }
        
        logger.info(f"Imported {imported_accounts} accounts with {imported_positions} positions for user {current_user.email}")
        
        return result
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error importing positions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to import positions: {str(e)}")
