from fastapi import Header, HTTPException, status
from app.core.config import settings

def verify_internal_api_key(x_api_key: str = Header(...)) -> str:
    if x_api_key != settings.INTERNAL_API_KEY.get_secret_value():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Internal API Key"
        )
    return x_api_key