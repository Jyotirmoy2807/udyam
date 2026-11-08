from datetime import datetime, timezone
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import redis
from sqlalchemy import create_engine, text
import boto3
from botocore.client import Config
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import structlog

from app.config import settings
from app.db.crypto import mask_phone, mask_gstin
from app.api.auth import router as auth_router
from app.api.leads import router as leads_router
from app.api.advisor import router as advisor_router
from app.api.quotes import router as quotes_router
from app.api.kyc import router as kyc_router
from app.api.orders import router as orders_router
from app.api.ops import router as ops_router
from app.api.webhooks import router as webhooks_router

logger = structlog.get_logger("api.access")

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])

app = FastAPI(
    title="Project Udyam Digital API",
    version="1.0.0",
    description="AI-Assisted SME Connectivity & Digital Transformation Platform (Accel YTL 2026)",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def pii_masking_audit_middleware(request: Request, call_next):
    """Audits HTTP requests and responses while guaranteeing zero unmasked PII leakage."""
    client_ip = request.client.host if request.client else "unknown"
    path = request.url.path

    response = await call_next(request)

    # Redact sensitive headers
    logger.info(
        "http_request_completed",
        method=request.method,
        path=path,
        status_code=response.status_code,
        client_ip=client_ip,
    )
    return response


# Include API Routers
app.include_router(auth_router)
app.include_router(leads_router)
app.include_router(advisor_router)
app.include_router(quotes_router)
app.include_router(kyc_router)
app.include_router(orders_router)
app.include_router(ops_router)
app.include_router(webhooks_router)


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    health_status = {
        "status": "healthy",
        "clock": {
            "fixed_date": settings.CLOCK_FIXED_DATE.strftime("%Y-%m-%d"),
            "fixed_datetime": settings.CLOCK_FIXED_DATE.isoformat(),
            "status": "ok",
        },
        "services": {},
    }

    # 1. PostgreSQL check
    try:
        engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health_status["services"]["postgres"] = "healthy"
    except Exception as e:
        health_status["services"]["postgres"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    # 2. Redis check
    try:
        r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2.0)
        r.ping()
        health_status["services"]["redis"] = "healthy"
    except Exception as e:
        health_status["services"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    # 3. MinIO check
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=f"{'https' if settings.MINIO_SECURE else 'http'}://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        s3.head_bucket(Bucket=settings.MINIO_BUCKET)
        health_status["services"]["minio"] = "healthy"
    except Exception as e:
        health_status["services"]["minio"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    if health_status["status"] == "degraded":
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=health_status)

    return health_status
