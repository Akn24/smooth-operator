"""
Context Gathering System for Meeting Preparation.

Collects context from multiple sources:
- Gmail (emails + attachments)
- Slack (messages + files)
- Google Calendar (event details + attachments)
- Google Drive (shared documents)
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field
import logging
import base64
import io
import re

from models import Meeting, Attendee, Email, SlackMessage
from document_processor import DocumentProcessor, ExtractedDocument

logger = logging.getLogger(__name__)


@dataclass
class EmailAttachment:
    """Represents an email attachment."""
    filename: str
    mime_type: str
    size: int
    content: Optional[bytes] = None
    extracted_text: Optional[str] = None


@dataclass
class EnrichedEmail:
    """Email with full body content and attachments."""
    id: str
    thread_id: str
    subject: str
    sender: str
    recipients: list[str]
    date: datetime
    body_text: str
    body_html: Optional[str] = None
    snippet: str = ""
    attachments: list[EmailAttachment] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)

    def to_basic_email(self) -> Email:
        """Convert to basic Email model."""
        return Email(
            id=self.id,
            subject=self.subject,
            sender=self.sender,
            recipient=self.recipients[0] if self.recipients else "",
            snippet=self.snippet or self.body_text[:200],
            date=self.date,
        )


@dataclass
class SlackFile:
    """Represents a file shared in Slack."""
    id: str
    name: str
    filetype: str
    url_private: str
    size: int
    content: Optional[bytes] = None
    extracted_text: Optional[str] = None
    shared_by: str = ""
    timestamp: str = ""


@dataclass
class EnrichedSlackMessage:
    """Slack message with files and additional context."""
    text: str
    user: str
    user_email: Optional[str]
    channel: str
    channel_type: str  # 'dm', 'channel', 'group'
    timestamp: str
    thread_ts: Optional[str] = None
    files: list[SlackFile] = field(default_factory=list)
    reactions: list[dict] = field(default_factory=list)
    is_thread_reply: bool = False

    def to_basic_message(self) -> SlackMessage:
        """Convert to basic SlackMessage model."""
        return SlackMessage(
            text=self.text,
            user=self.user,
            channel=self.channel,
            timestamp=self.timestamp,
        )


@dataclass
class CalendarAttachment:
    """Represents a calendar event attachment."""
    file_id: str
    filename: str
    mime_type: str
    icon_link: Optional[str] = None
    content: Optional[bytes] = None
    extracted_text: Optional[str] = None


@dataclass
class MeetingContext:
    """
    Complete context gathered for a meeting.

    Contains all relevant information from various sources.
    """
    meeting: Meeting
    emails: list[EnrichedEmail] = field(default_factory=list)
    slack_messages: list[EnrichedSlackMessage] = field(default_factory=list)
    calendar_attachments: list[CalendarAttachment] = field(default_factory=list)
    drive_documents: list[ExtractedDocument] = field(default_factory=list)

    # Context metadata
    gathering_time: datetime = field(default_factory=datetime.utcnow)
    external_attendees: list[str] = field(default_factory=list)
    internal_domain: Optional[str] = None

    # Stats
    total_emails: int = 0
    total_slack_messages: int = 0
    total_documents: int = 0
    errors: list[str] = field(default_factory=list)

    def has_external_attendees(self) -> bool:
        """Check if meeting has external attendees."""
        return len(self.external_attendees) > 0

    def get_all_extracted_documents(self) -> list[ExtractedDocument]:
        """Get all documents extracted from all sources."""
        docs = []

        # From email attachments
        for email in self.emails:
            for attachment in email.attachments:
                if attachment.extracted_text:
                    docs.append(ExtractedDocument(
                        filename=attachment.filename,
                        text_content=attachment.extracted_text,
                        source_type='email_attachment',
                        metadata={
                            'email_subject': email.subject,
                            'email_sender': email.sender,
                            'email_date': email.date.isoformat(),
                        }
                    ))

        # From Slack files
        for msg in self.slack_messages:
            for file in msg.files:
                if file.extracted_text:
                    docs.append(ExtractedDocument(
                        filename=file.name,
                        text_content=file.extracted_text,
                        source_type='slack_file',
                        metadata={
                            'channel': msg.channel,
                            'shared_by': file.shared_by,
                            'timestamp': file.timestamp,
                        }
                    ))

        # From calendar attachments
        for attachment in self.calendar_attachments:
            if attachment.extracted_text:
                docs.append(ExtractedDocument(
                    filename=attachment.filename,
                    text_content=attachment.extracted_text,
                    source_type='calendar_attachment',
                    metadata={
                        'meeting_title': self.meeting.title,
                    }
                ))

        # Direct drive documents
        docs.extend(self.drive_documents)

        return docs


class ContextGatherer:
    """
    Gathers comprehensive context for a meeting from all integrated sources.
    """

    def __init__(
        self,
        gmail_client=None,
        slack_client=None,
        calendar_client=None,
        drive_credentials=None,
        internal_domain: Optional[str] = None,
    ):
        """
        Initialize the context gatherer.

        Args:
            gmail_client: Initialized GmailClient
            slack_client: Initialized SlackClient
            calendar_client: Initialized GoogleCalendarClient
            drive_credentials: Google credentials for Drive API
            internal_domain: Company domain for detecting external attendees
        """
        self.gmail_client = gmail_client
        self.slack_client = slack_client
        self.calendar_client = calendar_client
        self.drive_credentials = drive_credentials
        self.internal_domain = internal_domain

        self.document_processor = DocumentProcessor(drive_credentials)

    async def gather_meeting_context(
        self,
        meeting: Meeting,
        days_back: int = 14,
        include_documents: bool = True,
    ) -> MeetingContext:
        """
        Gather all context for a meeting.

        Args:
            meeting: The meeting to gather context for
            days_back: Number of days to look back for messages/emails
            include_documents: Whether to extract text from attachments

        Returns:
            MeetingContext with all gathered information
        """
        context = MeetingContext(meeting=meeting, internal_domain=self.internal_domain)

        # Identify external attendees
        context.external_attendees = self._identify_external_attendees(meeting.attendees)

        # Gather context from all sources in parallel
        tasks = []

        # Email context
        if self.gmail_client:
            tasks.append(self._gather_email_context(
                meeting.attendees,
                days_back,
                include_documents,
            ))

        # Slack context
        if self.slack_client:
            tasks.append(self._gather_slack_context(
                meeting.attendees,
                days_back,
                include_documents,
                meeting_title=meeting.title,
            ))

        # Calendar attachments
        if self.calendar_client:
            tasks.append(self._gather_calendar_attachments(
                meeting,
                include_documents,
            ))

        # Execute all gathering tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                context.errors.append(f"Gathering error: {result}")
                logger.error(f"Context gathering error: {result}")
            elif isinstance(result, list):
                if tasks and i < len(tasks):
                    task_name = tasks[i].__name__ if hasattr(tasks[i], '__name__') else str(i)

                    # Determine result type by content
                    if result and isinstance(result[0], EnrichedEmail):
                        context.emails = result
                        context.total_emails = len(result)
                    elif result and isinstance(result[0], EnrichedSlackMessage):
                        context.slack_messages = result
                        context.total_slack_messages = len(result)
                    elif result and isinstance(result[0], CalendarAttachment):
                        context.calendar_attachments = result

        # Count total documents
        context.total_documents = len(context.get_all_extracted_documents())

        return context

    def _identify_external_attendees(self, attendees: list[Attendee]) -> list[str]:
        """Identify attendees with external (non-company) email domains."""
        if not self.internal_domain:
            return []

        external = []
        for attendee in attendees:
            email_domain = attendee.email.split('@')[-1].lower()
            if email_domain != self.internal_domain.lower():
                external.append(attendee.email)

        return external

    async def _gather_email_context(
        self,
        attendees: list[Attendee],
        days_back: int,
        include_documents: bool,
    ) -> list[EnrichedEmail]:
        """Gather email context for all attendees."""
        all_emails = []

        for attendee in attendees:
            try:
                emails = await self._get_emails_with_person(
                    attendee.email,
                    days_back,
                    include_documents,
                )
                all_emails.extend(emails)
            except Exception as e:
                logger.error(f"Error gathering emails for {attendee.email}: {e}")

        # Deduplicate by email ID
        seen_ids = set()
        unique_emails = []
        for email in all_emails:
            if email.id not in seen_ids:
                seen_ids.add(email.id)
                unique_emails.append(email)

        # Sort by date (newest first)
        unique_emails.sort(key=lambda e: e.date, reverse=True)

        return unique_emails

    async def _get_emails_with_person(
        self,
        email_address: str,
        days_back: int,
        include_documents: bool,
    ) -> list[EnrichedEmail]:
        """Get emails with a specific person, including attachments."""
        if not self.gmail_client:
            return []

        enriched_emails = []
        service = self.gmail_client.service

        # Build search query
        query = f"(from:{email_address} OR to:{email_address})"

        try:
            # Search for messages
            results = service.users().messages().list(
                userId="me",
                q=query,
                maxResults=20,
            ).execute()

            messages = results.get("messages", [])

            for msg_info in messages:
                try:
                    # Get full message with attachment info
                    message = service.users().messages().get(
                        userId="me",
                        id=msg_info["id"],
                        format="full",
                    ).execute()

                    enriched_email = await self._parse_email_message(
                        message,
                        include_documents,
                    )
                    if enriched_email:
                        enriched_emails.append(enriched_email)

                except Exception as e:
                    logger.error(f"Error parsing email {msg_info['id']}: {e}")

        except Exception as e:
            logger.error(f"Error searching emails: {e}")

        return enriched_emails

    async def _parse_email_message(
        self,
        message: dict,
        include_documents: bool,
    ) -> Optional[EnrichedEmail]:
        """Parse a Gmail message into EnrichedEmail."""
        try:
            headers = {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}

            # Parse date
            date_str = headers.get("Date", "")
            try:
                from email.utils import parsedate_to_datetime
                date = parsedate_to_datetime(date_str)
            except Exception:
                date = datetime.utcnow()

            # Parse recipients
            recipients = []
            to_header = headers.get("To", "")
            for addr in to_header.split(","):
                addr = addr.strip()
                # Extract email from "Name <email>" format
                match = re.search(r'<([^>]+)>', addr)
                if match:
                    recipients.append(match.group(1))
                elif '@' in addr:
                    recipients.append(addr)

            # Extract body
            body_text, body_html = self._extract_email_body(message.get("payload", {}))

            # Extract attachments
            attachments = []
            if include_documents:
                attachments = await self._extract_email_attachments(
                    message["id"],
                    message.get("payload", {}),
                )

            return EnrichedEmail(
                id=message["id"],
                thread_id=message.get("threadId", ""),
                subject=headers.get("Subject", "No Subject"),
                sender=headers.get("From", ""),
                recipients=recipients,
                date=date,
                body_text=body_text,
                body_html=body_html,
                snippet=message.get("snippet", ""),
                attachments=attachments,
                labels=message.get("labelIds", []),
            )

        except Exception as e:
            logger.error(f"Error parsing email message: {e}")
            return None

    def _extract_email_body(self, payload: dict) -> tuple[str, Optional[str]]:
        """Extract plain text and HTML body from email payload."""
        body_text = ""
        body_html = None

        def extract_parts(parts):
            nonlocal body_text, body_html

            for part in parts:
                mime_type = part.get("mimeType", "")
                body_data = part.get("body", {}).get("data")

                if mime_type == "text/plain" and body_data:
                    body_text = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")
                elif mime_type == "text/html" and body_data:
                    body_html = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")
                elif "parts" in part:
                    extract_parts(part["parts"])

        # Handle single-part messages
        if payload.get("body", {}).get("data"):
            mime_type = payload.get("mimeType", "")
            body_data = payload["body"]["data"]
            decoded = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")

            if mime_type == "text/html":
                body_html = decoded
                # Strip HTML tags for plain text
                body_text = re.sub(r'<[^>]+>', '', decoded)
            else:
                body_text = decoded

        # Handle multi-part messages
        if "parts" in payload:
            extract_parts(payload["parts"])

        return body_text, body_html

    async def _extract_email_attachments(
        self,
        message_id: str,
        payload: dict,
    ) -> list[EmailAttachment]:
        """Extract and process attachments from an email."""
        attachments = []
        service = self.gmail_client.service

        def find_attachments(parts):
            for part in parts:
                filename = part.get("filename", "")
                if filename and part.get("body", {}).get("attachmentId"):
                    attachments.append({
                        "filename": filename,
                        "mime_type": part.get("mimeType", ""),
                        "size": part.get("body", {}).get("size", 0),
                        "attachment_id": part["body"]["attachmentId"],
                    })
                if "parts" in part:
                    find_attachments(part["parts"])

        find_attachments(payload.get("parts", []))

        # Download and process attachments
        processed_attachments = []
        for att_info in attachments[:5]:  # Limit to 5 attachments
            try:
                # Download attachment
                attachment = service.users().messages().attachments().get(
                    userId="me",
                    messageId=message_id,
                    id=att_info["attachment_id"],
                ).execute()

                content = base64.urlsafe_b64decode(attachment["data"])

                # Extract text
                extracted = await self.document_processor.extract_from_bytes(
                    content,
                    att_info["filename"],
                    att_info["mime_type"],
                )

                processed_attachments.append(EmailAttachment(
                    filename=att_info["filename"],
                    mime_type=att_info["mime_type"],
                    size=att_info["size"],
                    content=content,
                    extracted_text=extracted.text_content if extracted.success else None,
                ))

            except Exception as e:
                logger.error(f"Error processing attachment {att_info['filename']}: {e}")
                processed_attachments.append(EmailAttachment(
                    filename=att_info["filename"],
                    mime_type=att_info["mime_type"],
                    size=att_info["size"],
                ))

        return processed_attachments

    async def _gather_slack_context(
        self,
        attendees: list[Attendee],
        days_back: int,
        include_documents: bool,
        meeting_title: Optional[str] = None,
    ) -> list[EnrichedSlackMessage]:
        """Gather Slack context for all attendees."""
        all_messages = []

        for attendee in attendees:
            try:
                messages = await self._get_slack_messages_with_person(
                    attendee.email,
                    attendee.name,
                    days_back,
                    include_documents,
                )
                all_messages.extend(messages)
            except Exception as e:
                logger.error(f"Error gathering Slack messages for {attendee.email}: {e}")

            # Also get DMs with this person (conversations.history includes files properly)
            try:
                dm_messages = await self._get_direct_messages_with_files(
                    attendee.email,
                    days_back,
                    include_documents,
                )
                all_messages.extend(dm_messages)
            except Exception as e:
                logger.error(f"Error getting DMs with {attendee.email}: {e}")

        # Also search by meeting title keywords if provided
        if meeting_title:
            try:
                title_messages = await self._search_slack_by_keywords(
                    meeting_title,
                    days_back,
                    include_documents,
                )
                all_messages.extend(title_messages)
            except Exception as e:
                logger.error(f"Error searching Slack by title keywords: {e}")

        # Also fetch recent files separately (search API doesn't always return files)
        if include_documents:
            try:
                file_messages = await self._gather_slack_files(attendees, days_back)
                all_messages.extend(file_messages)
            except Exception as e:
                logger.error(f"Error gathering Slack files: {e}")

        # Deduplicate by timestamp
        seen_ts = set()
        unique_messages = []
        for msg in all_messages:
            if msg.timestamp not in seen_ts:
                seen_ts.add(msg.timestamp)
                unique_messages.append(msg)

        # Sort by timestamp (newest first)
        unique_messages.sort(key=lambda m: float(m.timestamp), reverse=True)

        return unique_messages

    async def _search_slack_by_keywords(
        self,
        meeting_title: str,
        days_back: int,
        include_documents: bool,
    ) -> list[EnrichedSlackMessage]:
        """Search Slack messages by meeting title keywords."""
        if not self.slack_client:
            return []

        enriched_messages = []
        client = self.slack_client.client

        # Extract meaningful keywords from meeting title
        # Remove common words and short words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'can', 'will', 'just', 'should', 'now', 'meeting', 'sync', 'call', 'discussion', 'review', 'update', 'updates', 'weekly', 'daily', 'monthly', 'bi-weekly', 'standup', 'stand-up'}

        words = meeting_title.lower().split()
        keywords = [w.strip('.,!?()[]{}') for w in words if len(w) > 2 and w.lower() not in stop_words]

        # Search for each significant keyword
        for keyword in keywords[:3]:  # Limit to top 3 keywords
            try:
                response = client.search_messages(
                    query=keyword,
                    count=20,
                    sort="timestamp",
                    sort_dir="desc",
                )

                matches = response.get("messages", {}).get("matches", [])

                for match in matches:
                    try:
                        enriched_msg = await self._parse_slack_message(
                            match,
                            include_documents,
                        )
                        if enriched_msg:
                            enriched_messages.append(enriched_msg)
                    except Exception as e:
                        logger.error(f"Error parsing Slack message: {e}")

            except Exception as e:
                logger.error(f"Error searching Slack for keyword '{keyword}': {e}")

        return enriched_messages

    async def _get_slack_messages_with_person(
        self,
        email: str,
        name: Optional[str],
        days_back: int,
        include_documents: bool,
    ) -> list[EnrichedSlackMessage]:
        """Get Slack messages involving a specific person."""
        if not self.slack_client:
            return []

        enriched_messages = []
        client = self.slack_client.client

        # Try to find user by email
        user_id = None
        user_email = email
        try:
            response = client.users_lookupByEmail(email=email)
            user = response.get("user", {})
            user_id = user.get("id")
            name = name or user.get("real_name", user.get("name"))
        except Exception:
            # If email lookup fails, try to extract name from email
            if not name:
                # Extract potential name from email (e.g., "john.doe@..." -> "John Doe")
                email_prefix = email.split('@')[0]
                # Handle common patterns: john.doe, john_doe, johndoe
                potential_name = email_prefix.replace('.', ' ').replace('_', ' ').replace('-', ' ')
                # Remove numbers and clean up
                potential_name = ''.join(c for c in potential_name if not c.isdigit())
                potential_name = potential_name.strip()
                if len(potential_name) >= 2:
                    name = potential_name.title()

        # Search for messages using multiple queries
        search_queries = []

        # Always include the email
        search_queries.append(email)

        # Add name if available
        if name:
            search_queries.append(name)
            # Also try first name only for common mentions like "@Sam"
            first_name = name.split()[0] if name else None
            if first_name and len(first_name) > 2:
                search_queries.append(first_name)

        for query in search_queries:
            try:
                response = client.search_messages(
                    query=query,
                    count=30,
                    sort="timestamp",
                    sort_dir="desc",
                )

                matches = response.get("messages", {}).get("matches", [])

                for match in matches:
                    try:
                        enriched_msg = await self._parse_slack_message(
                            match,
                            include_documents,
                        )
                        if enriched_msg:
                            enriched_msg.user_email = user_email
                            enriched_messages.append(enriched_msg)
                    except Exception as e:
                        logger.error(f"Error parsing Slack message: {e}")

            except Exception as e:
                logger.error(f"Error searching Slack for '{query}': {e}")

        return enriched_messages

    async def _parse_slack_message(
        self,
        match: dict,
        include_documents: bool,
    ) -> Optional[EnrichedSlackMessage]:
        """Parse a Slack search match into EnrichedSlackMessage."""
        try:
            channel_info = match.get("channel", {})
            channel_type = "channel"
            if channel_info.get("is_im"):
                channel_type = "dm"
            elif channel_info.get("is_private") or channel_info.get("is_mpim"):
                channel_type = "group"

            # Extract files
            files = []
            if include_documents and "files" in match:
                files = await self._extract_slack_files(match["files"])

            return EnrichedSlackMessage(
                text=match.get("text", ""),
                user=match.get("username", match.get("user", "Unknown")),
                user_email=None,
                channel=channel_info.get("name", "Unknown"),
                channel_type=channel_type,
                timestamp=match.get("ts", ""),
                thread_ts=match.get("thread_ts"),
                files=files,
                reactions=match.get("reactions", []),
                is_thread_reply=bool(match.get("thread_ts") and match.get("thread_ts") != match.get("ts")),
            )

        except Exception as e:
            logger.error(f"Error parsing Slack message: {e}")
            return None

    async def _extract_slack_files(self, files: list[dict]) -> list[SlackFile]:
        """Extract and process Slack files."""
        processed_files = []

        for file_info in files[:5]:  # Limit to 5 files
            try:
                slack_file = SlackFile(
                    id=file_info.get("id", ""),
                    name=file_info.get("name", "unknown"),
                    filetype=file_info.get("filetype", ""),
                    url_private=file_info.get("url_private", ""),
                    size=file_info.get("size", 0),
                    shared_by=file_info.get("user", ""),
                    timestamp=str(file_info.get("timestamp", "")),
                )

                # Download file if URL available
                if slack_file.url_private:
                    try:
                        import httpx

                        async with httpx.AsyncClient() as http_client:
                            response = await http_client.get(
                                slack_file.url_private,
                                headers={
                                    "Authorization": f"Bearer {self.slack_client.client.token}",
                                },
                                timeout=30,
                            )

                            if response.status_code == 200:
                                content = response.content
                                slack_file.content = content

                                # Extract text
                                extracted = await self.document_processor.extract_from_bytes(
                                    content,
                                    slack_file.name,
                                )
                                if extracted.success:
                                    slack_file.extracted_text = extracted.text_content

                    except Exception as e:
                        logger.error(f"Error downloading Slack file {slack_file.name}: {e}")

                processed_files.append(slack_file)

            except Exception as e:
                logger.error(f"Error processing Slack file: {e}")

        return processed_files

    async def _get_direct_messages_with_files(
        self,
        email: str,
        days_back: int,
        include_documents: bool,
    ) -> list[EnrichedSlackMessage]:
        """
        Get direct messages with a person using conversations.history API.
        This API properly includes file attachments unlike search.messages.
        """
        if not self.slack_client:
            return []

        enriched_messages = []

        try:
            # Use the slack client's get_direct_messages method
            dm_messages = self.slack_client.get_direct_messages(
                user_email=email,
                limit=50,
                days_back=days_back,
            )

            for msg in dm_messages:
                files = []
                if include_documents and msg.get("files"):
                    for file_info in msg["files"][:5]:
                        slack_file = SlackFile(
                            id=file_info.get("id", ""),
                            name=file_info.get("name", "unknown"),
                            filetype=file_info.get("filetype", ""),
                            url_private=file_info.get("url_private", ""),
                            size=file_info.get("size", 0),
                            shared_by=file_info.get("user", ""),
                            timestamp=str(file_info.get("timestamp", "")),
                        )

                        # Download and extract file
                        if slack_file.url_private:
                            try:
                                content = await self.slack_client.download_file(slack_file.url_private)
                                if content:
                                    slack_file.content = content
                                    extracted = await self.document_processor.extract_from_bytes(
                                        content,
                                        slack_file.name,
                                    )
                                    if extracted.success:
                                        slack_file.extracted_text = extracted.text_content
                                        logger.info(f"Successfully extracted text from Slack file: {slack_file.name}")
                            except Exception as e:
                                logger.error(f"Error downloading Slack DM file {slack_file.name}: {e}")

                        files.append(slack_file)

                enriched_messages.append(EnrichedSlackMessage(
                    text=msg.get("text", ""),
                    user=msg.get("user", "Unknown"),
                    user_email=email,
                    channel=msg.get("channel", "direct-message"),
                    channel_type="dm",
                    timestamp=msg.get("timestamp", ""),
                    thread_ts=msg.get("thread_ts"),
                    files=files,
                    reactions=[],
                    is_thread_reply=False,
                ))

        except Exception as e:
            logger.error(f"Error getting DMs with {email}: {e}")

        return enriched_messages

    async def _gather_slack_files(
        self,
        attendees: list[Attendee],
        days_back: int,
    ) -> list[EnrichedSlackMessage]:
        """
        Gather files shared recently using files.list API.
        This catches files that might be missed by search.messages.
        """
        if not self.slack_client:
            return []

        enriched_messages = []
        seen_file_ids = set()

        for attendee in attendees:
            try:
                # List files shared by this user
                files = self.slack_client.list_files(
                    user_email=attendee.email,
                    days_back=days_back,
                    max_files=10,
                )

                for file_info in files:
                    # Skip if already processed
                    if file_info.get("id") in seen_file_ids:
                        continue
                    seen_file_ids.add(file_info.get("id"))

                    slack_file = SlackFile(
                        id=file_info.get("id", ""),
                        name=file_info.get("name", "unknown"),
                        filetype=file_info.get("filetype", ""),
                        url_private=file_info.get("url_private", "") or file_info.get("url_private_download", ""),
                        size=file_info.get("size", 0),
                        shared_by=file_info.get("user", ""),
                        timestamp=str(file_info.get("timestamp", "")),
                    )

                    # Download and extract file
                    if slack_file.url_private:
                        try:
                            content = await self.slack_client.download_file(slack_file.url_private)
                            if content:
                                slack_file.content = content
                                extracted = await self.document_processor.extract_from_bytes(
                                    content,
                                    slack_file.name,
                                )
                                if extracted.success:
                                    slack_file.extracted_text = extracted.text_content
                                    logger.info(f"Successfully extracted text from Slack file (via files.list): {slack_file.name}")
                        except Exception as e:
                            logger.error(f"Error downloading Slack file {slack_file.name}: {e}")

                    # Create a synthetic message for this file
                    enriched_messages.append(EnrichedSlackMessage(
                        text=f"[Shared file: {slack_file.name}]",
                        user=attendee.name or attendee.email.split('@')[0],
                        user_email=attendee.email,
                        channel="file-share",
                        channel_type="channel",
                        timestamp=slack_file.timestamp or str(datetime.utcnow().timestamp()),
                        files=[slack_file],
                        reactions=[],
                        is_thread_reply=False,
                    ))

            except Exception as e:
                logger.error(f"Error listing files for {attendee.email}: {e}")

        return enriched_messages

    async def _gather_calendar_attachments(
        self,
        meeting: Meeting,
        include_documents: bool,
    ) -> list[CalendarAttachment]:
        """Gather attachments from the calendar event."""
        if not self.calendar_client:
            return []

        attachments = []
        service = self.calendar_client.service

        try:
            # Get event with attachments
            event = service.events().get(
                calendarId="primary",
                eventId=meeting.id,
            ).execute()

            event_attachments = event.get("attachments", [])

            for att in event_attachments[:10]:  # Limit to 10 attachments
                try:
                    cal_attachment = CalendarAttachment(
                        file_id=att.get("fileId", ""),
                        filename=att.get("title", "unknown"),
                        mime_type=att.get("mimeType", ""),
                        icon_link=att.get("iconLink"),
                    )

                    # Download and extract if it's a Drive file
                    if include_documents and cal_attachment.file_id and self.drive_credentials:
                        try:
                            content, filename, mime_type = await self.document_processor.download_drive_file(
                                cal_attachment.file_id,
                            )
                            cal_attachment.content = content

                            extracted = await self.document_processor.extract_from_bytes(
                                content,
                                filename,
                                mime_type,
                            )
                            if extracted.success:
                                cal_attachment.extracted_text = extracted.text_content

                        except Exception as e:
                            logger.error(f"Error downloading calendar attachment: {e}")

                    attachments.append(cal_attachment)

                except Exception as e:
                    logger.error(f"Error processing calendar attachment: {e}")

        except Exception as e:
            logger.error(f"Error getting calendar event attachments: {e}")

        return attachments


# ========== Demo Context Gatherer ==========

class DemoContextGatherer:
    """Generate demo context for testing without real API connections."""

    def __init__(self, internal_domain: str = "company.com"):
        self.internal_domain = internal_domain

    async def gather_meeting_context(
        self,
        meeting: Meeting,
        days_back: int = 14,
        include_documents: bool = True,
    ) -> MeetingContext:
        """Generate demo meeting context."""
        context = MeetingContext(
            meeting=meeting,
            internal_domain=self.internal_domain,
        )

        # Identify external attendees
        context.external_attendees = [
            a.email for a in meeting.attendees
            if not a.email.endswith(f"@{self.internal_domain}")
        ]

        # Generate demo emails
        context.emails = self._generate_demo_emails(meeting)
        context.total_emails = len(context.emails)

        # Generate demo Slack messages
        context.slack_messages = self._generate_demo_slack_messages(meeting)
        context.total_slack_messages = len(context.slack_messages)

        # Generate demo attachments for specific meetings
        if "Q4" in meeting.title or "Budget" in meeting.title:
            context.calendar_attachments = self._generate_demo_calendar_attachments()

        context.total_documents = len(context.get_all_extracted_documents())

        return context

    def _generate_demo_emails(self, meeting: Meeting) -> list[EnrichedEmail]:
        """Generate demo emails based on meeting context."""
        emails = []
        now = datetime.utcnow()

        # Email templates based on meeting type
        if "Q4" in meeting.title or "Planning" in meeting.title:
            emails.append(EnrichedEmail(
                id="demo-email-budget-1",
                thread_id="thread-1",
                subject="Q4 Budget Analysis - Action Required",
                sender=meeting.attendees[0].email if meeting.attendees else "sarah@company.com",
                recipients=["you@company.com"],
                date=now - timedelta(days=2),
                body_text="""Hi,

