"""Google Calendar API client with attachment support."""

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from datetime import datetime, timedelta
from typing import Optional
from models import Meeting, Attendee
from config import get_settings
import io
import logging

logger = logging.getLogger(__name__)


class GoogleCalendarClient:
    """Client for interacting with Google Calendar API with attachment support."""

    SCOPES = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    def __init__(self, access_token: str, refresh_token: Optional[str] = None):
        settings = get_settings()
        self.credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        )
        self.service = build("calendar", "v3", credentials=self.credentials)
        self._drive_service = None

    def _get_drive_service(self):
        """Get or create Google Drive service for attachment downloads."""
        if not self._drive_service:
            self._drive_service = build("drive", "v3", credentials=self.credentials)
        return self._drive_service

    def get_upcoming_meetings(
        self,
        days_ahead: int = 7,
        max_results: int = 20,
    ) -> list[Meeting]:
        """Fetch upcoming meetings from Google Calendar."""
        now = datetime.utcnow()
        time_min = now.isoformat() + "Z"
        time_max = (now + timedelta(days=days_ahead)).isoformat() + "Z"

        events_result = self.service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = events_result.get("items", [])
        meetings = []

        for event in events:
            meeting = self._parse_event(event)
            if meeting:
                meetings.append(meeting)

        return meetings

    def get_meeting_by_id(self, meeting_id: str) -> Optional[Meeting]:
        """Fetch a specific meeting by ID."""
        try:
            event = self.service.events().get(
                calendarId="primary",
                eventId=meeting_id,
            ).execute()

            return self._parse_event(event)
        except Exception as e:
            logger.error(f"Error getting meeting: {e}")
            return None

    def _parse_event(self, event: dict) -> Optional[Meeting]:
        """Parse a calendar event into a Meeting object."""
        start = event.get("start", {})
        end = event.get("end", {})

        # Skip all-day events without specific times
        if "dateTime" not in start:
            return None

        attendees = []
        for attendee in event.get("attendees", []):
            attendees.append(Attendee(
                email=attendee.get("email", ""),
                name=attendee.get("displayName"),
                response_status=attendee.get("responseStatus"),
            ))

        # Extract meeting link
        meeting_link = None
        if "hangoutLink" in event:
            meeting_link = event["hangoutLink"]
        elif "conferenceData" in event:
            entry_points = event["conferenceData"].get("entryPoints", [])
            for ep in entry_points:
                if ep.get("entryPointType") == "video":
                    meeting_link = ep.get("uri")
                    break

        return Meeting(
            id=event["id"],
            title=event.get("summary", "Untitled Meeting"),
            description=event.get("description"),
            start_time=datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00")),
            end_time=datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00")),
            attendees=attendees,
            location=event.get("location"),
            meeting_link=meeting_link,
        )

    def get_event_with_attachments(self, event_id: str) -> Optional[dict]:
        """
        Get a calendar event with full attachment details.

        Returns dict with meeting details plus attachments list.
        """
        try:
            event = self.service.events().get(
                calendarId="primary",
                eventId=event_id,
            ).execute()

            meeting = self._parse_event(event)
            if not meeting:
                return None

            # Get attachments
            attachments = []
            for attachment in event.get("attachments", []):
                attachments.append({
                    "file_id": attachment.get("fileId", ""),
                    "filename": attachment.get("title", "unknown"),
                    "mime_type": attachment.get("mimeType", ""),
                    "file_url": attachment.get("fileUrl", ""),
                    "icon_link": attachment.get("iconLink", ""),
                })

            return {
                "meeting": meeting,
                "attachments": attachments,
                "raw_event": event,
            }

        except Exception as e:
            logger.error(f"Error getting event with attachments: {e}")
            return None

    def download_attachment(self, file_id: str) -> Optional[tuple[bytes, str, str]]:
        """
        Download a calendar attachment from Google Drive.

        Args:
            file_id: The Google Drive file ID

        Returns:
            Tuple of (content_bytes, filename, mime_type) or None on error
        """
        try:
            drive_service = self._get_drive_service()

            # Get file metadata
            file_metadata = drive_service.files().get(
                fileId=file_id,
                fields='name,mimeType',
            ).execute()

            filename = file_metadata.get('name', 'unknown')
            mime_type = file_metadata.get('mimeType', '')

            # Handle Google Workspace files (export to different format)
            google_mime_types = {
                'application/vnd.google-apps.document': 'text/plain',
                'application/vnd.google-apps.spreadsheet': 'text/csv',
                'application/vnd.google-apps.presentation': 'text/plain',
            }

            if mime_type in google_mime_types:
                content = drive_service.files().export(
                    fileId=file_id,
                    mimeType=google_mime_types[mime_type],
                ).execute()

                if isinstance(content, str):
                    content = content.encode('utf-8')

                return content, filename, mime_type

            # Download regular file
            request = drive_service.files().get_media(fileId=file_id)
            file_buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(file_buffer, request)

            done = False
            while not done:
                _, done = downloader.next_chunk()

            return file_buffer.getvalue(), filename, mime_type

        except Exception as e:
            logger.error(f"Error downloading attachment: {e}")
            return None

    def get_meetings_in_range(
        self,
        start_time: datetime,
        end_time: datetime,
        include_attachments: bool = False,
    ) -> list[dict]:
        """
        Get all meetings in a time range with optional attachment info.

        Args:
            start_time: Start of range
            end_time: End of range
            include_attachments: Whether to include attachment metadata

        Returns:
            List of meeting dicts with optional attachments
        """
        try:
            events_result = self.service.events().list(
                calendarId="primary",
                timeMin=start_time.isoformat() + "Z",
                timeMax=end_time.isoformat() + "Z",
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            meetings = []
            for event in events_result.get("items", []):
                meeting = self._parse_event(event)
                if not meeting:
                    continue

                meeting_data = {
                    "meeting": meeting,
                    "event_id": event["id"],
                }

                if include_attachments:
                    attachments = []
                    for attachment in event.get("attachments", []):
                        attachments.append({
                            "file_id": attachment.get("fileId", ""),
                            "filename": attachment.get("title", "unknown"),
                            "mime_type": attachment.get("mimeType", ""),
                        })
                    meeting_data["attachments"] = attachments

                meetings.append(meeting_data)

            return meetings

        except Exception as e:
            logger.error(f"Error getting meetings in range: {e}")
            return []

    def get_meetings_needing_prep(
        self,
        hours_ahead: int = 48,
        exclude_ids: Optional[list[str]] = None,
    ) -> list[Meeting]:
        """
        Get meetings that need prep generated.

        Args:
            hours_ahead: How far ahead to look (default 48 hours)
            exclude_ids: Meeting IDs to exclude (already have prep)

        Returns:
            List of meetings needing prep
        """
        exclude_ids = exclude_ids or []

        now = datetime.utcnow()
        time_min = now.isoformat() + "Z"
        time_max = (now + timedelta(hours=hours_ahead)).isoformat() + "Z"

        try:
            events_result = self.service.events().list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            meetings = []
            for event in events_result.get("items", []):
                if event["id"] in exclude_ids:
                    continue

                meeting = self._parse_event(event)
                if meeting and len(meeting.attendees) > 0:
                    meetings.append(meeting)

            return meetings

        except Exception as e:
            logger.error(f"Error getting meetings needing prep: {e}")
            return []

    def get_recurring_meeting_instances(
        self,
        recurring_event_id: str,
        max_instances: int = 10,
    ) -> list[Meeting]:
        """Get instances of a recurring meeting."""
        try:
            instances_result = self.service.events().instances(
                calendarId="primary",
                eventId=recurring_event_id,
                maxResults=max_instances,
            ).execute()

            meetings = []
            for event in instances_result.get("items", []):
                meeting = self._parse_event(event)
                if meeting:
                    meetings.append(meeting)

            return meetings

        except Exception as e:
            logger.error(f"Error getting recurring instances: {e}")
            return []
