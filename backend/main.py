from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings, APP_VERSION
from routers import health, medical_records, departments, rooms, doctors, patients_admin

app = FastAPI(
    title="Hospital Record Viewer API",
    version=APP_VERSION,
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
app.include_router(doctors.router, prefix="/api")
app.include_router(patients_admin.router, prefix="/api")