I've completed the Q4 budget analysis. Key findings:

- Total projected revenue: $2.4M (down 8% from Q3)
- Marketing spend needs to increase by 15% to hit targets
- Engineering headcount request: 3 FTEs
- Infrastructure costs trending 20% over budget

The attached spreadsheet has the full breakdown. We should discuss the revenue decline in our meeting - it's concerning given our growth targets.

Can you review before our meeting?

Best,
Sarah""",
                snippet="I've completed the Q4 budget analysis. Key findings: Total projected revenue: $2.4M (down 8% from Q3)...",
                attachments=[
                    EmailAttachment(
                        filename="Q4_Budget_Analysis.xlsx",
                        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        size=45000,
                        extracted_text="""Q4 Budget Analysis
=== Revenue Projections ===
Month | Projected | Actual | Variance
Oct | $800,000 | $720,000 | -10%
Nov | $850,000 | $790,000 | -7%
Dec | $900,000 | TBD | TBD

=== Department Budgets ===
Engineering | $450,000 | Headcount: 12 -> 15 requested
Marketing | $200,000 | Increase needed for Q4 push
Sales | $180,000 | On track
Infrastructure | $120,000 | 20% over due to cloud costs

KEY CONCERNS:
- Revenue trending 8% below Q3
- Cloud infrastructure costs up 35% YoY
- Marketing ROI needs improvement""",
                    ),
                ],
            ))

        # Health-related context email
        if any("1:1" in meeting.title or "Check-in" in meeting.title for _ in [1]):
            emails.append(EnrichedEmail(
                id="demo-email-health-1",
                thread_id="thread-2",
                subject="Re: This week",
                sender=meeting.attendees[0].email if meeting.attendees else "tom@company.com",
                recipients=["you@company.com"],
                date=now - timedelta(days=1),
                body_text="""Hey,

