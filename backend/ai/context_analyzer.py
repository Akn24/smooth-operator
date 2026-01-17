"""
Intelligent Context Analyzer for Meeting Preparation.

Implements smart filtering logic with tiered relevance:
- TIER 1: Always include (directly meeting-related)
- TIER 2: Include if relevant to meeting dynamics
- TIER 3: Include if recent and work-related
- TIER 4: Exclude (social, unrelated, old)

Special handling for external attendees.
"""

import re
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import logging

from context_gatherer import (
    MeetingContext,
    EnrichedEmail,
    EnrichedSlackMessage,
)
from document_processor import ExtractedDocument

logger = logging.getLogger(__name__)


class RelevanceTier(Enum):
    """Context relevance tiers."""
    TIER_1_CRITICAL = 1  # Always include
    TIER_2_DYNAMICS = 2  # Relationship/meeting dynamics
    TIER_3_GENERAL = 3  # Recent work-related
    TIER_4_EXCLUDE = 4  # Exclude


@dataclass
class AnalyzedItem:
    """An item that has been analyzed for relevance."""
    item: any
    tier: RelevanceTier
    relevance_score: float  # 0.0 to 1.0
    reasons: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)  # 'health', 'blocker', 'commitment', etc.
    is_sensitive: bool = False  # Should be filtered for external meetings


@dataclass
class FilteredContext:
    """Context after intelligent filtering."""
    emails: list[AnalyzedItem]
    slack_messages: list[AnalyzedItem]
    documents: list[ExtractedDocument]

    # Extracted insights
    action_items: list[str] = field(default_factory=list)
    commitments: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    unanswered_questions: list[str] = field(default_factory=list)
    health_mentions: list[str] = field(default_factory=list)
    relationship_notes: list[str] = field(default_factory=list)

    # Document insights
    key_metrics: list[str] = field(default_factory=list)
    document_summaries: list[dict] = field(default_factory=list)

    # Stats
    total_items_analyzed: int = 0
    items_included: int = 0
    items_excluded: int = 0


