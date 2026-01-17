"""
Enhanced AI Meeting Prep Generator.

Generates comprehensive meeting preparation documents using:
- Filtered context from emails, Slack, documents
- Intelligent insights extraction
- Document analysis with metrics
- External attendee handling
"""

import json
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field
import logging

from openai import OpenAI
from config import get_settings
from models import Meeting
from context_gatherer import MeetingContext, EnrichedEmail, EnrichedSlackMessage
from ai.context_analyzer import FilteredContext, AnalyzedItem, RelevanceTier

settings = get_settings()
logger = logging.getLogger(__name__)


@dataclass
class EnhancedPrepDocument:
    """Enhanced meeting preparation document."""
    meeting_id: str
    generated_at: datetime

    # Main content sections
    context_summary: str
    key_discussion_points: list[dict]  # {point, source, priority}
    relationship_notes: list[str]
    document_insights: list[dict]  # {document, key_findings, metrics}
    suggested_agenda: list[dict]  # {item, duration, priority}
    questions_to_ask: list[str]
    action_items: list[str]
    referenced_sources: list[dict]  # {type, title, link, date}

    # Prep metadata
    context_stats: dict = field(default_factory=dict)
    has_external_attendees: bool = False
    warnings: list[str] = field(default_factory=list)

    # Full markdown for display
    prep_markdown: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'meeting_id': self.meeting_id,
            'generated_at': self.generated_at.isoformat(),
            'context_summary': self.context_summary,
            'key_discussion_points': self.key_discussion_points,
            'relationship_notes': self.relationship_notes,
            'document_insights': self.document_insights,
            'suggested_agenda': self.suggested_agenda,
            'questions_to_ask': self.questions_to_ask,
            'action_items': self.action_items,
            'referenced_sources': self.referenced_sources,
            'context_stats': self.context_stats,
            'has_external_attendees': self.has_external_attendees,
            'warnings': self.warnings,
            'prep_markdown': self.prep_markdown,
        }


