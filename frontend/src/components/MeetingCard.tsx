'use client';

import { useState } from 'react';
import { format, parseISO } from 'date-fns';
import {
  Calendar,
  Clock,
  Users,
  MapPin,
  Video,
  Sparkles,
  Loader2,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { Meeting, api, MeetingPrepResponse } from '@/lib/api';
import PrepDocument from './PrepDocument';

interface MeetingCardProps {
  meeting: Meeting;
}

export default function MeetingCard({ meeting }: MeetingCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [prepData, setPrepData] = useState<MeetingPrepResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const startTime = parseISO(meeting.start_time);
  const endTime = parseISO(meeting.end_time);
  const duration = Math.round((endTime.getTime() - startTime.getTime()) / 60000);

  const handleGeneratePrep = async () => {
    setIsGenerating(true);
    setError(null);

    try {
      const response = await api.generatePrepDocument(meeting.id);
      setPrepData(response);
      setIsExpanded(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate prep document');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRegenerate = async () => {
    setIsGenerating(true);
    setError(null);

    try {
      const response = await api.generatePrepDocument(meeting.id, true);
      setPrepData(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to regenerate prep document');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      <div className="p-6">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              {meeting.title}
            </h3>

            <div className="flex flex-wrap gap-4 text-sm text-gray-600">
              <div className="flex items-center gap-1.5">
                <Calendar className="w-4 h-4" />
                <span>{format(startTime, 'EEEE, MMMM d, yyyy')}</span>
              </div>

              <div className="flex items-center gap-1.5">
                <Clock className="w-4 h-4" />
                <span>
                  {format(startTime, 'h:mm a')} - {format(endTime, 'h:mm a')}
                  <span className="text-gray-400 ml-1">({duration} min)</span>
                </span>
              </div>

              {meeting.attendees.length > 0 && (
                <div className="flex items-center gap-1.5">
                  <Users className="w-4 h-4" />
                  <span>{meeting.attendees.length} attendee(s)</span>
                </div>
              )}

              {meeting.location && (
                <div className="flex items-center gap-1.5">
                  <MapPin className="w-4 h-4" />
                  <span>{meeting.location}</span>
                </div>
              )}

              {meeting.meeting_link && (
                <a
                  href={meeting.meeting_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 text-blue-600 hover:text-blue-700"
                >
                  <Video className="w-4 h-4" />
                  <span>Join Meeting</span>
                </a>
              )}
            </div>

            {meeting.description && (
              <p className="mt-3 text-sm text-gray-600 line-clamp-2">
                {meeting.description}
              </p>
            )}

            {meeting.attendees.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {meeting.attendees.slice(0, 5).map((attendee, index) => (
                  <span
                    key={index}
                    className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700"
                  >
                    {attendee.name || attendee.email.split('@')[0]}
                  </span>
                ))}
                {meeting.attendees.length > 5 && (
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-500">
                    +{meeting.attendees.length - 5} more
                  </span>
                )}
              </div>
            )}
          </div>

          <div className="ml-4 flex flex-col gap-2">
            {!prepData ? (
              <button
                onClick={handleGeneratePrep}
                disabled={isGenerating}
                className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-blue-600 text-white text-sm font-medium rounded-lg hover:from-purple-700 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    Generate Prep
                  </>
                )}
              </button>
            ) : (
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-200 transition-all"
              >
                {isExpanded ? (
                  <>
                    <ChevronUp className="w-4 h-4" />
                    Hide Prep
                  </>
                ) : (
                  <>
                    <ChevronDown className="w-4 h-4" />
                    View Prep
                  </>
                )}
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}
      </div>

      {isExpanded && prepData && (
        <div className="border-t border-gray-200 bg-gray-50 p-6">
          <PrepDocument
            prepDocument={prepData.prep_document}
            onRegenerate={handleRegenerate}
            isRegenerating={isGenerating}
          />
        </div>
      )}
    </div>
  );
}
