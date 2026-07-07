from __future__ import annotations
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError, ExpiredSignatureError
from .config import settings
from .database import get_supabase_admin

security = HTTPBearer(auto_error=False)

_AUTH_HEADERS = {"WWW-Authenticate": "Bearer"}

# Supabase는 비대칭 JWT 서명키(ES256/RS256)로 마이그레이션되었다.
# 토큰은 JWKS 공개키로 검증하고, 레거시 HS256(공유 시크릿)은 폴백으로 둔다.
_JWKS_CACHE: dict | None = None


def _jwks_url() -> str:
    return f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"


async def _get_jwks(force: bool = False) -> dict:
    global _JWKS_CACHE
    if _JWKS_CACHE is None or force:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(_jwks_url())
            resp.raise_for_status()
            _JWKS_CACHE = resp.json()
    return _JWKS_CACHE


async def _find_key(kid: str) -> dict | None:
    jwks = await _get_jwks()
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    # 키 회전 가능성 → 한 번 강제 재조회
    jwks = await _get_jwks(force=True)
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers=_AUTH_HEADERS,
        )
    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")

        if alg == "HS256":
            # 레거시 대칭키 검증
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"leeway": 10},
            )
        else:
            # 비대칭키(ES256/RS256) — JWKS 공개키로 검증
            kid = header.get("kid")
            if not kid:
                raise JWTError("missing kid")
            key = await _find_key(kid)
            if key is None:
                raise JWTError("no matching JWKS key")
            payload = jwt.decode(
                token,
                key,
                algorithms=[alg],
                audience="authenticated",
                options={"leeway": 10},
            )

        return {**payload, "token": token}
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers=_AUTH_HEADERS,
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers=_AUTH_HEADERS,
        )


async def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """관리자 전용 엔드포인트 가드 — user_profiles.role이 admin이 아니면 403."""
    sub = current_user.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다",
        )
    try:
        result = (
            get_supabase_admin()
            .table("user_profiles")
            .select("role")
            .eq("user_id", sub)
            .execute()
        )
    except Exception:
        # 권한 확인 불가 시 fail-closed
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="권한 확인에 실패했습니다. 잠시 후 다시 시도해주세요",
        )
    rows = result.data or []
    if not rows or rows[0].get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다",
        )
    return current_user
