"""
Background scheduler for automatic meeting prep generation.

Checks for upcoming meetings and pre-generates prep documents
so they're ready when the user needs them.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
import logging

from config import get_settings
from supabase_client import (
    get_oauth_token,
    get_meeting_prep,
    store_meeting_prep,
    get_all_users_with_google,
)
from integrations import GoogleCalendarClient, GmailClient, SlackClient
from context_gatherer import ContextGatherer
from ai.context_analyzer import analyze_meeting_context
from ai.prep_generator import EnhancedPrepGenerator

logger = logging.getLogger(__name__)
settings = get_settings()


class PrepScheduler:
    """
    Background scheduler that automatically generates meeting prep documents.

    Features:
    - Checks for meetings in the next 24-48 hours
    - Generates prep documents ahead of time
    - Caches results in Supabase
    - Runs periodically (configurable interval)
    """

    def __init__(
        self,
        check_interval_minutes: int = 15,
        lookahead_hours: int = 48,
    ):
        """
        Initialize the scheduler.

        Args:
            check_interval_minutes: How often to check for new meetings
            lookahead_hours: How far ahead to look for meetings
        """
        self.check_interval = check_interval_minutes * 60  # Convert to seconds
        self.lookahead_hours = lookahead_hours
        self.running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the scheduler."""
        if self.running:
            logger.warning("Scheduler already running")
            return

        self.running = True
        logger.info(f"Starting prep scheduler (interval: {self.check_interval}s, lookahead: {self.lookahead_hours}h)")

        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Prep scheduler stopped")

    async def _run_loop(self):
        """Main scheduler loop."""
        while self.running:
            try:
                await self._check_and_generate()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")

            # Wait for next check
            await asyncio.sleep(self.check_interval)

    async def _check_and_generate(self):
        """Check for upcoming meetings and generate prep."""
        logger.info("Checking for meetings needing prep...")

        # Get all users with Google connected
        try:
            users = await get_all_users_with_google()
        except Exception as e:
            logger.error(f"Failed to get users: {e}")
            return

        for user_id in users:
            try:
                await self._process_user(user_id)
            except Exception as e:
                logger.error(f"Error processing user {user_id}: {e}")

    async def _process_user(self, user_id: str):
        """Process meetings for a single user."""
        # Get Google token
        google_token = await get_oauth_token(user_id, "google")
        if not google_token:
            return

        # Get upcoming meetings
        calendar = GoogleCalendarClient(
            google_token.access_token,
            google_token.refresh_token,
        )

        try:
            meetings = calendar.get_meetings_needing_prep(
                hours_ahead=self.lookahead_hours,
            )
        except Exception as e:
            logger.error(f"Failed to get meetings for {user_id}: {e}")
            return

        logger.info(f"Found {len(meetings)} meetings for user {user_id}")

        for meeting in meetings:
            # Check if prep already exists
            existing = await get_meeting_prep(user_id, meeting.id)
            if existing:
                continue

            # Generate prep
            try:
                await self._generate_prep_for_meeting(user_id, meeting)
                logger.info(f"Generated prep for meeting: {meeting.title}")
            except Exception as e:
                logger.error(f"Failed to generate prep for {meeting.id}: {e}")

    async def _generate_prep_for_meeting(self, user_id: str, meeting):
        """Generate and cache prep for a meeting."""
        # Get tokens
        google_token = await get_oauth_token(user_id, "google")
        slack_token = await get_oauth_token(user_id, "slack")

        # Initialize clients
        gmail_client = None
        slack_client = None
        calendar_client = None

        if google_token:
            gmail_client = GmailClient(google_token.access_token, google_token.refresh_token)
            calendar_client = GoogleCalendarClient(google_token.access_token, google_token.refresh_token)

        if slack_token:
            slack_client = SlackClient(slack_token.access_token)

        # Gather context
        gatherer = ContextGatherer(
            gmail_client=gmail_client,
            slack_client=slack_client,
            calendar_client=calendar_client,
            drive_credentials=calendar_client.credentials if calendar_client else None,
        )

        context = await gatherer.gather_meeting_context(
            meeting,
            days_back=14,
            include_documents=True,
        )

        # Filter context
        filtered_context = analyze_meeting_context(context, meeting.title)

        # Generate prep
        generator = EnhancedPrepGenerator()
        prep = generator.generate_prep(
            meeting=meeting,
            filtered_context=filtered_context,
            has_external_attendees=context.has_external_attendees(),
        )

        # Cache result
        await store_meeting_prep(
            user_id=user_id,
            meeting_id=meeting.id,
            prep_document=prep.to_dict(),
        )


async def run_once():
    """Run the scheduler once (for testing or one-off runs)."""
    scheduler = PrepScheduler()
    await scheduler._check_and_generate()


# Entry point for running as standalone script
if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        # Run once and exit
        asyncio.run(run_once())
    else:
        # Run continuous loop
        async def main():
            scheduler = PrepScheduler()
            await scheduler.start()

            # Keep running until interrupted
            try:
                while True:
                    await asyncio.sleep(3600)
            except KeyboardInterrupt:
                await scheduler.stop()

        asyncio.run(main())
