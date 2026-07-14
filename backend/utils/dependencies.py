from fastapi import Request, HTTPException, Depends, WebSocket, status
import jwt
from backend.config.settings import settings

def get_current_user(request: Request):
    """
    Dependency to verify the JWT session token in the HttpOnly cookie.
    Extracts the user payload if valid, otherwise raises a 401 Unauthorized error.
    """
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session has expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session token.")

def get_current_user_ws(websocket: WebSocket):
    """
    Dependency to verify the JWT session token in the HttpOnly cookie for WebSockets.
    """
    token = websocket.cookies.get("session_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token.")

