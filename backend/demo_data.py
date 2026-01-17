"""Demo data for testing without real API connections."""

from datetime import datetime, timedelta
from models import Meeting, Attendee, Email, SlackMessage


def get_demo_meetings() -> list[Meeting]:
    """Generate demo meetings for the next 7 days."""
    now = datetime.utcnow()

    meetings = [
        Meeting(
            id="demo-meeting-1",
            title="Q4 Planning Review",
            description="Quarterly planning review with leadership team to discuss goals and objectives for Q4.",
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=3),
            attendees=[
                Attendee(email="sarah.chen@company.com", name="Sarah Chen", response_status="accepted"),
                Attendee(email="mike.johnson@company.com", name="Mike Johnson", response_status="accepted"),
                Attendee(email="lisa.wang@company.com", name="Lisa Wang", response_status="tentative"),
            ],
            location="Conference Room A",
            meeting_link="https://meet.google.com/abc-defg-hij",
        ),
        Meeting(
            id="demo-meeting-2",
            title="Product Sync with Engineering",
            description="Weekly sync between product and engineering teams.",
            start_time=now + timedelta(days=1, hours=3),
            end_time=now + timedelta(days=1, hours=4),
            attendees=[
                Attendee(email="alex.kumar@company.com", name="Alex Kumar", response_status="accepted"),
                Attendee(email="emma.davis@company.com", name="Emma Davis", response_status="accepted"),
            ],
            location=None,
            meeting_link="https://meet.google.com/xyz-uvwx-yz",
        ),
        Meeting(
            id="demo-meeting-3",
            title="Customer Success Check-in",
            description="Monthly check-in with the customer success team to review metrics and discuss improvements.",
            start_time=now + timedelta(days=2, hours=5),
            end_time=now + timedelta(days=2, hours=6),
            attendees=[
                Attendee(email="james.wilson@company.com", name="James Wilson", response_status="accepted"),
                Attendee(email="maria.garcia@company.com", name="Maria Garcia", response_status="needsAction"),
            ],
            location="Virtual",
            meeting_link="https://zoom.us/j/123456789",
        ),
        Meeting(
            id="demo-meeting-4",
            title="1:1 with Direct Report",
            description="Weekly 1:1 meeting",
            start_time=now + timedelta(days=3, hours=1),
            end_time=now + timedelta(days=3, hours=1, minutes=30),
            attendees=[
                Attendee(email="tom.anderson@company.com", name="Tom Anderson", response_status="accepted"),
            ],
            location=None,
            meeting_link="https://meet.google.com/one-on-one",
        ),
        Meeting(
            id="demo-meeting-5",
            title="Vendor Demo - Analytics Platform",
            description="Demo of the new analytics platform from potential vendor.",
            start_time=now + timedelta(days=4, hours=4),
            end_time=now + timedelta(days=4, hours=5),
            attendees=[
                Attendee(email="vendor@analyticsplatform.com", name="John Smith (Vendor)", response_status="accepted"),
                Attendee(email="procurement@company.com", name="Procurement Team", response_status="accepted"),
                Attendee(email="it-security@company.com", name="IT Security", response_status="tentative"),
            ],
            location="Virtual",
            meeting_link="https://teams.microsoft.com/demo-link",
        ),
    ]

    return meetings


def get_demo_emails(attendee_email: str) -> list[Email]:
    """Generate demo emails for a given attendee."""
    now = datetime.utcnow()

    base_emails = [
        Email(
            id="email-1",
            subject="Re: Q4 Planning - Initial Thoughts",
            sender=attendee_email,
            recipient="you@company.com",
            snippet="Thanks for sending over the preliminary numbers. I've reviewed the budget allocations and have a few suggestions for the engineering team's requests. I think we should prioritize the infrastructure upgrades given the recent performance issues...",
            date=now - timedelta(days=2),
        ),
        Email(
            id="email-2",
            subject="Meeting Agenda Items",
            sender="you@company.com",
            recipient=attendee_email,
            snippet="Hi, I wanted to share some agenda items for our upcoming meeting. Key topics include: 1) Review of current project status, 2) Discussion of timeline adjustments, 3) Resource allocation for next phase...",
            date=now - timedelta(days=5),
        ),
        Email(
            id="email-3",
            subject="Follow-up: Last Week's Discussion",
            sender=attendee_email,
            recipient="you@company.com",
            snippet="As discussed last week, I've put together the analysis you requested. The data shows some interesting trends that we should discuss. In particular, the customer feedback from the beta program has been overwhelmingly positive...",
            date=now - timedelta(days=7),
        ),
        Email(
            id="email-4",
            subject="Quick Question",
            sender=attendee_email,
            recipient="you@company.com",
            snippet="Hey, quick question - do you have the latest version of the roadmap doc? I want to make sure I'm referencing the right priorities in my presentation next week. Also, are we still targeting the March launch date?",
            date=now - timedelta(days=10),
        ),
    ]

    return base_emails


def get_demo_slack_messages(attendee_email: str) -> list[SlackMessage]:
    """Generate demo Slack messages mentioning the attendee."""
    name = attendee_email.split("@")[0].replace(".", " ").title()

    messages = [
        SlackMessage(
            text=f"Hey @{name}, can you review the PR when you get a chance? It's related to the auth refactoring we discussed.",
            user="Engineering Bot",
            channel="engineering",
            timestamp="1699900000.000001",
        ),
        SlackMessage(
            text=f"Great work on the presentation, {name}! The stakeholders were impressed with the metrics you pulled together.",
            user="Product Lead",
            channel="general",
            timestamp="1699800000.000002",
        ),
        SlackMessage(
            text=f"@{name} The customer called back and they're happy with the resolution. Nice job handling that escalation!",
            user="Support Team",
            channel="customer-success",
            timestamp="1699700000.000003",
        ),
        SlackMessage(
            text=f"Reminder: We need to finalize the Q4 budget by EOD Friday. @{name} please share your team's requests.",
            user="Finance",
            channel="leadership",
            timestamp="1699600000.000004",
        ),
        SlackMessage(
            text=f"The deployment went smoothly. Thanks {name} for coordinating with the DevOps team on the timing.",
            user="Release Manager",
            channel="releases",
            timestamp="1699500000.000005",
        ),
    ]

    return messages


def get_demo_meeting_by_id(meeting_id: str) -> Meeting | None:
    """Get a specific demo meeting by ID."""
    meetings = get_demo_meetings()
    for meeting in meetings:
        if meeting.id == meeting_id:
            return meeting
    return None
