from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class User(BaseModel):
    id: str
    email: str


class OAuthToken(BaseModel):
    user_id: str
    provider: str  # 'google' or 'slack'
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None


class Attendee(BaseModel):
    email: str
    name: Optional[str] = None
    response_status: Optional[str] = None


class Meeting(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    attendees: list[Attendee]
    location: Optional[str] = None
    meeting_link: Optional[str] = None


class SlackMessage(BaseModel):
    text: str
    user: str
    channel: str
    timestamp: str


class Email(BaseModel):
    id: str
    subject: str
    sender: str
    recipient: str
    snippet: str
    date: datetime


class PrepDocument(BaseModel):
    meeting_id: str
    context_summary: str
    key_points: list[str]
    suggested_agenda: list[str]
    action_items: list[str]
    generated_at: datetime


class MeetingPrepRequest(BaseModel):
    meeting_id: str


class MeetingPrepResponse(BaseModel):
    meeting: Meeting
    prep_document: PrepDocument


class ConnectionStatus(BaseModel):
    google_connected: bool
    slack_connected: bool
