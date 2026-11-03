from datetime import datetime, timezone
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
import redis
from sqlalchemy import create_engine, text
import boto3
from botocore.client import Config

try:
    from app.config import settings
    from app.api.quotes import router as quotes_router
except ModuleNotFoundError:
    from backend.app.config import settings
    from backend.app.api.quotes import router as quotes_router

app = FastAPI(
    title="Project Udyam Digital API",
    version="0.1.0",
    description="AI-Assisted SME Connectivity & Digital Bundle Platform",
)

app.include_router(quotes_router)


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
        s3.list_buckets()
        health_status["services"]["minio"] = "healthy"
    except Exception as e:
        health_status["services"]["minio"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    http_status = (
        status.HTTP_200_OK
        if health_status["status"] == "healthy"
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return JSONResponse(status_code=http_status, content=health_status)
