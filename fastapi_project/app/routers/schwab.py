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
from ..dependencies import get_current_user, get_db
from .. import models

router = APIRouter(prefix="/schwab", tags=["schwab"])
logger = logging.getLogger(__name__)

# Schwab API Configuration
SCHWAB_CONFIG = {
    "auth_url": "https://api.schwabapi.com/v1/oauth/authorize",
    "token_url": "https://api.schwabapi.com/v1/oauth/token",
    "accounts_url": "https://api.schwabapi.com/trader/v1/accounts",
    "client_id": os.getenv("SCHWAB_CLIENT_ID", ""),
    "client_secret": os.getenv("SCHWAB_CLIENT_SECRET", ""),
    "redirect_uri": os.getenv("SCHWAB_REDIRECT_URI", "https://allocraft-backend.onrender.com/schwab/callback")
}

@router.get("/auth-url")
async def get_auth_url():
    """Generate Schwab OAuth authorization URL"""
    if not SCHWAB_CONFIG["client_id"]:
        raise HTTPException(status_code=500, detail="Schwab Client ID not configured")
    
    params = {
        "response_type": "code",
        "client_id": SCHWAB_CONFIG["client_id"],
        "redirect_uri": SCHWAB_CONFIG["redirect_uri"],
        "scope": "AccountsAndTrading readonly"
    }
    
    auth_url = f"{SCHWAB_CONFIG['auth_url']}?{urlencode(params)}"
    return {"auth_url": auth_url}

@router.get("/callback")
async def oauth_callback(
    code: Optional[str] = None, 
    error: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Handle OAuth callback from Schwab"""
    if error:
        logger.error(f"OAuth error: {error}")
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
    
    if not code:
        raise HTTPException(status_code=400, detail="No authorization code received")
    
    try:
        # Exchange code for tokens
        tokens = await exchange_code_for_tokens(code)
        
        # Store tokens with the user
        await store_user_schwab_tokens(db, current_user, tokens)
        
        # Redirect back to frontend with success
        frontend_url = os.getenv("FRONTEND_URL", "https://allocraft.app")
        return RedirectResponse(
            url=f"{frontend_url}/auth/callback?success=true",
            status_code=302
        )
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        frontend_url = os.getenv("FRONTEND_URL", "https://allocraft.app")
        return RedirectResponse(
            url=f"{frontend_url}/auth/callback?error={str(e)}",
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
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get user's Schwab accounts"""
    access_token = await get_user_schwab_token(db, current_user)
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated with Schwab")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            SCHWAB_CONFIG["accounts_url"],
            headers=headers
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to fetch accounts: {response.text}"
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
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to fetch positions: {response.text}"
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