Just wanted to give you a heads up - I've been dealing with some back issues this week and might need to take it easy. Still planning to be in the meeting but might need to keep it shorter if that's okay.

Also, I finished the code review you asked about. Left some comments on the PR.

Thanks for understanding,
Tom""",
                snippet="Just wanted to give you a heads up - I've been dealing with some back issues this week...",
            ))

        # External meeting context
        if meeting.external_attendees if hasattr(meeting, 'external_attendees') else any(
            not a.email.endswith("@company.com") for a in meeting.attendees
        ):
            emails.append(EnrichedEmail(
                id="demo-email-vendor-1",
                thread_id="thread-3",
                subject="Pre-meeting: Demo agenda and requirements",
                sender="john.smith@analyticsplatform.com",
                recipients=["you@company.com"],
                date=now - timedelta(days=3),
                body_text="""Hi,

Looking forward to our demo next week. I've attached our standard requirements checklist and a brief overview of our platform capabilities.

For the demo, I'll cover:
1. Real-time analytics dashboard
2. Custom report builder
3. API integration options
4. Security & compliance features

Please let me know if there are specific features you'd like me to focus on.

Best regards,
John Smith
Senior Solutions Engineer
Analytics Platform Inc.""",
                snippet="Looking forward to our demo next week. I've attached our standard requirements checklist...",
                attachments=[
                    EmailAttachment(
                        filename="Analytics_Platform_Overview.pdf",
                        mime_type="application/pdf",
                        size=2500000,
                        extracted_text="""Analytics Platform - Enterprise Overview

