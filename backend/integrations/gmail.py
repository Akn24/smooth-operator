"""Gmail API client with attachment support."""

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from typing import Optional
from models import Email
from config import get_settings
import base64
import re
from email.utils import parsedate_to_datetime
import logging

logger = logging.getLogger(__name__)


class GmailClient:
    """Client for interacting with Gmail API with full attachment support."""

    def __init__(self, access_token: str, refresh_token: Optional[str] = None):
        settings = get_settings()
        self.credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        )
        self.service = build("gmail", "v1", credentials=self.credentials)

    def search_emails_with_person(
        self,
        email_address: str,
        max_results: int = 10,
        days_back: int = 30,
    ) -> list[Email]:
        """Search for emails involving a specific person."""
        # Build search query for emails from or to the person
        query = f"(from:{email_address} OR to:{email_address})"

        try:
            results = self.service.users().messages().list(
                userId="me",
                q=query,
                maxResults=max_results,
            ).execute()

            messages = results.get("messages", [])
            emails = []

            for msg in messages:
                email = self._get_email_details(msg["id"])
                if email:
                    emails.append(email)

            return emails
        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            return []

    def _get_email_details(self, message_id: str) -> Optional[Email]:
        """Get details for a specific email."""
        try:
            message = self.service.users().messages().get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"],
            ).execute()

            headers = {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}

            # Parse date
            date_str = headers.get("Date", "")
            try:
                date = parsedate_to_datetime(date_str)
            except Exception:
                date = datetime.utcnow()

            return Email(
                id=message_id,
                subject=headers.get("Subject", "No Subject"),
                sender=headers.get("From", ""),
                recipient=headers.get("To", ""),
                snippet=message.get("snippet", ""),
                date=date,
            )
        except Exception as e:
            logger.error(f"Error getting email details: {e}")
            return None

    def get_email_thread(self, thread_id: str) -> list[Email]:
        """Get all emails in a thread."""
        try:
            thread = self.service.users().threads().get(
                userId="me",
                id=thread_id,
            ).execute()

            emails = []
            for message in thread.get("messages", []):
                email = self._get_email_details(message["id"])
                if email:
                    emails.append(email)

            return emails
        except Exception as e:
            logger.error(f"Error getting email thread: {e}")
            return []

    def get_full_email(self, message_id: str) -> Optional[dict]:
        """
        Get full email content including body and attachment metadata.

        Returns dict with:
        - id, thread_id, subject, sender, recipients, date
        - body_text, body_html
        - attachments: list of {filename, mime_type, size, attachment_id}
        """
        try:
            message = self.service.users().messages().get(
                userId="me",
                id=message_id,
                format="full",
            ).execute()

            headers = {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}

            # Parse date
            date_str = headers.get("Date", "")
            try:
                date = parsedate_to_datetime(date_str)
            except Exception:
                date = datetime.utcnow()

            # Parse recipients
            recipients = []
            to_header = headers.get("To", "")
            for addr in to_header.split(","):
                addr = addr.strip()
                match = re.search(r'<([^>]+)>', addr)
                if match:
                    recipients.append(match.group(1))
                elif '@' in addr:
                    recipients.append(addr)

            # Extract body
            body_text, body_html = self._extract_body(message.get("payload", {}))

            # Extract attachment info
            attachments = self._get_attachment_info(message.get("payload", {}))

            return {
                "id": message_id,
                "thread_id": message.get("threadId", ""),
                "subject": headers.get("Subject", "No Subject"),
                "sender": headers.get("From", ""),
                "recipients": recipients,
                "date": date,
                "body_text": body_text,
                "body_html": body_html,
                "snippet": message.get("snippet", ""),
                "attachments": attachments,
                "labels": message.get("labelIds", []),
            }

        except Exception as e:
            logger.error(f"Error getting full email: {e}")
            return None

    def _extract_body(self, payload: dict) -> tuple[str, Optional[str]]:
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

    def _get_attachment_info(self, payload: dict) -> list[dict]:
        """Get metadata for all attachments in an email."""
        attachments = []

        def find_attachments(parts):
            for part in parts:
                filename = part.get("filename", "")
                body = part.get("body", {})

                if filename and body.get("attachmentId"):
                    attachments.append({
                        "filename": filename,
                        "mime_type": part.get("mimeType", ""),
                        "size": body.get("size", 0),
                        "attachment_id": body["attachmentId"],
                    })

                if "parts" in part:
                    find_attachments(part["parts"])

        find_attachments(payload.get("parts", []))
        return attachments

    def download_attachment(self, message_id: str, attachment_id: str) -> Optional[bytes]:
        """
        Download an email attachment.

        Args:
            message_id: The email message ID
            attachment_id: The attachment ID

        Returns:
            Attachment content as bytes, or None on error
        """
        try:
            attachment = self.service.users().messages().attachments().get(
                userId="me",
                messageId=message_id,
                id=attachment_id,
            ).execute()

            data = attachment.get("data")
            if data:
                return base64.urlsafe_b64decode(data)
            return None

        except Exception as e:
            logger.error(f"Error downloading attachment: {e}")
            return None

    def search_emails_with_attachments(
        self,
        email_address: str,
        max_results: int = 10,
        days_back: int = 14,
    ) -> list[dict]:
        """
        Search for emails with attachments involving a specific person.

        Returns list of full email dicts with attachment info.
        """
        # Build query with attachment filter
        date_filter = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y/%m/%d")
        query = f"(from:{email_address} OR to:{email_address}) has:attachment after:{date_filter}"

        try:
            results = self.service.users().messages().list(
                userId="me",
                q=query,
                maxResults=max_results,
            ).execute()

            messages = results.get("messages", [])
            emails_with_attachments = []

            for msg in messages:
                full_email = self.get_full_email(msg["id"])
                if full_email and full_email["attachments"]:
                    emails_with_attachments.append(full_email)

            return emails_with_attachments

        except Exception as e:
            logger.error(f"Error searching emails with attachments: {e}")
            return []

    def search_recent_threads(
        self,
        email_address: str,
        max_threads: int = 5,
        days_back: int = 14,
    ) -> list[list[dict]]:
        """
        Get recent email threads with a person.

        Returns list of threads, where each thread is a list of full email dicts.
        """
        date_filter = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y/%m/%d")
        query = f"(from:{email_address} OR to:{email_address}) after:{date_filter}"

        try:
            results = self.service.users().threads().list(
                userId="me",
                q=query,
                maxResults=max_threads,
            ).execute()

            threads_data = []
            for thread_info in results.get("threads", []):
                thread = self.service.users().threads().get(
                    userId="me",
                    id=thread_info["id"],
                    format="full",
                ).execute()

                thread_emails = []
                for message in thread.get("messages", []):
                    full_email = self._parse_thread_message(message)
                    if full_email:
                        thread_emails.append(full_email)

                if thread_emails:
                    threads_data.append(thread_emails)

            return threads_data

        except Exception as e:
            logger.error(f"Error getting threads: {e}")
            return []

    def _parse_thread_message(self, message: dict) -> Optional[dict]:
        """Parse a message from a thread response."""
        try:
            headers = {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}

            date_str = headers.get("Date", "")
            try:
                date = parsedate_to_datetime(date_str)
            except Exception:
                date = datetime.utcnow()

            body_text, body_html = self._extract_body(message.get("payload", {}))
            attachments = self._get_attachment_info(message.get("payload", {}))

            return {
                "id": message["id"],
                "thread_id": message.get("threadId", ""),
                "subject": headers.get("Subject", "No Subject"),
                "sender": headers.get("From", ""),
                "date": date,
                "body_text": body_text,
                "snippet": message.get("snippet", ""),
                "attachments": attachments,
            }

        except Exception as e:
            logger.error(f"Error parsing thread message: {e}")
            return None
