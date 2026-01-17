"""ProactivePA - AI Meeting Prep Assistant Backend."""

from fastapi import FastAPI, HTTPException, Depends, Query, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional
import httpx
import jwt
from datetime import datetime, timedelta
import logging
import asyncio

from config import get_settings
from models import (
    Meeting,
    PrepDocument,
    MeetingPrepResponse,
    ConnectionStatus,
)
from supabase_client import (
    store_oauth_token,
    get_oauth_token,
    delete_oauth_token,
    store_meeting_prep,
    get_meeting_prep,
    check_connection_status,
)
from integrations import GoogleCalendarClient, GmailClient, SlackClient
from context_gatherer import ContextGatherer, DemoContextGatherer
from ai.context_analyzer import analyze_meeting_context
from ai.prep_generator import EnhancedPrepGenerator, DemoPrepGenerator, EnhancedPrepDocument
from ai.openai_prep import PrepDocumentGenerator, DemoGenerator
from demo_data import (
    get_demo_meetings,
    get_demo_meeting_by_id,
    get_demo_emails,
    get_demo_slack_messages,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="ProactivePA",
    description="AI-powered meeting prep assistant with document analysis",
    version="2.0.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Auth dependency - verify Supabase JWT
async def get_current_user(
    authorization: Optional[str] = Header(None),
    user_id: Optional[str] = Query(None),
) -> str:
    """Get current user from auth header or query param (demo mode)."""
    if settings.demo_mode and user_id:
        return user_id
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        try:
            # Decode JWT to get user ID (Supabase JWTs contain 'sub' claim)
            payload = jwt.decode(token, options={"verify_signature": False})
            user_id_from_token = payload.get("sub")
            if user_id_from_token:
                return user_id_from_token
        except Exception as e:
            logger.error(f"JWT decode error: {e}")
            raise HTTPException(status_code=401, detail="Invalid token")
    if settings.demo_mode:
        return "demo-user"
    raise HTTPException(status_code=401, detail="Not authenticated")


# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "demo_mode": settings.demo_mode, "version": "2.0.0"}


# ============ OAuth Routes ============

@app.get("/auth/google")
async def google_auth_start(user_id: str = Depends(get_current_user)):
    """Start Google OAuth flow."""
    scopes = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    scope_str = " ".join(scopes)

    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.google_client_id}&"
        f"redirect_uri={settings.google_redirect_uri}&"
        f"response_type=code&"
        f"scope={scope_str}&"
        f"access_type=offline&"
        f"prompt=consent&"
        f"state={user_id}"
    )
    return {"auth_url": auth_url}


@app.get("/auth/google/callback")
async def google_auth_callback(code: str, state: str):
    """Handle Google OAuth callback."""
    user_id = state

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.google_redirect_uri,
            },
        )

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange code")

    tokens = response.json()
    expires_at = datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600))

    await store_oauth_token(
        user_id=user_id,
        provider="google",
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        expires_at=expires_at,
    )

    return RedirectResponse(url=f"{settings.frontend_url}/connect?google=success")


@app.get("/auth/slack")
async def slack_auth_start(user_id: str = Depends(get_current_user)):
    """Start Slack OAuth flow."""
    # User token scopes (needed for search:read and file access)
    user_scopes = "search:read,users:read,users:read.email,channels:history,groups:history,im:history,mpim:history,files:read"

    auth_url = (
        f"https://slack.com/oauth/v2/authorize?"
        f"client_id={settings.slack_client_id}&"
        f"user_scope={user_scopes}&"
        f"redirect_uri={settings.slack_redirect_uri}&"
        f"state={user_id}"
    )
    return {"auth_url": auth_url}


@app.get("/auth/slack/callback")
async def slack_auth_callback(code: str, state: str):
    """Handle Slack OAuth callback."""
    user_id = state

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://slack.com/api/oauth.v2.access",
            data={
                "client_id": settings.slack_client_id,
                "client_secret": settings.slack_client_secret,
                "code": code,
                "redirect_uri": settings.slack_redirect_uri,
            },
        )

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange code")

    data = response.json()
    if not data.get("ok"):
        raise HTTPException(status_code=400, detail=data.get("error", "Unknown error"))

    # Get the user token (authed_user.access_token) for user scopes
    access_token = data.get("authed_user", {}).get("access_token") or data.get("access_token")

    await store_oauth_token(
        user_id=user_id,
        provider="slack",
        access_token=access_token,
        refresh_token=None,
        expires_at=None,
    )

    return RedirectResponse(url=f"{settings.frontend_url}/connect?slack=success")