PLATFORM CAPABILITIES:
- Real-time data processing: Up to 1M events/second
- Custom dashboards with 50+ visualization types
- Machine learning insights and anomaly detection
- SOC2 Type II and HIPAA compliant

PRICING TIERS:
- Starter: $500/month (up to 10 users)
- Professional: $2,000/month (up to 50 users)
- Enterprise: Custom pricing

INTEGRATION OPTIONS:
- REST API with full documentation
- Native connectors for Salesforce, HubSpot, Segment
- Webhook support for real-time alerts
- SSO via SAML 2.0 and OAuth 2.0

IMPLEMENTATION TIMELINE:
- Basic setup: 1-2 weeks
- Full integration: 4-6 weeks
- Custom development: 8-12 weeks""",
                    ),
                ],
            ))

        # Follow-up email with action items
        if len(meeting.attendees) > 1:
            attendee_name = meeting.attendees[0].name or "Team"
            emails.append(EnrichedEmail(
                id="demo-email-followup-1",
                thread_id="thread-4",
                subject=f"Re: {meeting.title} - Quick question",
                sender=meeting.attendees[0].email if meeting.attendees else "colleague@company.com",
                recipients=["you@company.com"],
                date=now - timedelta(days=5),
                body_text=f"""Hi,

Quick question before our meeting - did you get a chance to review the proposal I sent last week? I haven't heard back and want to make sure we're aligned before discussing with the broader team.

