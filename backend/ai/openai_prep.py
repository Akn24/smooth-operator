from openai import OpenAI
from models import Meeting, Email, SlackMessage, PrepDocument
from datetime import datetime
from config import get_settings
import json

settings = get_settings()


class PrepDocumentGenerator:
    """Generate meeting prep documents using OpenAI GPT-4."""

    def __init__(self, api_key: str | None = None):
        self.client = OpenAI(api_key=api_key or settings.openai_api_key)

    def generate_prep_document(
        self,
        meeting: Meeting,
        emails: list[Email],
        slack_messages: list[SlackMessage],
    ) -> PrepDocument:
        """Generate a comprehensive meeting prep document."""

        # Build context from all sources
        context = self._build_context(meeting, emails, slack_messages)

        # Generate prep document using GPT-4
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert executive assistant helping prepare for meetings.

Your task is to analyze meeting details, recent email communications, and Slack messages to create a comprehensive meeting prep document.

You must respond with valid JSON in exactly this format:
{
    "context_summary": "A 2-3 paragraph summary of the meeting context based on all available information",
    "key_points": ["Array of 3-5 key points to be aware of going into the meeting"],
    "suggested_agenda": ["Array of 3-6 suggested agenda items based on the context"],
    "action_items": ["Array of potential action items or topics to follow up on"]
}

Be specific and actionable. If there's limited context, make reasonable assumptions and note them."""
                },
                {
                    "role": "user",
                    "content": context
                }
            ],
            temperature=0.7,
            max_tokens=2000,
        )

        # Parse the response
        content = response.choices[0].message.content
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # If JSON parsing fails, create a default structure
            data = {
                "context_summary": content,
                "key_points": ["Review meeting details", "Prepare questions"],
                "suggested_agenda": ["Introductions", "Discussion", "Next steps"],
                "action_items": ["Follow up after meeting"],
            }

        return PrepDocument(
            meeting_id=meeting.id,
            context_summary=data.get("context_summary", ""),
            key_points=data.get("key_points", []),
            suggested_agenda=data.get("suggested_agenda", []),
            action_items=data.get("action_items", []),
            generated_at=datetime.utcnow(),
        )

    def _build_context(
        self,
        meeting: Meeting,
        emails: list[Email],
        slack_messages: list[SlackMessage],
    ) -> str:
        """Build a context string from all available information."""

        parts = []

        # Meeting details
        parts.append("## MEETING DETAILS")
        parts.append(f"Title: {meeting.title}")
        parts.append(f"Date/Time: {meeting.start_time.strftime('%B %d, %Y at %I:%M %p')}")
        parts.append(f"Duration: {(meeting.end_time - meeting.start_time).seconds // 60} minutes")

        if meeting.description:
            parts.append(f"Description: {meeting.description}")

        if meeting.location:
            parts.append(f"Location: {meeting.location}")

        # Attendees
        if meeting.attendees:
            parts.append("\n## ATTENDEES")
            for attendee in meeting.attendees:
                name = attendee.name or attendee.email
                status = f" ({attendee.response_status})" if attendee.response_status else ""
                parts.append(f"- {name}{status}")

        # Recent emails
        if emails:
            parts.append("\n## RECENT EMAIL COMMUNICATIONS")
            for email in emails[:5]:  # Limit to 5 most recent
                parts.append(f"\n### Email: {email.subject}")
                parts.append(f"From: {email.sender}")
                parts.append(f"Date: {email.date.strftime('%B %d, %Y')}")
                parts.append(f"Preview: {email.snippet[:300]}...")

        # Slack messages
        if slack_messages:
            parts.append("\n## RECENT SLACK MESSAGES")
            for msg in slack_messages[:10]:  # Limit to 10 messages
                parts.append(f"\n- [{msg.user} in #{msg.channel}]: {msg.text[:200]}")

        # No context available
        if not emails and not slack_messages:
            parts.append("\n## NOTE")
            parts.append("Limited recent communication history available with the attendees.")
            parts.append("Consider reaching out before the meeting to understand the agenda.")

        return "\n".join(parts)


# Demo mode generator with mock data
class DemoGenerator:
    """Generate mock prep documents for demo mode."""

    def generate_prep_document(
        self,
        meeting: Meeting,
        emails: list[Email],
        slack_messages: list[SlackMessage],
    ) -> PrepDocument:
        """Generate a demo prep document without calling OpenAI."""

        attendee_names = [a.name or a.email.split("@")[0] for a in meeting.attendees]
        names_str = ", ".join(attendee_names[:2]) if attendee_names else "the team"

        context_summary = f"""This meeting "{meeting.title}" is scheduled with {names_str}.

Based on recent communications, there has been ongoing discussion about project priorities and upcoming deliverables. The team has been actively collaborating on key initiatives and this meeting appears to be a check-in to align on progress.

Recent Slack activity shows active engagement around the topics likely to be discussed. Email threads indicate follow-up items from previous conversations that may be relevant."""

        key_points = [
            f"Meeting with {len(meeting.attendees)} attendee(s) scheduled for {meeting.start_time.strftime('%B %d')}",
            "Review recent project updates and status",
            "Discuss any blockers or challenges",
            "Align on priorities for the upcoming period",
            "Follow up on action items from previous meetings",
        ]

        suggested_agenda = [
            "Quick round of updates (5 min)",
            "Review progress on current initiatives (10 min)",
            "Discuss blockers and dependencies (10 min)",
            "Align on priorities and next steps (10 min)",
            "Action items and wrap-up (5 min)",
        ]

        action_items = [
            "Send meeting notes after the call",
            "Schedule follow-up if needed",
            "Update project tracking with discussed items",
            "Share relevant documents mentioned in discussion",
        ]

        return PrepDocument(
            meeting_id=meeting.id,
            context_summary=context_summary,
            key_points=key_points,
            suggested_agenda=suggested_agenda,
            action_items=action_items,
            generated_at=datetime.utcnow(),
        )
