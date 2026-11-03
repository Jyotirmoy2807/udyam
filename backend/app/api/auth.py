"""Authentication and JWT role-based access control."""

from datetime import datetime, timedelta, timezone
from typing import Any
import jwt
from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication & Access Control"])
security = HTTPBearer(auto_error=False)


class OtpSendRequest(BaseModel):
    phone: str = Field(description="10-digit Indian mobile number")
    channel: str = Field(default="SMS", description="SMS or WHATSAPP")


class OtpVerifyRequest(BaseModel):
    phone: str
    otp: str
    role: str = Field(default="customer", description="customer, partner, or ops_admin")


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=8))
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> dict[str, Any]:
    if not credentials:
        # Default anonymous/demo customer context if no auth header passed
        return {"sub": "demo-user", "role": "customer"}
    return decode_access_token(credentials.credentials)


def require_role(required_role: str):
    async def role_checker(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        user_role = user.get("role", "customer")
        if user_role != required_role and user_role != "ops_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires role '{required_role}', user has '{user_role}'.",
            )
        return user
    return role_checker


@router.post("/otp/send")
def send_otp(req: OtpSendRequest):
    """Generates and dispatches mock OTP."""
    clean_phone = req.phone.strip()
    return {
        "status": "OTP_SENT",
        "phone_masked": f"******{clean_phone[-4:]}" if len(clean_phone) >= 4 else clean_phone,
        "message": f"Demo OTP is {settings.DEMO_FIXED_OTP}",
    }


@router.post("/otp/verify")
def verify_otp(req: OtpVerifyRequest):
    """Verifies OTP and returns role-based JWT."""
    if req.otp != settings.DEMO_FIXED_OTP:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP code.")

    token = create_access_token({
        "sub": req.phone,
        "role": req.role,
    })

    return {
        "status": "AUTHENTICATED",
        "access_token": token,
        "token_type": "bearer",
        "role": req.role,
        "phone_masked": f"******{req.phone[-4:]}" if len(req.phone) >= 4 else req.phone,
    }