Also, I noticed the deadline for the roadmap doc is coming up. Can we add that to our agenda?

Thanks,
{attendee_name}""",
                snippet="Quick question before our meeting - did you get a chance to review the proposal I sent last week?...",
            ))

        return emails

    def _generate_demo_slack_messages(self, meeting: Meeting) -> list[EnrichedSlackMessage]:
        """Generate demo Slack messages."""
        messages = []
        now = datetime.utcnow()

        attendee_name = meeting.attendees[0].name if meeting.attendees else "Sarah"
        first_name = attendee_name.split()[0] if attendee_name else "Sarah"

        # Work-related messages
        messages.append(EnrichedSlackMessage(
            text=f"@{first_name} the deployment is blocked - we're waiting on the security review. Can you check with IT?",
            user="Alex Kumar",
            user_email=meeting.attendees[0].email if meeting.attendees else None,
            channel="engineering",
            channel_type="channel",
            timestamp=str((now - timedelta(hours=4)).timestamp()),
        ))

        messages.append(EnrichedSlackMessage(
            text=f"Thanks for the heads up. I'll ping the security team. Also, I need to reschedule our 1:1 this week - dealing with some personal stuff.",
            user=first_name,
            user_email=meeting.attendees[0].email if meeting.attendees else None,
            channel="engineering",
            channel_type="channel",
            timestamp=str((now - timedelta(hours=3, minutes=45)).timestamp()),
        ))

        # Direct message with blocker info
        messages.append(EnrichedSlackMessage(
            text=f"Hey, just between us - I'm pretty stressed about the Q4 targets. The numbers aren't looking great and leadership is pushing hard. Can we talk about this in our meeting?",
            user=first_name,
            user_email=meeting.attendees[0].email if meeting.attendees else None,
            channel="direct-message",
            channel_type="dm",
            timestamp=str((now - timedelta(days=1)).timestamp()),
        ))

        # Commitment mention
        messages.append(EnrichedSlackMessage(
            text=f"I promised to have the API docs ready by Friday. @channel I'll need some review help - who's available?",
            user=first_name,
            user_email=meeting.attendees[0].email if meeting.attendees else None,
            channel="product",
            channel_type="channel",
            timestamp=str((now - timedelta(days=2)).timestamp()),
            files=[
                SlackFile(
                    id="file-1",
                    name="API_Documentation_Draft.md",
                    filetype="md",
                    url_private="",
                    size=15000,
                    extracted_text="""# API Documentation v2.0

