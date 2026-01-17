from supabase import create_client, Client
from config import get_settings
from cryptography.fernet import Fernet
import base64
import hashlib
from typing import Optional
from models import OAuthToken
from datetime import datetime

settings = get_settings()


def get_encryption_key() -> bytes:
    """Derive a Fernet-compatible key from the secret key."""
    key = hashlib.sha256(settings.secret_key.encode()).digest()
    return base64.urlsafe_b64encode(key)


def encrypt_token(token: str) -> str:
    """Encrypt a token for storage."""
    f = Fernet(get_encryption_key())
    return f.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a stored token."""
    f = Fernet(get_encryption_key())
    return f.decrypt(encrypted_token.encode()).decode()


def get_supabase_client() -> Client:
    """Get the Supabase client."""
    return create_client(settings.supabase_url, settings.supabase_key)


def get_supabase_admin_client() -> Client:
    """Get the Supabase admin client with service key."""
    return create_client(settings.supabase_url, settings.supabase_service_key)


async def store_oauth_token(
    user_id: str,
    provider: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    expires_at: Optional[datetime] = None,
) -> None:
    """Store encrypted OAuth tokens in Supabase."""
    client = get_supabase_admin_client()  # Use admin client to bypass RLS

    encrypted_access = encrypt_token(access_token)
    encrypted_refresh = encrypt_token(refresh_token) if refresh_token else None

    data = {
        "user_id": user_id,
        "provider": provider,
        "access_token": encrypted_access,
        "refresh_token": encrypted_refresh,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "updated_at": datetime.utcnow().isoformat(),
    }

    # Upsert the token
    client.table("oauth_tokens").upsert(
        data,
        on_conflict="user_id,provider"
    ).execute()


async def get_oauth_token(user_id: str, provider: str) -> Optional[OAuthToken]:
    """Retrieve and decrypt OAuth tokens from Supabase."""
    client = get_supabase_admin_client()  # Use admin client to bypass RLS

    result = client.table("oauth_tokens").select("*").eq(
        "user_id", user_id
    ).eq("provider", provider).execute()

    if not result.data or len(result.data) == 0:
        return None

    data = result.data[0]
    return OAuthToken(
        user_id=data["user_id"],
        provider=data["provider"],
        access_token=decrypt_token(data["access_token"]),
        refresh_token=decrypt_token(data["refresh_token"]) if data.get("refresh_token") else None,
        expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
    )


async def delete_oauth_token(user_id: str, provider: str) -> None:
    """Delete OAuth tokens from Supabase."""
    client = get_supabase_admin_client()  # Use admin client to bypass RLS
    client.table("oauth_tokens").delete().eq(
        "user_id", user_id
    ).eq("provider", provider).execute()


async def store_meeting_prep(
    user_id: str,
    meeting_id: str,
    prep_document: dict,
) -> None:
    """Store a generated meeting prep document."""
    client = get_supabase_admin_client()  # Use admin client to bypass RLS

    data = {
        "user_id": user_id,
        "meeting_id": meeting_id,
        "prep_document": prep_document,
        "generated_at": datetime.utcnow().isoformat(),
    }

    client.table("meeting_preps").upsert(
        data,
        on_conflict="user_id,meeting_id"
    ).execute()


async def get_meeting_prep(user_id: str, meeting_id: str) -> Optional[dict]:
    """Retrieve a stored meeting prep document."""
    client = get_supabase_admin_client()  # Use admin client to bypass RLS

    result = client.table("meeting_preps").select("*").eq(
        "user_id", user_id
    ).eq("meeting_id", meeting_id).execute()

    if not result.data or len(result.data) == 0:
        return None

    return result.data[0].get("prep_document")


async def check_connection_status(user_id: str) -> dict:
    """Check which services the user has connected."""
    client = get_supabase_admin_client()  # Use admin client to bypass RLS

    result = client.table("oauth_tokens").select("provider").eq(
        "user_id", user_id
    ).execute()

    providers = [r["provider"] for r in result.data] if result.data else []

    return {
        "google_connected": "google" in providers,
        "slack_connected": "slack" in providers,
    }


async def get_user_email(user_id: str) -> Optional[str]:
    """Get the user's email from Supabase auth."""
    client = get_supabase_admin_client()

    try:
        # Try to get user from auth.users via admin API
        user = client.auth.admin.get_user_by_id(user_id)
        if user and user.user:
            return user.user.email
    except Exception:
        pass

    return None


async def get_all_users_with_google() -> list[str]:
    """Get all user IDs that have Google connected (for scheduler)."""
    client = get_supabase_admin_client()

    result = client.table("oauth_tokens").select("user_id").eq(
        "provider", "google"
    ).execute()

    if not result.data:
        return []

    return list(set(r["user_id"] for r in result.data))


async def get_user_meeting_prep_ids(user_id: str) -> list[str]:
    """Get all meeting IDs that have prep documents for a user."""
    client = get_supabase_admin_client()

    result = client.table("meeting_preps").select("meeting_id").eq(
        "user_id", user_id
    ).execute()

    if not result.data:
        return []

    return [r["meeting_id"] for r in result.data]
