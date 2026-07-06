from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from backend.config.settings import settings
from workos import WorkOSClient
import jwt
from datetime import datetime, timedelta, timezone

# Initialize WorkOS client using the v9+ SDK
workos_client = WorkOSClient(
    api_key=settings.WORKOS_API_KEY,
    client_id=settings.WORKOS_CLIENT_ID,
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

def create_jwt_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def get_workos_session_id_from_token(access_token: str) -> str | None:
    """
    Decodes the WorkOS access token (without verification) to extract the session ID (sid claim).
    The access token is a JWT issued by WorkOS - we only need the payload, not signature verification.
    """
    try:
        payload = jwt.decode(access_token, options={"verify_signature": False})
        return payload.get("sid")
    except Exception:
        return None

@router.get("/login")
async def login():
    """
    Redirects the user to the WorkOS Authorization URL (uses cached session if available).
    """
    if not settings.WORKOS_CLIENT_ID or not settings.WORKOS_API_KEY:
        raise HTTPException(status_code=500, detail="WorkOS configuration is missing.")

    authorization_url = workos_client.user_management.get_authorization_url(
        redirect_uri=settings.WORKOS_REDIRECT_URI,
        provider="authkit",
    )
    return RedirectResponse(url=authorization_url)

@router.get("/switch")
async def switch_account(email: str = None):
    """
    Forces a fresh WorkOS login screen for a different account.
    Accepts an optional email hint to pre-fill the login form.
    """
    if not settings.WORKOS_CLIENT_ID or not settings.WORKOS_API_KEY:
        raise HTTPException(status_code=500, detail="WorkOS configuration is missing.")

    authorization_url = workos_client.user_management.get_authorization_url(
        redirect_uri=settings.WORKOS_REDIRECT_URI,
        provider="authkit",
        screen_hint="sign-in",
        login_hint=email,  # Pre-fills the email field if provided
    )
    return RedirectResponse(url=authorization_url)

@router.get("/callback")
async def callback(code: str):
    """
    Exchanges the code for a WorkOS profile, generates a JWT, and sets an HttpOnly cookie.
    Stores the WorkOS access_token in the JWT to enable session revocation on logout.
    """
    try:
        # Exchange the authorization code for a user profile using the new SDK
        auth_response = workos_client.user_management.authenticate_with_code(
            code=code,
        )
        user = auth_response.user
        access_token = auth_response.access_token

        # Extract WorkOS session ID from the access token to enable session revocation later
        session_id = get_workos_session_id_from_token(access_token)

        # Create JWT token for our session, storing the WorkOS session ID
        user_data = {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "workos_session_id": session_id,  # Stored to allow proper session revocation
        }
        token = create_jwt_token(user_data)

        # Redirect to the frontend and set the HttpOnly cookie
        response = RedirectResponse(url="/")
        response.set_cookie(
            key="session_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=24 * 3600  # 24 hours
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")

@router.get("/me")
async def get_me(request: Request):
    """
    Returns the currently authenticated user based on the HttpOnly cookie.
    """
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        # Return user info without the internal session ID
        return {k: v for k, v in payload.items() if k != "workos_session_id"}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/logout")
async def logout(request: Request):
    """
    Revokes the WorkOS session server-side, clears the local session cookie,
    and clears the local session cookie.
    Revokes the session on WorkOS server-side so the next login forces fresh authentication.
    Uses GET so the browser can navigate directly without CORS issues.
    """
    # Try to revoke the WorkOS session server-side
    token = request.cookies.get("session_token")
    if token:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
            session_id = payload.get("workos_session_id")
            if session_id:
                # Revoke the session on WorkOS - this ensures the next login shows a fresh screen
                workos_client.user_management.revoke_session(session_id=session_id)
        except Exception:
            pass  # Always clear the local cookie even if revocation fails

    # Clear the local session cookie and redirect to home
    # WorkOS will detect the revoked session and show fresh login next time
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_token")
    return response