## Authentication
All API requests require Bearer token authentication.

## Endpoints

### GET /api/v2/users
Returns list of users with pagination.

### POST /api/v2/analytics/events
Submit analytics events in batch.
- Max batch size: 1000 events
- Rate limit: 10,000 events/minute

## Breaking Changes from v1
- Removed deprecated /api/v1/legacy endpoint
- Changed date format to ISO 8601
- Added required 'source' field to events""",
                ),
            ],
        ))

        # Unanswered question
        messages.append(EnrichedSlackMessage(
            text=f"@you Did you see my question about the database migration timeline? Need to know for capacity planning.",
            user=first_name,
            user_email=meeting.attendees[0].email if meeting.attendees else None,
            channel="engineering",
            channel_type="channel",
            timestamp=str((now - timedelta(days=3)).timestamp()),
        ))

        return messages

    def _generate_demo_calendar_attachments(self) -> list[CalendarAttachment]:
        """Generate demo calendar attachments."""
        return [
            CalendarAttachment(
                file_id="cal-attach-1",
                filename="Q4_Roadmap_2024.pdf",
                mime_type="application/pdf",
                extracted_text="""Q4 2024 Product Roadmap

PRIORITY 1 - MUST SHIP:
- User authentication overhaul (Oct 15)
- Mobile app v2.0 launch (Nov 1)
- Holiday readiness optimizations (Nov 15)

PRIORITY 2 - SHOULD SHIP:
- Analytics dashboard redesign
- API rate limiting improvements
- Customer portal enhancements

KEY MILESTONES:
- Oct 1: Feature freeze for mobile v2.0
- Oct 15: Auth system go-live
- Nov 1: Mobile launch (App Store + Play Store)
- Dec 1: Year-end code freeze

RISKS:
- Mobile app approval process may delay launch
- Auth migration requires 2-hour downtime window
- Team capacity reduced due to PTO in December

RESOURCE ALLOCATION:
- Mobile team: 5 engineers (full-time)
- Backend team: 3 engineers (50% on auth)
- QA team: 2 engineers (shared)""",
            ),
        ]