@app.delete("/auth/{provider}")
async def disconnect_provider(
    provider: str,
    user_id: str = Depends(get_current_user),
):
    """Disconnect a provider."""
    await delete_oauth_token(user_id, provider)
    return {"status": "disconnected"}


@app.get("/auth/status", response_model=ConnectionStatus)
async def get_connection_status(user_id: str = Depends(get_current_user)):
    """Get connection status for all providers."""
    if settings.demo_mode:
        return ConnectionStatus(google_connected=True, slack_connected=True)

    status = await check_connection_status(user_id)
    return ConnectionStatus(**status)


# ============ Meetings Routes ============

@app.get("/meetings", response_model=list[Meeting])
async def get_meetings(user_id: str = Depends(get_current_user)):
    """Get upcoming meetings from Google Calendar."""
    if settings.demo_mode:
        return get_demo_meetings()

    token = await get_oauth_token(user_id, "google")
    if not token:
        raise HTTPException(status_code=400, detail="Google not connected")

    calendar = GoogleCalendarClient(token.access_token, token.refresh_token)
    return calendar.get_upcoming_meetings()


@app.get("/meetings/{meeting_id}", response_model=Meeting)
async def get_meeting(
    meeting_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get a specific meeting."""
    if settings.demo_mode:
        meeting = get_demo_meeting_by_id(meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        return meeting

    token = await get_oauth_token(user_id, "google")
    if not token:
        raise HTTPException(status_code=400, detail="Google not connected")

    calendar = GoogleCalendarClient(token.access_token, token.refresh_token)
    meeting = calendar.get_meeting_by_id(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


# ============ Enhanced Prep Document Routes ============

class GeneratePrepRequest(BaseModel):
    meeting_id: str
    force_regenerate: bool = False


class EnhancedPrepResponse(BaseModel):
    """Enhanced prep response with full document analysis."""
    meeting: Meeting
    prep_document: dict  # EnhancedPrepDocument as dict
    context_summary: dict
    generated_at: str

    class Config:
        from_attributes = True


@app.post("/api/meetings/{meeting_id}/generate-prep")
async def generate_enhanced_prep(
    meeting_id: str,
    force_regenerate: bool = False,
    user_id: str = Depends(get_current_user),
):
    """
    Generate comprehensive meeting prep with document analysis.

    This is the new enhanced endpoint that:
    - Gathers context from Gmail, Slack, Calendar
    - Downloads and extracts text from attachments
    - Applies intelligent filtering
    - Generates AI prep with document insights
    """
    # Check for cached prep
    if not force_regenerate and not settings.demo_mode:
        cached = await get_meeting_prep(user_id, meeting_id)
        if cached and cached.get("prep_markdown"):
            # Return cached enhanced prep
            meeting = await get_meeting(meeting_id, user_id)
            return {
                "meeting": meeting,
                "prep_document": cached,
                "context_summary": cached.get("context_stats", {}),
                "generated_at": cached.get("generated_at", datetime.utcnow().isoformat()),
            }

    # Get meeting details
    if settings.demo_mode:
        meeting = get_demo_meeting_by_id(meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
    else:
        token = await get_oauth_token(user_id, "google")
        if not token:
            raise HTTPException(status_code=400, detail="Google not connected")
        calendar = GoogleCalendarClient(token.access_token, token.refresh_token)
        meeting = calendar.get_meeting_by_id(meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

    # Gather comprehensive context
    if settings.demo_mode:
        gatherer = DemoContextGatherer(internal_domain="company.com")
        context = await gatherer.gather_meeting_context(meeting)
    else:
        # Initialize clients
        google_token = await get_oauth_token(user_id, "google")
        slack_token = await get_oauth_token(user_id, "slack")

        gmail_client = GmailClient(google_token.access_token, google_token.refresh_token) if google_token else None
        slack_client = SlackClient(slack_token.access_token) if slack_token else None
        calendar_client = GoogleCalendarClient(google_token.access_token, google_token.refresh_token) if google_token else None

        gatherer = ContextGatherer(
            gmail_client=gmail_client,
            slack_client=slack_client,
            calendar_client=calendar_client,
            drive_credentials=calendar_client.credentials if calendar_client else None,
            internal_domain=None,  # Could be configured per user
        )

        context = await gatherer.gather_meeting_context(meeting, days_back=14, include_documents=True)

    # Apply intelligent filtering
    filtered_context = analyze_meeting_context(context, meeting.title)

    # Generate enhanced prep
    if settings.demo_mode:
        generator = DemoPrepGenerator()
    else:
        generator = EnhancedPrepGenerator()

    prep = generator.generate_prep(
        meeting=meeting,
        filtered_context=filtered_context,
        has_external_attendees=context.has_external_attendees(),
    )

    # Cache the result
    if not settings.demo_mode:
        await store_meeting_prep(
            user_id=user_id,
            meeting_id=meeting_id,
            prep_document=prep.to_dict(),
        )

    return {
        "meeting": meeting,
        "prep_document": prep.to_dict(),
        "context_summary": {
            "slack_messages": prep.context_stats.get("slack_messages_analyzed", 0),
            "email_threads": prep.context_stats.get("emails_analyzed", 0),
            "documents_analyzed": prep.context_stats.get("documents_analyzed", 0),
            "external_attendees": prep.has_external_attendees,
        },
        "generated_at": prep.generated_at.isoformat(),
    }


# Legacy endpoint for backwards compatibility
@app.post("/prep/generate", response_model=MeetingPrepResponse)
async def generate_prep_document(
    request: GeneratePrepRequest,
    user_id: str = Depends(get_current_user),
):
    """Generate a meeting prep document (legacy endpoint)."""

    # Check for cached prep document
    if not request.force_regenerate and not settings.demo_mode:
        cached = await get_meeting_prep(user_id, request.meeting_id)
        if cached:
            meeting = await get_meeting(request.meeting_id, user_id)
            # Convert enhanced prep to legacy format if needed
            if cached.get("prep_markdown"):
                legacy_prep = PrepDocument(
                    meeting_id=request.meeting_id,
                    context_summary=cached.get("context_summary", ""),
                    key_points=[p.get("point", "") for p in cached.get("key_discussion_points", [])],
                    suggested_agenda=[a.get("item", "") for a in cached.get("suggested_agenda", [])],
                    action_items=cached.get("action_items", []),
                    generated_at=datetime.fromisoformat(cached.get("generated_at", datetime.utcnow().isoformat())),
                )
            else:
                legacy_prep = PrepDocument(**cached)
            return MeetingPrepResponse(
                meeting=meeting,
                prep_document=legacy_prep,
            )

    # Get meeting details
    if settings.demo_mode:
        meeting = get_demo_meeting_by_id(request.meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
    else:
        token = await get_oauth_token(user_id, "google")
        if not token:
            raise HTTPException(status_code=400, detail="Google not connected")
        calendar = GoogleCalendarClient(token.access_token, token.refresh_token)
        meeting = calendar.get_meeting_by_id(request.meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

    # Gather context from integrations
    emails = []
    slack_messages = []

    for attendee in meeting.attendees:
        if settings.demo_mode:
            emails.extend(get_demo_emails(attendee.email))
            slack_messages.extend(get_demo_slack_messages(attendee.email))
        else:
            # Get emails
            google_token = await get_oauth_token(user_id, "google")
            if google_token:
                gmail = GmailClient(google_token.access_token, google_token.refresh_token)
                emails.extend(gmail.search_emails_with_person(attendee.email))

            # Get Slack messages
            slack_token = await get_oauth_token(user_id, "slack")
            if slack_token:
                slack = SlackClient(slack_token.access_token)
                slack_messages.extend(slack.search_by_email(attendee.email))

    # Generate prep document
    if settings.demo_mode:
        generator = DemoGenerator()
    else:
        generator = PrepDocumentGenerator()

    prep_document = generator.generate_prep_document(meeting, emails, slack_messages)

    # Cache the result (skip in demo mode)
    if not settings.demo_mode:
        await store_meeting_prep(
            user_id=user_id,
            meeting_id=request.meeting_id,
            prep_document=prep_document.model_dump(mode="json"),
        )

    return MeetingPrepResponse(
        meeting=meeting,
        prep_document=prep_document,
    )


@app.get("/prep/{meeting_id}")
async def get_prep_document(
    meeting_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get a previously generated prep document."""
    if settings.demo_mode:
        # Generate on-the-fly for demo
        meeting = get_demo_meeting_by_id(meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

        # Use enhanced demo generator
        gatherer = DemoContextGatherer(internal_domain="company.com")
        context = await gatherer.gather_meeting_context(meeting)
        filtered_context = analyze_meeting_context(context, meeting.title)

        generator = DemoPrepGenerator()
        prep = generator.generate_prep(meeting, filtered_context, context.has_external_attendees())

        return prep.to_dict()

    cached = await get_meeting_prep(user_id, meeting_id)
    if not cached:
        raise HTTPException(status_code=404, detail="Prep document not found")

    return cached


# ============ Context Gathering Endpoint ============

@app.get("/api/meetings/{meeting_id}/context")
async def get_meeting_context(
    meeting_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Get raw context gathered for a meeting (for debugging/inspection).

    Returns unfiltered context from all sources.
    """
    # Get meeting
    if settings.demo_mode:
        meeting = get_demo_meeting_by_id(meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

        gatherer = DemoContextGatherer(internal_domain="company.com")
        context = await gatherer.gather_meeting_context(meeting)
    else:
        token = await get_oauth_token(user_id, "google")
        if not token:
            raise HTTPException(status_code=400, detail="Google not connected")

        calendar = GoogleCalendarClient(token.access_token, token.refresh_token)
        meeting = calendar.get_meeting_by_id(meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

        # Gather context
        google_token = await get_oauth_token(user_id, "google")
        slack_token = await get_oauth_token(user_id, "slack")

        gmail_client = GmailClient(google_token.access_token, google_token.refresh_token) if google_token else None
        slack_client = SlackClient(slack_token.access_token) if slack_token else None
        calendar_client = GoogleCalendarClient(google_token.access_token, google_token.refresh_token) if google_token else None

        gatherer = ContextGatherer(
            gmail_client=gmail_client,
            slack_client=slack_client,
            calendar_client=calendar_client,
        )

        context = await gatherer.gather_meeting_context(meeting, days_back=14, include_documents=True)

    # Return context summary
    return {
        "meeting_id": meeting_id,
        "meeting_title": meeting.title,
        "attendees": [{"email": a.email, "name": a.name} for a in meeting.attendees],
        "external_attendees": context.external_attendees,
        "stats": {
            "total_emails": context.total_emails,
            "total_slack_messages": context.total_slack_messages,
            "total_documents": context.total_documents,
        },
        "email_subjects": [e.subject for e in context.emails[:10]],
        "slack_channels": list(set(m.channel for m in context.slack_messages[:20])),
        "documents": [{"filename": d.filename, "source": d.source_type}
                     for d in context.get_all_extracted_documents()[:10]],
        "errors": context.errors,
    }


# ============ Demo Mode Endpoint ============

@app.get("/demo/status")
async def demo_status():
    """Check if demo mode is enabled."""
    return {"demo_mode": settings.demo_mode}


@app.get("/demo/meetings")
async def get_demo_meetings_list():
    """Get demo meetings with enhanced context preview."""
    meetings = get_demo_meetings()
    result = []

    for meeting in meetings:
        # Generate quick context preview
        gatherer = DemoContextGatherer(internal_domain="company.com")
        context = await gatherer.gather_meeting_context(meeting)

        result.append({
            "meeting": meeting,
            "context_preview": {
                "emails": context.total_emails,
                "slack_messages": context.total_slack_messages,
                "documents": context.total_documents,
                "has_external": context.has_external_attendees(),
            }
        })

    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
