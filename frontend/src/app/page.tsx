'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import Header from '@/components/Header';
import MeetingCard from '@/components/MeetingCard';
import { api, Meeting, ConnectionStatus } from '@/lib/api';
import {
  Loader2,
  Calendar,
  AlertCircle,
  Link as LinkIcon,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import Link from 'next/link';

export default function DashboardPage() {
  const { user, loading: authLoading, isDemoMode } = useAuth();
  const router = useRouter();

  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login');
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    if (user) {
      fetchData();
    }
  }, [user]);

  const fetchData = async () => {
    try {
      const [meetingsData, status] = await Promise.all([
        api.getMeetings(),
        api.getConnectionStatus(),
      ]);
      setMeetings(meetingsData);
      setConnectionStatus(status);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  if (authLoading || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="w-8 h-8 animate-spin text-purple-600" />
      </div>
    );
  }

  const needsConnection = connectionStatus && !connectionStatus.google_connected;

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Hero Section */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
                <Calendar className="w-7 h-7 text-purple-600" />
                Upcoming Meetings
              </h1>
              <p className="mt-2 text-gray-600">
                Generate AI-powered prep documents for your upcoming meetings
              </p>
            </div>

            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* Connection Warning */}
        {needsConnection && !isDemoMode && (
          <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5" />
              <div className="flex-1">
                <p className="font-medium text-amber-900">
                  Connect your accounts to get started
                </p>
                <p className="text-sm text-amber-700 mt-1">
                  Connect Google to see your calendar and generate meeting prep documents.
                </p>
                <Link
                  href="/connect"
                  className="inline-flex items-center gap-1.5 mt-3 text-sm font-medium text-amber-700 hover:text-amber-800"
                >
                  <LinkIcon className="w-4 h-4" />
                  Connect Services
                </Link>
              </div>
            </div>
          </div>
        )}

        {/* Demo Mode Info */}
        {isDemoMode && (
          <div className="mb-6 p-4 bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-xl">
            <div className="flex items-start gap-3">
              <Sparkles className="w-5 h-5 text-purple-600 mt-0.5" />
              <div>
                <p className="font-medium text-purple-900">Demo Mode Active</p>
                <p className="text-sm text-purple-700 mt-1">
                  You&apos;re viewing sample meetings and data. Click &quot;Generate Prep&quot; on any meeting
                  to see how the AI-powered prep documents work!
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 mt-0.5" />
              <div>
                <p className="font-medium text-red-900">Error loading meetings</p>
                <p className="text-sm text-red-700 mt-1">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Meetings List */}
        {meetings.length > 0 ? (
          <div className="space-y-4">
            {meetings.map((meeting) => (
              <MeetingCard key={meeting.id} meeting={meeting} />
            ))}
          </div>
        ) : !error ? (
          <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
            <Calendar className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              No upcoming meetings
            </h3>
            <p className="text-gray-600">
              {isDemoMode
                ? "Demo data will appear here. Try refreshing the page."
                : "Your upcoming meetings from Google Calendar will appear here."}
            </p>
          </div>
        ) : null}

        {/* Feature Highlights */}
        <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center mb-4">
              <Calendar className="w-5 h-5 text-purple-600" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-2">Calendar Integration</h3>
            <p className="text-sm text-gray-600">
              Automatically syncs with your Google Calendar to show upcoming meetings.
            </p>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
              <LinkIcon className="w-5 h-5 text-blue-600" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-2">Context Gathering</h3>
            <p className="text-sm text-gray-600">
              Searches Gmail and Slack for relevant communications with attendees.
            </p>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center mb-4">
              <Sparkles className="w-5 h-5 text-green-600" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-2">AI-Powered Prep</h3>
            <p className="text-sm text-gray-600">
              Generates comprehensive prep documents with key points and suggested agenda.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
