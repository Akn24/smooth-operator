'use client';

import { format, parseISO } from 'date-fns';
import {
  FileText,
  Key,
  ListChecks,
  CheckCircle2,
  RefreshCw,
  Loader2,
  MessageSquare,
  Users,
  AlertTriangle,
  FileSpreadsheet,
  Mail,
  Hash,
  HelpCircle,
  Link,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { useState } from 'react';
import {
  PrepDocument as PrepDocumentType,
  EnhancedPrepDocument,
  isEnhancedPrepDocument,
  ContextSummary,
} from '@/lib/api';

interface PrepDocumentProps {
  prepDocument: EnhancedPrepDocument | PrepDocumentType;
  contextSummary?: ContextSummary;
  onRegenerate?: () => void;
  isRegenerating?: boolean;
}

function PriorityBadge({ priority }: { priority: 'high' | 'medium' | 'low' }) {
  const colors = {
    high: 'bg-red-100 text-red-700',
    medium: 'bg-yellow-100 text-yellow-700',
    low: 'bg-gray-100 text-gray-600',
  };

  return (
    <span className={`text-xs px-2 py-0.5 rounded-full ${colors[priority]}`}>
      {priority}
    </span>
  );
}

function SourceIcon({ type }: { type: string }) {
  switch (type) {
    case 'email':
      return <Mail className="w-3.5 h-3.5 text-blue-500" />;
    case 'slack':
      return <Hash className="w-3.5 h-3.5 text-purple-500" />;
    case 'document':
      return <FileSpreadsheet className="w-3.5 h-3.5 text-green-500" />;
    default:
      return <FileText className="w-3.5 h-3.5 text-gray-500" />;
  }
}

function CollapsibleSection({
  title,
  icon: Icon,
  iconColor,
  children,
  defaultOpen = true,
  badge,
}: {
  title: string;
  icon: React.ElementType;
  iconColor: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
  badge?: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className={`w-4 h-4 ${iconColor}`} />
          <h5 className="font-medium text-gray-900">{title}</h5>
          {badge}
        </div>
        {isOpen ? (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronRight className="w-4 h-4 text-gray-400" />
        )}
      </button>
      {isOpen && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

function EnhancedPrepView({
  prep,
  contextSummary,
}: {
  prep: EnhancedPrepDocument;
  contextSummary?: ContextSummary;
}) {
  return (
    <div className="space-y-4">
      {/* Context Stats Banner */}
      {contextSummary && (
        <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg p-4 border border-blue-100">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-6 text-sm">
              <div className="flex items-center gap-1.5">
                <Mail className="w-4 h-4 text-blue-600" />
                <span className="text-gray-600">
                  <strong>{contextSummary.email_threads}</strong> emails
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <Hash className="w-4 h-4 text-purple-600" />
                <span className="text-gray-600">
                  <strong>{contextSummary.slack_messages}</strong> Slack messages
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <FileSpreadsheet className="w-4 h-4 text-green-600" />
                <span className="text-gray-600">
                  <strong>{contextSummary.documents_analyzed}</strong> documents
                </span>
              </div>
            </div>
            {contextSummary.external_attendees && (
              <div className="flex items-center gap-1.5 text-sm text-amber-700 bg-amber-50 px-2 py-1 rounded">
                <Users className="w-4 h-4" />
                External attendees
              </div>
            )}
          </div>
        </div>
      )}

      {/* Warnings */}
      {prep.warnings && prep.warnings.length > 0 && (
        <div className="bg-amber-50 rounded-lg p-4 border border-amber-200">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div>
              <h5 className="font-medium text-amber-800 mb-1">Concerns</h5>
              <ul className="space-y-1">
                {prep.warnings.map((warning, i) => (
                  <li key={i} className="text-sm text-amber-700">
                    {warning}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Context Summary */}
      <CollapsibleSection
        title="Context Summary"
        icon={FileText}
        iconColor="text-blue-600"
      >
        <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
          {prep.context_summary}
        </div>
      </CollapsibleSection>

      {/* Key Discussion Points */}
      {prep.key_discussion_points && prep.key_discussion_points.length > 0 && (
        <CollapsibleSection
          title="Key Discussion Points"
          icon={MessageSquare}
          iconColor="text-indigo-600"
          badge={
            <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full">
              {prep.key_discussion_points.length}
            </span>
          }
        >
          <ul className="space-y-3">
            {prep.key_discussion_points.map((point, index) => (
              <li key={index} className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 flex items-center justify-center bg-indigo-100 text-indigo-700 rounded-full text-xs font-medium">
                  {index + 1}
                </span>
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm text-gray-800">{point.point}</span>
                    {point.priority && <PriorityBadge priority={point.priority} />}
                  </div>
                  {point.source && (
                    <p className="text-xs text-gray-500 mt-1">
                      Source: {point.source}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </CollapsibleSection>
      )}

      {/* Relationship Notes */}
      {prep.relationship_notes && prep.relationship_notes.length > 0 && (
        <CollapsibleSection
          title="Relationship Notes"
          icon={Users}
          iconColor="text-pink-600"
        >
          <ul className="space-y-2">
            {prep.relationship_notes.map((note, index) => (
              <li key={index} className="flex items-start gap-2 text-sm text-gray-700">
                <span className="text-pink-500 flex-shrink-0">&#x2022;</span>
                <span>{note}</span>
              </li>
            ))}
          </ul>
        </CollapsibleSection>
      )}

      {/* Document Insights */}
      {prep.document_insights && prep.document_insights.length > 0 && (
        <CollapsibleSection
          title="Document Insights"
          icon={FileSpreadsheet}
          iconColor="text-green-600"
          badge={
            <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
              {prep.document_insights.length} docs
            </span>
          }
        >
          <div className="space-y-4">
            {prep.document_insights.map((insight, index) => (
              <div key={index} className="bg-gray-50 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2">
                  <FileSpreadsheet className="w-4 h-4 text-green-600" />
                  <span className="font-medium text-sm text-gray-900">
                    {insight.document}
                  </span>
                </div>
                <p className="text-sm text-gray-700 mb-2">{insight.key_findings}</p>
                {insight.metrics && insight.metrics.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {insight.metrics.map((metric, i) => (
                      <span
                        key={i}
                        className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded"
                      >
                        {metric}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Suggested Agenda */}
      {prep.suggested_agenda && prep.suggested_agenda.length > 0 && (
        <CollapsibleSection
          title="Suggested Agenda"
          icon={ListChecks}
          iconColor="text-emerald-600"
        >
          <ul className="space-y-2">
            {prep.suggested_agenda.map((item, index) => (
              <li key={index} className="flex items-center gap-3 text-sm">
                <span className="flex-shrink-0 w-6 h-6 flex items-center justify-center bg-emerald-100 text-emerald-700 rounded-full text-xs font-medium">
                  {index + 1}
                </span>
                <span className="flex-1 text-gray-800">
                  {typeof item === 'string' ? item : item.item}
                </span>
                {typeof item !== 'string' && item.duration && (
                  <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                    {item.duration}
                  </span>
                )}
                {typeof item !== 'string' && item.priority && (
                  <PriorityBadge priority={item.priority} />
                )}
              </li>
            ))}
          </ul>
        </CollapsibleSection>
      )}

      {/* Questions to Ask */}
      {prep.questions_to_ask && prep.questions_to_ask.length > 0 && (
        <CollapsibleSection
          title="Questions to Ask"
          icon={HelpCircle}
          iconColor="text-orange-600"
        >
          <ul className="space-y-2">
            {prep.questions_to_ask.map((question, index) => (
              <li key={index} className="flex items-start gap-2 text-sm text-gray-700">
                <HelpCircle className="w-4 h-4 text-orange-500 flex-shrink-0 mt-0.5" />
                <span>{question}</span>
              </li>
            ))}
          </ul>
        </CollapsibleSection>
      )}

      {/* Action Items */}
      {prep.action_items && prep.action_items.length > 0 && (
        <CollapsibleSection
          title="Outstanding Action Items"
          icon={CheckCircle2}
          iconColor="text-purple-600"
        >
          <ul className="space-y-2">
            {prep.action_items.map((item, index) => (
              <li key={index} className="flex items-start gap-2 text-sm text-gray-700">
                <div className="flex-shrink-0 w-5 h-5 flex items-center justify-center mt-0.5">
                  <div className="w-4 h-4 border-2 border-purple-300 rounded" />
                </div>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </CollapsibleSection>
      )}

      {/* Referenced Sources */}
      {prep.referenced_sources && prep.referenced_sources.length > 0 && (
        <CollapsibleSection
          title="Referenced Sources"
          icon={Link}
          iconColor="text-gray-600"
          defaultOpen={false}
        >
          <ul className="space-y-2">
            {prep.referenced_sources.map((source, index) => (
              <li key={index} className="flex items-center gap-2 text-sm">
                <SourceIcon type={source.type} />
                <span className="text-gray-800">{source.title}</span>
                {source.date && (
                  <span className="text-xs text-gray-500">({source.date})</span>
                )}
              </li>
            ))}
          </ul>
        </CollapsibleSection>
      )}
    </div>
  );
}

function LegacyPrepView({ prep }: { prep: PrepDocumentType }) {
  return (
    <div className="space-y-6">
      {/* Context Summary */}
      <div className="bg-white rounded-lg p-4 border border-gray-200">
        <h5 className="font-medium text-gray-900 mb-2 flex items-center gap-2">
          <FileText className="w-4 h-4 text-blue-600" />
          Context Summary
        </h5>
        <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
          {prep.context_summary}
        </div>
      </div>

      {/* Key Points */}
      <div className="bg-white rounded-lg p-4 border border-gray-200">
        <h5 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
          <Key className="w-4 h-4 text-amber-600" />
          Key Points
        </h5>
        <ul className="space-y-2">
          {prep.key_points.map((point, index) => (
            <li key={index} className="flex items-start gap-2 text-sm text-gray-700">
              <span className="flex-shrink-0 w-5 h-5 flex items-center justify-center bg-amber-100 text-amber-700 rounded-full text-xs font-medium">
                {index + 1}
              </span>
              <span>{point}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Suggested Agenda */}
      <div className="bg-white rounded-lg p-4 border border-gray-200">
        <h5 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
          <ListChecks className="w-4 h-4 text-green-600" />
          Suggested Agenda
        </h5>
        <ul className="space-y-2">
          {prep.suggested_agenda.map((item, index) => (
            <li key={index} className="flex items-start gap-2 text-sm text-gray-700">
              <span className="flex-shrink-0 w-5 h-5 flex items-center justify-center bg-green-100 text-green-700 rounded-full text-xs font-medium">
                {index + 1}
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Action Items */}
      <div className="bg-white rounded-lg p-4 border border-gray-200">
        <h5 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-purple-600" />
          Action Items
        </h5>
        <ul className="space-y-2">
          {prep.action_items.map((item, index) => (
            <li key={index} className="flex items-start gap-2 text-sm text-gray-700">
              <div className="flex-shrink-0 w-5 h-5 flex items-center justify-center">
                <div className="w-4 h-4 border-2 border-purple-300 rounded" />
              </div>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default function PrepDocument({
  prepDocument,
  contextSummary,
  onRegenerate,
  isRegenerating = false,
}: PrepDocumentProps) {
  const isEnhanced = isEnhancedPrepDocument(prepDocument);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-gradient-to-r from-purple-100 to-blue-100 rounded-lg">
            <FileText className="w-5 h-5 text-purple-600" />
          </div>
          <div>
            <h4 className="font-semibold text-gray-900">
              {isEnhanced ? 'Enhanced Meeting Prep' : 'Meeting Prep Document'}
            </h4>
            <p className="text-xs text-gray-500">
              Generated{' '}
              {format(parseISO(prepDocument.generated_at), "MMM d, yyyy 'at' h:mm a")}
            </p>
          </div>
        </div>

        {onRegenerate && (
          <button
            onClick={onRegenerate}
            disabled={isRegenerating}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-200 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isRegenerating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Regenerating...
              </>
            ) : (
              <>
                <RefreshCw className="w-4 h-4" />
                Regenerate
              </>
            )}
          </button>
        )}
      </div>

      {isEnhanced ? (
        <EnhancedPrepView
          prep={prepDocument as EnhancedPrepDocument}
          contextSummary={contextSummary}
        />
      ) : (
        <LegacyPrepView prep={prepDocument as PrepDocumentType} />
      )}
    </div>
  );
}
