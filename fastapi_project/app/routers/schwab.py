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
from ..dependencies import get_current_user
from ..database import get_db
from .. import models
from ..services.schwab_sync_service import SchwabSyncService
from .. import models
from ..models import SchwabAccount, SchwabPosition

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
            # Trigger sync first
            schwab_client = SchwabClient()
            sync_service = SchwabSyncService(db, schwab_client)
            await sync_service.sync_all_accounts(force_refresh=True)
        
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
        schwab_client = SchwabClient()
        return await schwab_client.get_account_summaries()
        
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
        schwab_client = SchwabClient()
        sync_service = SchwabSyncService(db, schwab_client)
        
        if fresh:
            # Force refresh from Schwab API
            sync_result = await sync_service.sync_all_accounts(force_refresh=True)
            logger.info(f"Fresh sync completed: {sync_result}")
        
        # Get stored positions
        accounts = db.query(SchwabAccount).all()
        
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
        schwab_client = SchwabClient()
        sync_service = SchwabSyncService(db, schwab_client)
        
        result = await sync_service.sync_all_accounts(force_refresh=force)
        return {
            "message": "Synchronization completed",
            "result": result
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
