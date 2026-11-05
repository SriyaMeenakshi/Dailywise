import uuid
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.core.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)
_ASYMMETRIC_ALGS = ["ES256", "RS256"]


@dataclass(frozen=True)
class AuthUser:
    id: uuid.UUID
    email: str | None
    display_name: str | None


@lru_cache
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True, lifespan=3600)


def _unauthorized(detail: str = "Invalid or expired credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def decode_supabase_token(token: str, settings: Settings) -> dict:
    """Verify a Supabase access token: signature, expiry, audience and (when known) issuer."""
    try:
        alg = jwt.get_unverified_header(token).get("alg")
        options = {"require": ["exp", "sub"]}
        issuer = settings.jwt_issuer or None
        if alg == "HS256":
            if not settings.supabase_jwt_secret:
                raise _unauthorized()
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                issuer=issuer,
                options=options,
            )
        if alg in _ASYMMETRIC_ALGS and settings.jwks_url:
            key = _jwks_client(settings.jwks_url).get_signing_key_from_jwt(token).key
            return jwt.decode(
                token,
                key,
                algorithms=_ASYMMETRIC_ALGS,
                audience="authenticated",
                issuer=issuer,
                options=options,
            )
    except HTTPException:
        raise
    except jwt.PyJWTError:
        raise _unauthorized() from None
    raise _unauthorized()


def get_auth_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> AuthUser:
    if credentials is None:
        raise _unauthorized("Missing bearer token")
    claims = decode_supabase_token(credentials.credentials, settings)
    try:
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError):
        raise _unauthorized() from None
    meta = claims.get("user_metadata") or {}
    return AuthUser(
        id=user_id,
        email=claims.get("email"),
        display_name=meta.get("full_name") or meta.get("name"),
    )
