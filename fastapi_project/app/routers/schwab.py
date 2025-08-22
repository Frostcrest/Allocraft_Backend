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
from ..dependencies import get_current_user

router = APIRouter(prefix="/schwab", tags=["schwab"])
logger = logging.getLogger(__name__)

# Schwab API Configuration
SCHWAB_CONFIG = {
    "auth_url": "https://api.schwabapi.com/v1/oauth/authorize",
    "token_url": "https://api.schwabapi.com/v1/oauth/token",
    "accounts_url": "https://api.schwabapi.com/trader/v1/accounts",
    "client_id": os.getenv("SCHWAB_CLIENT_ID", ""),
    "client_secret": os.getenv("SCHWAB_CLIENT_SECRET", ""),
    "redirect_uri": os.getenv("SCHWAB_REDIRECT_URI", "http://localhost:3000/api/schwab/callback")
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
async def oauth_callback(code: Optional[str] = None, error: Optional[str] = None):
    """Handle OAuth callback from Schwab"""
    if error:
        logger.error(f"OAuth error: {error}")
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
    
    if not code:
        raise HTTPException(status_code=400, detail="No authorization code received")
    
    try:
        # Exchange code for tokens
        tokens = await exchange_code_for_tokens(code)
        
        # Redirect back to frontend with success
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(
            url=f"{frontend_url}/auth/callback?success=true",
            status_code=302
        )
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
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

@router.get("/accounts")
async def get_accounts(access_token: str, current_user=Depends(get_current_user)):
    """Get user's Schwab accounts"""
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
async def get_positions(account_id: str, access_token: str, current_user=Depends(get_current_user)):
    """Get positions for a specific account"""
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
async def refresh_access_token(refresh_token: str, current_user=Depends(get_current_user)):
    """Refresh access token using refresh token"""
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