class EnhancedPrepGenerator:
    """
    Generate comprehensive meeting prep documents using OpenAI GPT-4.

    Features:
    - Full document analysis with metrics extraction
    - Intelligent context filtering results
    - Relationship dynamics (health, stress, blockers)
    - External attendee handling
    - Structured output with sources
    """

    SYSTEM_PROMPT = """You are an intelligent executive assistant preparing meeting briefs.

CONTEXT ANALYSIS RULES:
1. Analyze all provided context (messages, emails, documents)
2. Identify direct topic relevance and prioritize accordingly
3. Surface relationship dynamics (health concerns, commitments, blockers)
4. Extract key data from documents (numbers, decisions, changes)
5. Note outstanding action items and unanswered questions
6. Identify potential concerns or risks

OUTPUT REQUIREMENTS:
Your response must be valid JSON with this exact structure:
{
    "context_summary": "2-3 sentence executive summary including key document insights",
    "key_discussion_points": [
        {"point": "specific discussion point", "source": "Email/Slack/Document name", "priority": "high/medium/low"}
    ],
    "relationship_notes": [
        "Note about attendee health, availability, stress level, etc."
    ],
    "document_insights": [
        {"document": "filename", "key_findings": "important findings", "metrics": ["$2.4M revenue", "8% decline"]}
    ],
    "suggested_agenda": [
        {"item": "agenda item", "duration": "10 min", "priority": "high/medium/low"}
    ],
    "questions_to_ask": [
        "Specific, actionable question based on context"
    ],
    "action_items": [
        "Outstanding action item with owner if known"
    ],
    "referenced_sources": [
        {"type": "email/slack/document", "title": "source title", "date": "date if available"}
    ],
    "warnings": [
        "Any concerning trends or issues to be aware of"
    ]
}

IMPORTANT GUIDELINES:
- Be SPECIFIC - reference actual conversations, documents, and data
- Include NUMBERS and METRICS from documents when available
- Flag concerning trends (revenue decline, deadline risks, etc.)
- Note any blockers or dependencies that could affect the meeting
- Surface relationship context (someone not feeling well, stressed, etc.)
- Prioritize actionable intelligence over generic summaries
- For external attendee meetings, keep content professional and public-appropriate
"""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the prep generator."""
        self.client = OpenAI(api_key=api_key or settings.openai_api_key)

    def generate_prep(
        self,
        meeting: Meeting,
        filtered_context: FilteredContext,
        has_external_attendees: bool = False,
    ) -> EnhancedPrepDocument:
        """
        Generate a comprehensive meeting prep document.

        Args:
            meeting: The meeting details
            filtered_context: Analyzed and filtered context
            has_external_attendees: Whether meeting has external attendees

        Returns:
            EnhancedPrepDocument with all sections
        """
        # Build the user prompt with all context
        user_prompt = self._build_user_prompt(
            meeting,
            filtered_context,
            has_external_attendees,
        )

        # Call OpenAI API
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=3000,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            data = json.loads(content)

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            # Return fallback document
            return self._generate_fallback(meeting, filtered_context)

        # Build the prep document
        prep = EnhancedPrepDocument(
            meeting_id=meeting.id,
            generated_at=datetime.utcnow(),
            context_summary=data.get('context_summary', ''),
            key_discussion_points=data.get('key_discussion_points', []),
            relationship_notes=data.get('relationship_notes', []),
            document_insights=data.get('document_insights', []),
            suggested_agenda=data.get('suggested_agenda', []),
            questions_to_ask=data.get('questions_to_ask', []),
            action_items=data.get('action_items', []),
            referenced_sources=data.get('referenced_sources', []),
            context_stats={
                'emails_analyzed': len(filtered_context.emails),
                'slack_messages_analyzed': len(filtered_context.slack_messages),
                'documents_analyzed': len(filtered_context.documents),
                'items_included': filtered_context.items_included,
                'items_excluded': filtered_context.items_excluded,
            },
            has_external_attendees=has_external_attendees,
            warnings=data.get('warnings', []),
        )

        # Generate markdown version
        prep.prep_markdown = self._generate_markdown(prep, meeting)

        return prep

    def _build_user_prompt(
        self,
        meeting: Meeting,
        filtered: FilteredContext,
        has_external: bool,
    ) -> str:
        """Build the user prompt with all context."""
        parts = []

        # Meeting details
        parts.append("## MEETING DETAILS")
        parts.append(f"Title: {meeting.title}")
        parts.append(f"Time: {meeting.start_time.strftime('%B %d, %Y at %I:%M %p')}")
        parts.append(f"Duration: {(meeting.end_time - meeting.start_time).seconds // 60} minutes")

        if meeting.description:
            parts.append(f"Description: {meeting.description}")

        # Attendees
        parts.append("\n## ATTENDEES")
        external_list = []
        for attendee in meeting.attendees:
            name = attendee.name or attendee.email
            status = f" ({attendee.response_status})" if attendee.response_status else ""
            parts.append(f"- {name}{status}")

            # Track external
            if not attendee.email.endswith('@company.com'):  # Simplified check
                external_list.append(attendee.email)

        if external_list:
            parts.append(f"\n**External Attendees**: {', '.join(external_list)}")
            parts.append("*Note: Content has been filtered for external attendee appropriateness*")

        # Pre-extracted insights
        if filtered.blockers:
            parts.append("\n## IDENTIFIED BLOCKERS")
            for blocker in filtered.blockers[:5]:
                parts.append(f"- {blocker}")

        if filtered.commitments:
            parts.append("\n## OUTSTANDING COMMITMENTS")
            for commitment in filtered.commitments[:5]:
                parts.append(f"- {commitment}")

        if filtered.unanswered_questions:
            parts.append("\n## UNANSWERED QUESTIONS")
            for question in filtered.unanswered_questions[:5]:
                parts.append(f"- {question}")

        if filtered.health_mentions:
            parts.append("\n## HEALTH/AVAILABILITY CONCERNS")
            for mention in filtered.health_mentions[:3]:
                parts.append(f"- {mention}")

        # Email context
        if filtered.emails:
            parts.append("\n## EMAIL CONTEXT (last 14 days)")
            for analyzed in filtered.emails[:10]:
                email = analyzed.item
                relevance = f"[{analyzed.tier.name}]" if analyzed.tier != RelevanceTier.TIER_4_EXCLUDE else ""
                parts.append(f"\n### {relevance} Email: {email.subject}")
                parts.append(f"From: {email.sender}")
                parts.append(f"Date: {email.date.strftime('%B %d, %Y')}")
                parts.append(f"Content: {email.body_text[:500]}...")

                # Include attachment text
                for att in email.attachments:
                    if att.extracted_text:
                        parts.append(f"\n[Attachment: {att.filename}]")
                        parts.append(att.extracted_text[:1000])

        # Slack context
        if filtered.slack_messages:
            parts.append("\n## SLACK CONTEXT (last 14 days)")
            for analyzed in filtered.slack_messages[:15]:
                msg = analyzed.item
                channel_type = f"(DM)" if msg.channel_type == 'dm' else f"#{msg.channel}"
                flags = f" [{', '.join(analyzed.flags)}]" if analyzed.flags else ""
                parts.append(f"\n- [{msg.user} in {channel_type}]{flags}: {msg.text[:300]}")

                # Include file text
                for file in msg.files:
                    if file.extracted_text:
                        parts.append(f"\n  [File: {file.name}]")
                        parts.append(f"  {file.extracted_text[:500]}")

        # Document excerpts
        if filtered.documents:
            parts.append("\n## DOCUMENT EXCERPTS")
            for doc in filtered.documents[:5]:
                parts.append(f"\n### Document: {doc.filename}")
                parts.append(f"Source: {doc.source_type}")
                parts.append(f"Content Preview:\n{doc.text_content[:1500]}")

                # Include extracted metrics
                if doc.metadata.get('key_metrics'):
                    parts.append(f"Key Metrics: {', '.join(doc.metadata['key_metrics'][:5])}")

        # Document summaries with metrics
        if filtered.document_summaries:
            parts.append("\n## DOCUMENT SUMMARIES")
            for summary in filtered.document_summaries:
                parts.append(f"\n**{summary['filename']}**")
                parts.append(f"- Words: {summary['word_count']}")
                if summary['headings']:
                    parts.append(f"- Sections: {', '.join(summary['headings'][:3])}")
                if summary['key_metrics']:
                    parts.append(f"- Key Metrics: {', '.join(summary['key_metrics'][:5])}")
                parts.append(f"- Preview: {summary['preview']}")

        # Key metrics summary
        if filtered.key_metrics:
            parts.append("\n## KEY METRICS FOUND IN DOCUMENTS")
            for metric in list(set(filtered.key_metrics))[:15]:
                parts.append(f"- {metric}")

        parts.append("\n\nGenerate a comprehensive meeting prep document based on all this context.")
        parts.append("Be specific and reference actual data, conversations, and documents.")
        parts.append("Flag any concerning trends or issues that should be addressed.")

        return "\n".join(parts)

    def _generate_fallback(
        self,
        meeting: Meeting,
        filtered: FilteredContext,
    ) -> EnhancedPrepDocument:
        """Generate a fallback prep document if API fails."""
        attendee_names = [a.name or a.email.split('@')[0] for a in meeting.attendees]

        return EnhancedPrepDocument(
            meeting_id=meeting.id,
            generated_at=datetime.utcnow(),
            context_summary=f"Meeting with {', '.join(attendee_names[:3])}. Context gathering found {filtered.items_included} relevant items.",
            key_discussion_points=[
                {"point": "Review meeting objectives", "source": "Meeting details", "priority": "high"},
            ],
            relationship_notes=[],
            document_insights=[{"document": d.filename, "key_findings": d.get_summary(100), "metrics": []}
                              for d in filtered.documents[:3]],
            suggested_agenda=[
                {"item": "Opening and objectives", "duration": "5 min", "priority": "high"},
                {"item": "Main discussion", "duration": "20 min", "priority": "high"},
                {"item": "Action items and next steps", "duration": "5 min", "priority": "high"},
            ],
            questions_to_ask=filtered.unanswered_questions[:3] if filtered.unanswered_questions else [],
            action_items=filtered.action_items[:5] if filtered.action_items else [],
            referenced_sources=[],
            context_stats={
                'emails_analyzed': len(filtered.emails),
                'slack_messages_analyzed': len(filtered.slack_messages),
                'documents_analyzed': len(filtered.documents),
            },
            warnings=["AI generation failed - showing basic prep document"],
        )

    def _generate_markdown(self, prep: EnhancedPrepDocument, meeting: Meeting) -> str:
        """Generate a formatted markdown version of the prep document."""
        lines = []

        lines.append(f"# Meeting Prep: {meeting.title}")
        lines.append(f"*{meeting.start_time.strftime('%B %d, %Y at %I:%M %p')}*\n")

        # Context Summary
        lines.append("## 📋 Context Summary")
        lines.append(prep.context_summary)
        lines.append("")

        # Key Discussion Points
        if prep.key_discussion_points:
            lines.append("## 💬 Key Discussion Points")
            for point in prep.key_discussion_points:
                priority_emoji = "🔴" if point.get('priority') == 'high' else "🟡" if point.get('priority') == 'medium' else "⚪"
                source = f" *(Source: {point.get('source', 'N/A')})*" if point.get('source') else ""
                lines.append(f"- {priority_emoji} {point['point']}{source}")
            lines.append("")

        # Relationship Notes
        if prep.relationship_notes:
            lines.append("## 🤝 Relationship Notes")
            for note in prep.relationship_notes:
                lines.append(f"- {note}")
            lines.append("")

        # Document Insights
        if prep.document_insights:
            lines.append("## 📄 Document Insights")
            for insight in prep.document_insights:
                lines.append(f"### {insight.get('document', 'Document')}")
                lines.append(f"{insight.get('key_findings', '')}")
                if insight.get('metrics'):
                    lines.append(f"**Key Metrics:** {', '.join(insight['metrics'])}")
                lines.append("")

        # Suggested Agenda
        if prep.suggested_agenda:
            lines.append("## 🎯 Suggested Agenda")
            for item in prep.suggested_agenda:
                priority = "⭐ " if item.get('priority') == 'high' else ""
                duration = f" ({item.get('duration', '')})" if item.get('duration') else ""
                lines.append(f"- {priority}{item['item']}{duration}")
            lines.append("")

        # Questions to Ask
        if prep.questions_to_ask:
            lines.append("## ❓ Questions to Ask")
            for question in prep.questions_to_ask:
                lines.append(f"- {question}")
            lines.append("")

        # Action Items
        if prep.action_items:
            lines.append("## ✅ Outstanding Action Items")
            for item in prep.action_items:
                lines.append(f"- [ ] {item}")
            lines.append("")

        # Warnings
        if prep.warnings:
            lines.append("## ⚠️ Warnings & Concerns")
            for warning in prep.warnings:
                lines.append(f"- {warning}")
            lines.append("")

        # Referenced Sources
        if prep.referenced_sources:
            lines.append("## 📎 Referenced Sources")
            for source in prep.referenced_sources:
                source_type = source.get('type', 'source').title()
                title = source.get('title', 'Unknown')
                date = f" ({source.get('date')})" if source.get('date') else ""
                lines.append(f"- **{source_type}**: {title}{date}")
            lines.append("")

        # Stats
        lines.append("---")
        lines.append(f"*Generated at {prep.generated_at.strftime('%B %d, %Y %I:%M %p')}*")
        if prep.context_stats:
            stats = prep.context_stats
            lines.append(f"*Context: {stats.get('emails_analyzed', 0)} emails, {stats.get('slack_messages_analyzed', 0)} Slack messages, {stats.get('documents_analyzed', 0)} documents analyzed*")

        return "\n".join(lines)


# ========== Demo Prep Generator ==========

class DemoPrepGenerator:
    """Generate demo prep documents without calling OpenAI."""

    def generate_prep(
        self,
        meeting: Meeting,
        filtered_context: FilteredContext,
        has_external_attendees: bool = False,
    ) -> EnhancedPrepDocument:
        """Generate a demo prep document."""
        attendee_names = [a.name or a.email.split('@')[0] for a in meeting.attendees]
        names_str = ", ".join(attendee_names[:2]) if attendee_names else "the team"

        # Build context-aware content
        context_summary = self._build_demo_summary(meeting, filtered_context, has_external_attendees)
        discussion_points = self._build_demo_discussion_points(meeting, filtered_context)
        relationship_notes = self._build_demo_relationship_notes(filtered_context)
        document_insights = self._build_demo_document_insights(filtered_context)
        agenda = self._build_demo_agenda(meeting)
        questions = self._build_demo_questions(filtered_context)

        prep = EnhancedPrepDocument(
            meeting_id=meeting.id,
            generated_at=datetime.utcnow(),
            context_summary=context_summary,
            key_discussion_points=discussion_points,
            relationship_notes=relationship_notes,
            document_insights=document_insights,
            suggested_agenda=agenda,
            questions_to_ask=questions,
            action_items=filtered_context.action_items[:5] if filtered_context.action_items else [
                f"Follow up with {names_str} on discussion items",
                "Send meeting notes to all attendees",
                "Update project tracking with agreed action items",
            ],
            referenced_sources=self._build_demo_sources(filtered_context),
            context_stats={
                'emails_analyzed': len(filtered_context.emails),
                'slack_messages_analyzed': len(filtered_context.slack_messages),
                'documents_analyzed': len(filtered_context.documents),
                'items_included': filtered_context.items_included,
                'items_excluded': filtered_context.items_excluded,
            },
            has_external_attendees=has_external_attendees,
            warnings=self._build_demo_warnings(filtered_context),
        )

        # Generate markdown
        prep.prep_markdown = self._generate_demo_markdown(prep, meeting)

        return prep

    def _build_demo_summary(
        self,
        meeting: Meeting,
        filtered: FilteredContext,
        has_external: bool,
    ) -> str:
        """Build a context-aware demo summary."""
        attendee_names = [a.name or a.email.split('@')[0] for a in meeting.attendees]
        names_str = ", ".join(attendee_names[:2])

        summary_parts = [f"This meeting with {names_str} "]

        # Add document context if available
        if filtered.documents:
            doc_names = [d.filename for d in filtered.documents[:2]]
            summary_parts.append(f"includes attached documents ({', '.join(doc_names)}) ")

        # Add topic-specific context
        if "Q4" in meeting.title or "Budget" in meeting.title:
            summary_parts.append("focuses on Q4 planning and budget review. Analysis of the attached budget spreadsheet shows revenue trending 8% below Q3 targets, with infrastructure costs 20% over budget. Key decisions are needed on engineering headcount and marketing spend increases.")
        elif "1:1" in meeting.title:
            summary_parts.append("is a regular check-in. Recent communications indicate some personal and workload concerns that may be worth discussing.")
        elif "Vendor" in meeting.title or has_external:
            summary_parts.append("is with external participants. Content has been filtered to show only professionally appropriate context. Focus areas include product capabilities, pricing, and implementation timeline.")
        else:
            summary_parts.append(f"appears to be about {meeting.title.lower()}. Recent Slack and email communications show active collaboration on related topics.")

        return "".join(summary_parts)

    def _build_demo_discussion_points(
        self,
        meeting: Meeting,
        filtered: FilteredContext,
    ) -> list[dict]:
        """Build demo discussion points based on context."""
        points = []

        # Add document-based points
        for doc in filtered.documents[:2]:
            if "budget" in doc.filename.lower() or "Q4" in doc.filename:
                points.append({
                    "point": "Revenue is tracking 8% below Q3 - need to discuss mitigation strategies",
                    "source": doc.filename,
                    "priority": "high",
                })
                points.append({
                    "point": "Infrastructure costs are 20% over budget due to cloud spending - review optimization options",
                    "source": doc.filename,
                    "priority": "high",
                })
            elif "roadmap" in doc.filename.lower():
                points.append({
                    "point": "Q4 roadmap shows mobile v2.0 launch on Nov 1 - confirm timeline is still on track",
                    "source": doc.filename,
                    "priority": "high",
                })

        # Add blocker-based points
        for blocker in filtered.blockers[:2]:
            points.append({
                "point": blocker,
                "source": "Slack/Email",
                "priority": "high",
            })

        # Add commitment-based points
        for commitment in filtered.commitments[:2]:
            points.append({
                "point": f"Follow up on: {commitment}",
                "source": "Communications",
                "priority": "medium",
            })

        # Ensure we have some points
        if not points:
            points = [
                {"point": "Review current project status and progress", "source": "Meeting agenda", "priority": "high"},
                {"point": "Discuss any blockers or dependencies", "source": "Team feedback", "priority": "medium"},
                {"point": "Align on priorities for the upcoming period", "source": "Planning cycle", "priority": "medium"},
            ]

        return points[:6]

    def _build_demo_relationship_notes(self, filtered: FilteredContext) -> list[str]:
        """Build relationship notes from filtered context."""
        notes = []

        # Add health mentions
        if filtered.health_mentions:
            notes.append("⚕️ Health/availability concern mentioned in recent communications - may need shorter meeting or rescheduling flexibility")

        # Add stress indicators from Slack DMs
        for analyzed in filtered.slack_messages:
            if hasattr(analyzed, 'flags') and 'stress' in analyzed.flags:
                notes.append("😰 Team member mentioned feeling stressed about Q4 targets - consider discussing workload and support")
                break

        # Default notes
        if not notes:
            notes = [
                "Recent communications show positive collaboration and engagement",
                "No urgent relationship concerns identified",
            ]

        return notes

    def _build_demo_document_insights(self, filtered: FilteredContext) -> list[dict]:
        """Build document insights from filtered context."""
        insights = []

        for doc in filtered.documents[:3]:
            insight = {
                "document": doc.filename,
                "key_findings": "",
                "metrics": [],
            }

            # Parse based on document content
            if "budget" in doc.filename.lower():
                insight["key_findings"] = "Budget analysis shows concerning trends in revenue and infrastructure costs. Engineering headcount increase requested. Marketing ROI needs improvement."
                insight["metrics"] = ["$2.4M projected revenue", "-8% vs Q3", "+20% infra costs", "3 FTE request"]
            elif "roadmap" in doc.filename.lower():
                insight["key_findings"] = "Q4 roadmap includes mobile v2.0 launch, auth overhaul, and holiday optimizations. Key risk: mobile app approval timeline."
                insight["metrics"] = ["Oct 15 auth go-live", "Nov 1 mobile launch", "Dec 1 code freeze"]
            elif "api" in doc.filename.lower():
                insight["key_findings"] = "API documentation v2.0 draft includes breaking changes from v1. Rate limiting improved to 10K events/minute."
                insight["metrics"] = ["1000 max batch size", "10K events/min rate limit"]
            elif "analytics" in doc.filename.lower() or "platform" in doc.filename.lower():
                insight["key_findings"] = "Vendor platform overview shows competitive pricing and strong integration capabilities. SOC2 and HIPAA compliant."
                insight["metrics"] = ["$500-$2000/mo pricing tiers", "1M events/sec capacity", "4-6 week implementation"]
            else:
                insight["key_findings"] = f"Document contains {doc.word_count} words. Review key sections for meeting context."

            insights.append(insight)

        return insights

    def _build_demo_agenda(self, meeting: Meeting) -> list[dict]:
        """Build suggested agenda based on meeting type."""
        duration_minutes = (meeting.end_time - meeting.start_time).seconds // 60

        if "1:1" in meeting.title:
            return [
                {"item": "Check-in and personal updates", "duration": "5 min", "priority": "high"},
                {"item": "Review progress on current work", "duration": "10 min", "priority": "high"},
                {"item": "Discuss blockers and support needed", "duration": "10 min", "priority": "high"},
                {"item": "Career development / feedback", "duration": "5 min", "priority": "medium"},
            ]
        elif "Vendor" in meeting.title or "Demo" in meeting.title:
            return [
                {"item": "Introductions and context", "duration": "5 min", "priority": "high"},
                {"item": "Product demo / presentation", "duration": "20 min", "priority": "high"},
                {"item": "Q&A and technical discussion", "duration": "15 min", "priority": "high"},
                {"item": "Pricing and next steps", "duration": "10 min", "priority": "medium"},
            ]
        elif "Planning" in meeting.title or "Q4" in meeting.title:
            return [
                {"item": "Review current metrics and status", "duration": "10 min", "priority": "high"},
                {"item": "Budget and resource discussion", "duration": "15 min", "priority": "high"},
                {"item": "Priority alignment and trade-offs", "duration": "15 min", "priority": "high"},
                {"item": "Action items and owners", "duration": "10 min", "priority": "high"},
            ]
        else:
            return [
                {"item": "Opening and objectives", "duration": "5 min", "priority": "high"},
                {"item": "Main discussion topics", "duration": f"{duration_minutes - 15} min", "priority": "high"},
                {"item": "Action items and next steps", "duration": "10 min", "priority": "high"},
            ]

    def _build_demo_questions(self, filtered: FilteredContext) -> list[str]:
        """Build questions to ask based on context."""
        questions = []

        # Add unanswered questions from context
        questions.extend(filtered.unanswered_questions[:3])

        # Add document-based questions
        for doc in filtered.documents:
            if "budget" in doc.filename.lower():
                questions.append("What's the mitigation plan for the revenue shortfall?")
                questions.append("Can we reduce infrastructure costs without impacting performance?")
            elif "roadmap" in doc.filename.lower():
                questions.append("Are there any risks to the November 1st mobile launch date?")

        # Ensure we have questions
        if not questions:
            questions = [
                "What are the key blockers we need to address?",
                "Are we on track for our committed deadlines?",
                "What support do you need from me/the team?",
            ]

        return questions[:5]

    def _build_demo_sources(self, filtered: FilteredContext) -> list[dict]:
        """Build referenced sources list."""
        sources = []

        for analyzed in filtered.emails[:3]:
            email = analyzed.item
            sources.append({
                "type": "email",
                "title": email.subject,
                "date": email.date.strftime("%B %d"),
            })

        for analyzed in filtered.slack_messages[:3]:
            msg = analyzed.item
            sources.append({
                "type": "slack",
                "title": f"#{msg.channel} - {msg.user}",
                "date": "Recent",
            })

        for doc in filtered.documents[:3]:
            sources.append({
                "type": "document",
                "title": doc.filename,
                "date": doc.extraction_time.strftime("%B %d") if hasattr(doc, 'extraction_time') else "Attached",
            })

        return sources

    def _build_demo_warnings(self, filtered: FilteredContext) -> list[str]:
        """Build warnings based on context."""
        warnings = []

        # Check for concerning patterns in documents
        for doc in filtered.documents:
            if any(kw in doc.text_content.lower() for kw in ['decline', 'decrease', 'risk', 'delay', 'over budget']):
                warnings.append(f"📉 {doc.filename} contains concerning trends that should be discussed")

        # Check for blockers
        if filtered.blockers:
            warnings.append("🚧 Outstanding blockers may impact project timeline")

        # Check for health concerns
        if filtered.health_mentions:
            warnings.append("👤 Team member availability may be affected - consider meeting flexibility")

        return warnings

    def _generate_demo_markdown(self, prep: EnhancedPrepDocument, meeting: Meeting) -> str:
        """Generate markdown for demo prep."""
        # Reuse the same markdown generator from EnhancedPrepGenerator
        generator = EnhancedPrepGenerator.__new__(EnhancedPrepGenerator)
        return generator._generate_markdown(prep, meeting)
