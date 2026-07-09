from __future__ import annotations
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from postgrest.exceptions import APIError

from core.config import settings, APP_VERSION
from routers import health, medical_records, departments, rooms, access_logs, doctor, me, roles, users

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Hospital Record Viewer API",
    version=APP_VERSION,
)


@app.exception_handler(APIError)
async def postgrest_error_handler(request: Request, exc: APIError) -> JSONResponse:
    # DB/PostgREST 예외의 내부 원문을 사용자에게 노출하지 않는다.
    # 원인은 서버 로그에만 남기고, 응답은 일반화된 메시지로 통일.
    logger.exception("PostgREST 오류 method=%s path=%s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "데이터 처리 중 오류가 발생했습니다"},
    )

cors_origins = settings.get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(medical_records.router, prefix="/api")
app.include_router(departments.router, prefix="/api")
app.include_router(rooms.router, prefix="/api")
app.include_router(access_logs.router, prefix="/api")
app.include_router(doctor.router, prefix="/api")
app.include_router(me.router, prefix="/api")
app.include_router(roles.router, prefix="/api")
app.include_router(users.router, prefix="/api")
