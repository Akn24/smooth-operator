"""Slack API client with file download support."""

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from models import SlackMessage
from typing import Optional
from datetime import datetime, timedelta
import logging
import httpx

logger = logging.getLogger(__name__)


class SlackClient:
    """Client for interacting with Slack API with file support."""

    def __init__(self, access_token: str):
        self.client = WebClient(token=access_token)
        self.token = access_token
        self._user_cache: dict[str, dict] = {}

    def search_messages_mentioning(
        self,
        query: str,
        max_results: int = 20,
    ) -> list[SlackMessage]:
        """Search for messages mentioning a specific term (name or email)."""
        try:
            # Use Slack's search API
            response = self.client.search_messages(
                query=query,
                count=max_results,
                sort="timestamp",
                sort_dir="desc",
            )

            messages = []
            matches = response.get("messages", {}).get("matches", [])

            for match in matches:
                messages.append(SlackMessage(
                    text=match.get("text", ""),
                    user=match.get("username", match.get("user", "Unknown")),
                    channel=match.get("channel", {}).get("name", "Unknown"),
                    timestamp=match.get("ts", ""),
                ))

            return messages
        except SlackApiError as e:
            logger.error(f"Slack API error: {e}")
            return []

    def get_user_info(self, user_id: str) -> Optional[dict]:
        """Get information about a Slack user."""
        if user_id in self._user_cache:
            return self._user_cache[user_id]

        try:
            response = self.client.users_info(user=user_id)
            user = response.get("user", {})
            user_info = {
                "id": user_id,
                "name": user.get("real_name", user.get("name", "Unknown")),
                "email": user.get("profile", {}).get("email"),
                "display_name": user.get("profile", {}).get("display_name"),
                "title": user.get("profile", {}).get("title"),
            }
            self._user_cache[user_id] = user_info
            return user_info
        except SlackApiError:
            return None

    def search_by_email(self, email: str, max_results: int = 20) -> list[SlackMessage]:
        """Search for messages mentioning someone by their email."""
        # First, try to find the user by email to get their name
        try:
            response = self.client.users_lookupByEmail(email=email)
            user = response.get("user", {})
            name = user.get("real_name", user.get("name"))

            # Search by both email and name
            messages = self.search_messages_mentioning(email, max_results // 2)
            if name:
                messages.extend(self.search_messages_mentioning(name, max_results // 2))

            # Deduplicate by timestamp
            seen = set()
            unique_messages = []
            for msg in messages:
                if msg.timestamp not in seen:
                    seen.add(msg.timestamp)
                    unique_messages.append(msg)

            return unique_messages
        except SlackApiError:
            # If we can't find the user, just search by email
            return self.search_messages_mentioning(email, max_results)

    def get_recent_channel_messages(
        self,
        channel_id: str,
        limit: int = 100,
    ) -> list[SlackMessage]:
        """Get recent messages from a channel."""
        try:
            response = self.client.conversations_history(
                channel=channel_id,
                limit=limit,
            )

            messages = []
            for msg in response.get("messages", []):
                user_info = self.get_user_info(msg.get("user", ""))
                messages.append(SlackMessage(
                    text=msg.get("text", ""),
                    user=user_info.get("name", "Unknown") if user_info else "Unknown",
                    channel=channel_id,
                    timestamp=msg.get("ts", ""),
                ))

            return messages
        except SlackApiError as e:
            logger.error(f"Slack API error: {e}")
            return []

    def search_messages_with_files(
        self,
        query: str,
        max_results: int = 30,
    ) -> list[dict]:
        """
        Search for messages with file information.

        Returns list of dicts with message and file details.
        """
        try:
            response = self.client.search_messages(
                query=query,
                count=max_results,
                sort="timestamp",
                sort_dir="desc",
            )

            results = []
            matches = response.get("messages", {}).get("matches", [])

            for match in matches:
                channel_info = match.get("channel", {})
                channel_type = "channel"
                if channel_info.get("is_im"):
                    channel_type = "dm"
                elif channel_info.get("is_private") or channel_info.get("is_mpim"):
                    channel_type = "group"

                # Get user info
                user_id = match.get("user", "")
                user_info = self.get_user_info(user_id) if user_id else None

                result = {
                    "text": match.get("text", ""),
                    "user": match.get("username", user_info.get("name") if user_info else "Unknown"),
                    "user_id": user_id,
                    "user_email": user_info.get("email") if user_info else None,
                    "channel": channel_info.get("name", "Unknown"),
                    "channel_id": channel_info.get("id", ""),
                    "channel_type": channel_type,
                    "timestamp": match.get("ts", ""),
                    "thread_ts": match.get("thread_ts"),
                    "permalink": match.get("permalink", ""),
                    "files": [],
                }

                # Extract file information
                for file in match.get("files", []):
                    result["files"].append({
                        "id": file.get("id", ""),
                        "name": file.get("name", "unknown"),
                        "title": file.get("title", ""),
                        "filetype": file.get("filetype", ""),
                        "mimetype": file.get("mimetype", ""),
                        "url_private": file.get("url_private", ""),
                        "url_private_download": file.get("url_private_download", ""),
                        "size": file.get("size", 0),
                        "user": file.get("user", ""),
                        "timestamp": file.get("timestamp", 0),
                    })

                results.append(result)

            return results

        except SlackApiError as e:
            logger.error(f"Slack API error: {e}")
            return []

    async def download_file(self, url: str) -> Optional[bytes]:
        """
        Download a file from Slack.

        Args:
            url: The url_private or url_private_download of the file

        Returns:
            File content as bytes, or None on error
        """
        if not url:
            return None

        try:
            async with httpx.AsyncClient() as http_client:
                response = await http_client.get(
                    url,
                    headers={"Authorization": f"Bearer {self.token}"},
                    timeout=30,
                    follow_redirects=True,
                )

                if response.status_code == 200:
                    return response.content
                else:
                    logger.error(f"Failed to download file: {response.status_code}")
                    return None

        except Exception as e:
            logger.error(f"Error downloading Slack file: {e}")
            return None

    def download_file_sync(self, url: str) -> Optional[bytes]:
        """
        Synchronous version of file download.

        Args:
            url: The url_private or url_private_download of the file

        Returns:
            File content as bytes, or None on error
        """
        if not url:
            return None

        try:
            import requests

            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=30,
            )

            if response.status_code == 200:
                return response.content
            else:
                logger.error(f"Failed to download file: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error downloading Slack file: {e}")
            return None

    def get_direct_messages(
        self,
        user_email: str,
        limit: int = 50,
        days_back: int = 14,
    ) -> list[dict]:
        """
        Get direct messages with a specific user.

        Args:
            user_email: Email of the user to get DMs with
            limit: Maximum number of messages to retrieve
            days_back: Number of days to look back

        Returns:
            List of message dicts with file info
        """
        try:
            # Find user by email
            response = self.client.users_lookupByEmail(email=user_email)
            user = response.get("user", {})
            user_id = user.get("id")

            if not user_id:
                return []

            # Open or get DM channel
            dm_response = self.client.conversations_open(users=[user_id])
            channel_id = dm_response.get("channel", {}).get("id")

            if not channel_id:
                return []

            # Calculate oldest timestamp
            oldest = (datetime.utcnow() - timedelta(days=days_back)).timestamp()

            # Get messages
            history_response = self.client.conversations_history(
                channel=channel_id,
                limit=limit,
                oldest=str(oldest),
            )

            messages = []
            for msg in history_response.get("messages", []):
                # Get sender info
                sender_id = msg.get("user", "")
                sender_info = self.get_user_info(sender_id) if sender_id else None

                message = {
                    "text": msg.get("text", ""),
                    "user": sender_info.get("name") if sender_info else "Unknown",
                    "user_id": sender_id,
                    "channel": "direct-message",
                    "channel_type": "dm",
                    "timestamp": msg.get("ts", ""),
                    "thread_ts": msg.get("thread_ts"),
                    "files": [],
                }

                # Extract files
                for file in msg.get("files", []):
                    message["files"].append({
                        "id": file.get("id", ""),
                        "name": file.get("name", "unknown"),
                        "filetype": file.get("filetype", ""),
                        "url_private": file.get("url_private", ""),
                        "size": file.get("size", 0),
                    })

                messages.append(message)

            return messages

        except SlackApiError as e:
            logger.error(f"Error getting DMs: {e}")
            return []

    def list_files(
        self,
        user_email: Optional[str] = None,
        channel_id: Optional[str] = None,
        days_back: int = 14,
        max_files: int = 20,
    ) -> list[dict]:
        """
        List files shared by or with a user.

        Args:
            user_email: Filter by user email
            channel_id: Filter by channel
            days_back: Number of days to look back
            max_files: Maximum files to return

        Returns:
            List of file metadata dicts
        """
        try:
            params = {
                "count": max_files,
                "ts_from": str((datetime.utcnow() - timedelta(days=days_back)).timestamp()),
            }

            # Add user filter if provided
            if user_email:
                try:
                    response = self.client.users_lookupByEmail(email=user_email)
                    user_id = response.get("user", {}).get("id")
                    if user_id:
                        params["user"] = user_id
                except SlackApiError:
                    pass

            # Add channel filter if provided
            if channel_id:
                params["channel"] = channel_id

            response = self.client.files_list(**params)

            files = []
            for file in response.get("files", []):
                files.append({
                    "id": file.get("id", ""),
                    "name": file.get("name", "unknown"),
                    "title": file.get("title", ""),
                    "filetype": file.get("filetype", ""),
                    "mimetype": file.get("mimetype", ""),
                    "url_private": file.get("url_private", ""),
                    "url_private_download": file.get("url_private_download", ""),
                    "size": file.get("size", 0),
                    "user": file.get("user", ""),
                    "timestamp": file.get("timestamp", 0),
                    "channels": file.get("channels", []),
                    "ims": file.get("ims", []),
                })

            return files

        except SlackApiError as e:
            logger.error(f"Error listing files: {e}")
            return []

    def get_user_by_email(self, email: str) -> Optional[dict]:
        """Get Slack user info by email."""
        try:
            response = self.client.users_lookupByEmail(email=email)
            user = response.get("user", {})
            return {
                "id": user.get("id"),
                "name": user.get("real_name", user.get("name")),
                "email": user.get("profile", {}).get("email"),
                "display_name": user.get("profile", {}).get("display_name"),
                "title": user.get("profile", {}).get("title"),
            }
        except SlackApiError:
            return None
