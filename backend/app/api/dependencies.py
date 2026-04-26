from fastapi import Header, HTTPException, status, Depends
from app.core.config import settings
from app.core.db import get_session
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlmodel import Session, select
from app.models import User, UserRole

def verify_internal_api_key(x_api_key: str = Header(...)) -> str:
    if x_api_key != settings.INTERNAL_API_KEY.get_secret_value():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Internal API Key"
        )
    return x_api_key


# Where the login endpoint is (for the interactive Swagger Docs)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY.get_secret_value(), algorithms=[settings.ALGORITHM])
        username: None | str = payload.get("sub")
        if username is None:
            raise credentials_exception
            
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise credentials_exception

    user = session.exec(select(User).where(User.username == username)).first()
    if user is None or not user.is_active:
        raise credentials_exception
        
    return user

def get_current_admin(current_user: User = Depends(get_current_user)):
    """Runs the standard guard first, then checks if the role is Admin."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user