class ContextAnalyzer:
    """
    Analyzes and filters context for meeting preparation.

    Implements intelligent filtering based on:
    - Topic relevance
    - Meeting dynamics (health, stress, blockers)
    - Recency
    - External attendee handling
    """

    # Keywords for different categories
    HEALTH_KEYWORDS = [
        'sick', 'ill', 'not feeling well', 'under the weather',
        'doctor', 'appointment', 'medical', 'health issue',
        'back pain', 'migraine', 'headache', 'tired', 'exhausted',
        'mental health', 'stress', 'burned out', 'burnout',
        'taking time off', 'pto', 'personal day', 'family emergency',
    ]

    BLOCKER_KEYWORDS = [
        'blocked', 'blocker', 'blocking', 'stuck', 'waiting on',
        'dependency', 'depends on', 'can\'t proceed', 'need approval',
        'delayed', 'hold', 'on hold', 'postponed', 'issue with',
        'problem with', 'failing', 'broken', 'down', 'outage',
    ]

    COMMITMENT_KEYWORDS = [
        'i will', 'i\'ll', 'i promise', 'committed to', 'by friday',
        'by monday', 'by end of', 'deadline', 'due date', 'deliver',
        'ship', 'complete', 'finish', 'send you', 'get back to you',
        'follow up', 'action item', 'todo', 'to do', 'assigned to me',
    ]

    QUESTION_KEYWORDS = [
        'can you', 'could you', 'would you', 'did you', 'have you',
        '?', 'question', 'asking', 'wondering', 'thoughts on',
        'opinion on', 'what do you think', 'feedback on', 'review',
    ]

    SOCIAL_KEYWORDS = [
        'weekend', 'holiday', 'vacation', 'party', 'birthday',
        'lunch', 'coffee', 'happy hour', 'how are you', 'how\'s it going',
        'congratulations', 'congrats', 'thanks for', 'thank you for',
        'great job', 'awesome', 'nice work', 'well done',
    ]

    SENSITIVE_KEYWORDS = [
        'confidential', 'internal only', 'do not share', 'private',
        'salary', 'compensation', 'performance review', 'pip',
        'termination', 'layoff', 'restructuring', 'acquisition',
        'legal', 'lawsuit', 'complaint', 'hr issue', 'investigation',
        'between us', 'off the record', 'don\'t tell', 'secret',
    ]

    def __init__(
        self,
        meeting_topic: Optional[str] = None,
        attendee_names: Optional[list[str]] = None,
        external_attendees: Optional[list[str]] = None,
        internal_domain: Optional[str] = None,
    ):
        """
        Initialize the context analyzer.

        Args:
            meeting_topic: The meeting title/topic for relevance matching
            attendee_names: Names of meeting attendees
            external_attendees: Email addresses of external attendees
            internal_domain: Company domain
        """
        self.meeting_topic = meeting_topic or ""
        self.attendee_names = attendee_names or []
        self.external_attendees = external_attendees or []
        self.internal_domain = internal_domain
        self.has_external_attendees = len(self.external_attendees) > 0

        # Extract keywords from meeting topic
        self.topic_keywords = self._extract_topic_keywords(self.meeting_topic)

    def _extract_topic_keywords(self, topic: str) -> list[str]:
        """Extract keywords from meeting topic for relevance matching."""
        # Remove common words
        stop_words = {
            'meeting', 'sync', 'review', 'discussion', 'call', 'chat',
            'with', 'the', 'a', 'an', 'and', 'or', 'for', 'to', 'of',
            'in', 'on', 'at', 'by', 're', 'about', 'weekly', 'monthly',
            'daily', 'quarterly', 'annual', 'team', '1:1', 'one-on-one',
        }

        words = re.findall(r'\b\w+\b', topic.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        return keywords

    def analyze_context(self, context: MeetingContext) -> FilteredContext:
        """
        Analyze and filter the gathered context.

        Args:
            context: Raw MeetingContext from gatherer

        Returns:
            FilteredContext with intelligent filtering applied
        """
        filtered = FilteredContext(
            emails=[],
            slack_messages=[],
            documents=[],
        )

        # Analyze emails
        for email in context.emails:
            analyzed = self._analyze_email(email)
            filtered.total_items_analyzed += 1

            if analyzed.tier != RelevanceTier.TIER_4_EXCLUDE:
                # Apply external attendee filter
                if self.has_external_attendees and analyzed.is_sensitive:
                    continue

                filtered.emails.append(analyzed)
                filtered.items_included += 1

                # Extract insights
                self._extract_insights(analyzed, filtered)
            else:
                filtered.items_excluded += 1

        # Analyze Slack messages
        for msg in context.slack_messages:
            analyzed = self._analyze_slack_message(msg)
            filtered.total_items_analyzed += 1

            if analyzed.tier != RelevanceTier.TIER_4_EXCLUDE:
                if self.has_external_attendees and analyzed.is_sensitive:
                    continue

                filtered.slack_messages.append(analyzed)
                filtered.items_included += 1

                self._extract_insights(analyzed, filtered)
            else:
                filtered.items_excluded += 1

        # Process documents
        for doc in context.get_all_extracted_documents():
            if self.has_external_attendees:
                # Check for sensitive content in documents
                if self._is_sensitive_document(doc):
                    continue

            filtered.documents.append(doc)

            # Extract document insights
            self._extract_document_insights(doc, filtered)

        # Sort by relevance
        filtered.emails.sort(key=lambda x: (x.tier.value, -x.relevance_score))
        filtered.slack_messages.sort(key=lambda x: (x.tier.value, -x.relevance_score))

        # Deduplicate insights
        filtered.action_items = list(dict.fromkeys(filtered.action_items))
        filtered.commitments = list(dict.fromkeys(filtered.commitments))
        filtered.blockers = list(dict.fromkeys(filtered.blockers))
        filtered.unanswered_questions = list(dict.fromkeys(filtered.unanswered_questions))

        return filtered

    def _analyze_email(self, email: EnrichedEmail) -> AnalyzedItem:
        """Analyze an email for relevance."""
        text = f"{email.subject} {email.body_text}".lower()
        reasons = []
        flags = []
        tier = RelevanceTier.TIER_4_EXCLUDE
        score = 0.0

        # TIER 1: Direct meeting relevance
        if self._matches_meeting_topic(text):
            tier = RelevanceTier.TIER_1_CRITICAL
            score = 0.9
            reasons.append("Directly mentions meeting topic")

        # Check for attachments
        if email.attachments:
            tier = min(tier, RelevanceTier.TIER_1_CRITICAL, key=lambda t: t.value)
            score = max(score, 0.85)
            reasons.append(f"Has {len(email.attachments)} attachment(s)")

        # Document references
        if self._has_document_reference(text):
            tier = min(tier, RelevanceTier.TIER_1_CRITICAL, key=lambda t: t.value)
            score = max(score, 0.8)
            reasons.append("References shared document")

        # Action items
        if self._has_action_items(text):
            tier = min(tier, RelevanceTier.TIER_1_CRITICAL, key=lambda t: t.value)
            score = max(score, 0.85)
            reasons.append("Contains action items")
            flags.append("action_item")

        # TIER 2: Meeting dynamics
        if self._mentions_health(text):
            tier = min(tier, RelevanceTier.TIER_2_DYNAMICS, key=lambda t: t.value)
            score = max(score, 0.75)
            reasons.append("Mentions health/availability")
            flags.append("health")

        if self._mentions_blocker(text):
            tier = min(tier, RelevanceTier.TIER_2_DYNAMICS, key=lambda t: t.value)
            score = max(score, 0.8)
            reasons.append("Mentions blocker/dependency")
            flags.append("blocker")

        if self._mentions_commitment(text):
            tier = min(tier, RelevanceTier.TIER_2_DYNAMICS, key=lambda t: t.value)
            score = max(score, 0.75)
            reasons.append("Contains commitment/promise")
            flags.append("commitment")

        if self._has_unanswered_question(text):
            tier = min(tier, RelevanceTier.TIER_2_DYNAMICS, key=lambda t: t.value)
            score = max(score, 0.7)
            reasons.append("Contains unanswered question")
            flags.append("question")

        # TIER 3: Recent work-related
        days_old = (datetime.utcnow() - email.date).days
        if days_old <= 7 and tier == RelevanceTier.TIER_4_EXCLUDE:
            # Check if it's work-related (not purely social)
            if not self._is_purely_social(text):
                tier = RelevanceTier.TIER_3_GENERAL
                score = max(score, 0.5 - (days_old * 0.05))
                reasons.append(f"Recent work discussion ({days_old} days ago)")

        # Check for sensitive content
        is_sensitive = self._is_sensitive_content(text)

        # Exclude old non-relevant content
        if days_old > 14 and tier.value > RelevanceTier.TIER_1_CRITICAL.value:
            tier = RelevanceTier.TIER_4_EXCLUDE
            reasons.append("Too old (>14 days)")

        return AnalyzedItem(
            item=email,
            tier=tier,
            relevance_score=score,
            reasons=reasons,
            flags=flags,
            is_sensitive=is_sensitive,
        )

    def _analyze_slack_message(self, msg: EnrichedSlackMessage) -> AnalyzedItem:
        """Analyze a Slack message for relevance."""
        text = msg.text.lower()
        reasons = []
        flags = []
        tier = RelevanceTier.TIER_4_EXCLUDE
        score = 0.0

        # TIER 1: Direct meeting relevance
        if self._matches_meeting_topic(text):
            tier = RelevanceTier.TIER_1_CRITICAL
            score = 0.9
            reasons.append("Directly mentions meeting topic")

        # Check for files
        if msg.files:
            tier = min(tier, RelevanceTier.TIER_1_CRITICAL, key=lambda t: t.value)
            score = max(score, 0.85)
            reasons.append(f"Shared {len(msg.files)} file(s)")

        # Document references
        if self._has_document_reference(text):
            tier = min(tier, RelevanceTier.TIER_1_CRITICAL, key=lambda t: t.value)
            score = max(score, 0.8)
            reasons.append("References shared document")

        # Direct messages carry more weight
        if msg.channel_type == 'dm':
            score = min(score + 0.1, 1.0)
            reasons.append("Direct message")

        # TIER 2: Meeting dynamics
        if self._mentions_health(text):
            tier = min(tier, RelevanceTier.TIER_2_DYNAMICS, key=lambda t: t.value)
            score = max(score, 0.75)
            reasons.append("Mentions health/availability")
            flags.append("health")

        if self._mentions_blocker(text):
            tier = min(tier, RelevanceTier.TIER_2_DYNAMICS, key=lambda t: t.value)
            score = max(score, 0.8)
            reasons.append("Mentions blocker")
            flags.append("blocker")

        if self._mentions_commitment(text):
            tier = min(tier, RelevanceTier.TIER_2_DYNAMICS, key=lambda t: t.value)
            score = max(score, 0.75)
            reasons.append("Contains commitment")
            flags.append("commitment")

        if self._has_unanswered_question(text):
            tier = min(tier, RelevanceTier.TIER_2_DYNAMICS, key=lambda t: t.value)
            score = max(score, 0.7)
            reasons.append("Contains question directed at you")
            flags.append("question")

        # Mentions of stress/workload
        if self._mentions_stress(text):
            tier = min(tier, RelevanceTier.TIER_2_DYNAMICS, key=lambda t: t.value)
            score = max(score, 0.7)
            reasons.append("Mentions stress/workload concern")
            flags.append("stress")

        # TIER 3: Recent work discussion
        try:
            msg_time = datetime.fromtimestamp(float(msg.timestamp))
            days_old = (datetime.utcnow() - msg_time).days
        except (ValueError, TypeError):
            days_old = 0

        if days_old <= 7 and tier == RelevanceTier.TIER_4_EXCLUDE:
            if not self._is_purely_social(text):
                tier = RelevanceTier.TIER_3_GENERAL
                score = max(score, 0.5 - (days_old * 0.05))
                reasons.append(f"Recent work message ({days_old} days ago)")

        # Check for sensitive content
        is_sensitive = self._is_sensitive_content(text) or msg.channel_type == 'dm'

        # Exclude old content
        if days_old > 14 and tier.value > RelevanceTier.TIER_1_CRITICAL.value:
            tier = RelevanceTier.TIER_4_EXCLUDE

        return AnalyzedItem(
            item=msg,
            tier=tier,
            relevance_score=score,
            reasons=reasons,
            flags=flags,
            is_sensitive=is_sensitive,
        )

    def _matches_meeting_topic(self, text: str) -> bool:
        """Check if text matches meeting topic keywords."""
        if not self.topic_keywords:
            return False

        text_lower = text.lower()
        matches = sum(1 for kw in self.topic_keywords if kw in text_lower)
        return matches >= min(2, len(self.topic_keywords))

    def _has_document_reference(self, text: str) -> bool:
        """Check if text references a shared document."""
        patterns = [
            r'see the (doc|document|spreadsheet|slides|deck|file)',
            r'attached (is|are|the)',
            r'check out the',
            r'i\'ve shared',
            r'link to the',
            r'google doc',
            r'confluence',
            r'notion page',
            r'\.pdf|\.docx|\.xlsx|\.pptx',
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    def _has_action_items(self, text: str) -> bool:
        """Check if text contains action items."""
        patterns = [
            r'action item',
            r'todo:',
            r'to-do:',
            r'follow up on',
            r'need to',
            r'please (do|complete|finish|review|check)',
            r'can you (please )?',
            r'by (monday|tuesday|wednesday|thursday|friday|eod|eow)',
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    def _mentions_health(self, text: str) -> bool:
        """Check if text mentions health/availability issues."""
        return any(kw in text.lower() for kw in self.HEALTH_KEYWORDS)

    def _mentions_blocker(self, text: str) -> bool:
        """Check if text mentions blockers/dependencies."""
        return any(kw in text.lower() for kw in self.BLOCKER_KEYWORDS)

    def _mentions_commitment(self, text: str) -> bool:
        """Check if text contains commitments/promises."""
        return any(kw in text.lower() for kw in self.COMMITMENT_KEYWORDS)

    def _mentions_stress(self, text: str) -> bool:
        """Check if text mentions stress or workload concerns."""
        patterns = [
            r'stressed', r'overwhelmed', r'too much', r'overloaded',
            r'bandwidth', r'capacity', r'spread thin', r'behind on',
            r'catching up', r'falling behind', r'concerned about',
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    def _has_unanswered_question(self, text: str) -> bool:
        """Check if text contains an unanswered question."""
        # Look for questions directed at the user
        patterns = [
            r'\?$',  # Ends with question mark
            r'@you',
            r'did you',
            r'can you',
            r'could you',
            r'would you',
            r'thoughts\?',
            r'opinion\?',
            r'feedback\?',
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    def _is_purely_social(self, text: str) -> bool:
        """Check if text is purely social (not work-related)."""
        social_count = sum(1 for kw in self.SOCIAL_KEYWORDS if kw in text.lower())
        work_indicators = [
            'project', 'deadline', 'task', 'work', 'meeting', 'review',
            'code', 'bug', 'feature', 'release', 'deploy', 'sprint',
            'ticket', 'issue', 'pr', 'pull request', 'commit',
        ]
        work_count = sum(1 for kw in work_indicators if kw in text.lower())

        return social_count > work_count and work_count == 0

    def _is_sensitive_content(self, text: str) -> bool:
        """Check if content is sensitive and should be filtered for external meetings."""
        return any(kw in text.lower() for kw in self.SENSITIVE_KEYWORDS)

    def _is_sensitive_document(self, doc: ExtractedDocument) -> bool:
        """Check if a document contains sensitive content."""
        text = (doc.text_content + doc.filename).lower()
        return self._is_sensitive_content(text)

    def _extract_insights(self, analyzed: AnalyzedItem, filtered: FilteredContext):
        """Extract actionable insights from analyzed item."""
        if isinstance(analyzed.item, EnrichedEmail):
            text = analyzed.item.body_text
            source = f"Email: {analyzed.item.subject}"
        else:
            text = analyzed.item.text
            source = f"Slack #{analyzed.item.channel}"

        # Extract based on flags
        if 'action_item' in analyzed.flags:
            # Try to extract the actual action item
            lines = text.split('\n')
            for line in lines:
                if any(kw in line.lower() for kw in ['action:', 'todo:', 'need to', 'please']):
                    filtered.action_items.append(f"{line.strip()} (from {source})")
                    break

        if 'commitment' in analyzed.flags:
            # Extract commitment
            patterns = [
                r"(i(?:'ll| will)[^.!?]+[.!?])",
                r"(by (?:friday|monday|tuesday|wednesday|thursday|eod|eow)[^.!?]*[.!?]?)",
            ]
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches[:1]:  # Take first match
                    filtered.commitments.append(f"{match.strip()} (from {source})")

        if 'blocker' in analyzed.flags:
            # Extract blocker description
            patterns = [
                r"(blocked[^.!?]+[.!?])",
                r"(waiting on[^.!?]+[.!?])",
                r"(can't proceed[^.!?]+[.!?])",
            ]
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches[:1]:
                    filtered.blockers.append(f"{match.strip()} (from {source})")

        if 'question' in analyzed.flags:
            # Extract unanswered question
            sentences = re.split(r'[.!?]', text)
            for sentence in sentences:
                if '?' in sentence or any(kw in sentence.lower() for kw in ['can you', 'could you', 'did you']):
                    filtered.unanswered_questions.append(f"{sentence.strip()}? (from {source})")
                    break

        if 'health' in analyzed.flags:
            # Extract health mention
            for kw in self.HEALTH_KEYWORDS:
                if kw in text.lower():
                    idx = text.lower().find(kw)
                    start = max(0, idx - 50)
                    end = min(len(text), idx + len(kw) + 100)
                    snippet = text[start:end].strip()
                    filtered.health_mentions.append(f"...{snippet}... (from {source})")
                    break

    def _extract_document_insights(self, doc: ExtractedDocument, filtered: FilteredContext):
        """Extract insights from documents."""
        from document_processor import extract_key_metrics, extract_document_structure

        # Extract key metrics
        metrics = extract_key_metrics(doc.text_content)
        filtered.key_metrics.extend(metrics)

        # Create document summary
        structure = extract_document_structure(doc.text_content)
        summary = {
            'filename': doc.filename,
            'source_type': doc.source_type,
            'word_count': doc.word_count,
            'headings': structure['headings'][:5],
            'has_tables': structure['tables'] > 0,
            'key_metrics': metrics[:5],
            'preview': doc.get_summary(200),
        }
        filtered.document_summaries.append(summary)


def analyze_meeting_context(
    context: MeetingContext,
    meeting_topic: str,
) -> FilteredContext:
    """
    Convenience function to analyze meeting context.

    Args:
        context: The gathered MeetingContext
        meeting_topic: Meeting title/topic

    Returns:
        FilteredContext with intelligent filtering applied
    """
    attendee_names = [
        a.name or a.email.split('@')[0]
        for a in context.meeting.attendees
    ]

    analyzer = ContextAnalyzer(
        meeting_topic=meeting_topic,
        attendee_names=attendee_names,
        external_attendees=context.external_attendees,
        internal_domain=context.internal_domain,
    )

    return analyzer.analyze_context(context)
