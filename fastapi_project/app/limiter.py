"""
Shared rate limiter instance for the Allocraft API.

Usage in routers:
    from ..limiter import limiter
    from fastapi import Request

    @router.post("/login")
    @limiter.limit("5/minute")
    def login(request: Request, ...):
        ...
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Key on the client IP address. Behind a reverse proxy, ensure
# FORWARDED / X-Forwarded-For is trusted via trusted_proxies.
limiter = Limiter(key_func=get_remote_address)
