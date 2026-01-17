'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import Header from '@/components/Header';
import { api, ConnectionStatus } from '@/lib/api';
import {
  CheckCircle2,
  XCircle,
  Loader2,
  ExternalLink,
  Chrome,
  MessageSquare,
  ArrowLeft,
  AlertCircle,
} from 'lucide-react';
import Link from 'next/link';

function ConnectPageContent() {
  const { user, loading: authLoading, isDemoMode } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [status, setStatus] = useState<ConnectionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState<'google' | 'slack' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    // Check for callback success/error in URL
    const googleStatus = searchParams.get('google');
    const slackStatus = searchParams.get('slack');

    if (googleStatus === 'success') {
      setSuccessMessage('Google account connected successfully!');
    }
    if (slackStatus === 'success') {
      setSuccessMessage('Slack workspace connected successfully!');
    }
  }, [searchParams]);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login');
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    if (user) {
      fetchConnectionStatus();
    }
  }, [user]);

  const fetchConnectionStatus = async () => {
    try {
      const connectionStatus = await api.getConnectionStatus();
      setStatus(connectionStatus);
    } catch {
      setError('Failed to fetch connection status');
    } finally {
      setLoading(false);
    }
  };

  const handleConnectGoogle = async () => {
    if (isDemoMode) {
      setSuccessMessage('In demo mode, connections are simulated!');
      return;
    }

    setConnecting('google');
    setError(null);

    try {
      const { auth_url } = await api.getGoogleAuthUrl();
      window.location.href = auth_url;
    } catch {
      setError('Failed to start Google connection');
      setConnecting(null);
    }
  };

  const handleConnectSlack = async () => {
    if (isDemoMode) {
      setSuccessMessage('In demo mode, connections are simulated!');
      return;
    }

    setConnecting('slack');
    setError(null);

    try {
      const { auth_url } = await api.getSlackAuthUrl();
      window.location.href = auth_url;
    } catch {
      setError('Failed to start Slack connection');
      setConnecting(null);
    }
  };

  const handleDisconnect = async (provider: 'google' | 'slack') => {
    if (isDemoMode) {
      setError('Cannot disconnect in demo mode');
      return;
    }

    try {
      await api.disconnectProvider(provider);
      await fetchConnectionStatus();
    } catch {
      setError(`Failed to disconnect ${provider}`);
    }
  };

  if (authLoading || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="w-8 h-8 animate-spin text-purple-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Dashboard
          </Link>
        </div>

        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Connect Your Services</h1>
          <p className="mt-2 text-gray-600">
            Connect your Google and Slack accounts to enable AI-powered meeting prep.
            We&apos;ll analyze your calendar, emails, and messages to generate comprehensive prep documents.
          </p>
        </div>

        {isDemoMode && (
          <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-amber-900">Demo Mode Active</p>
                <p className="text-sm text-amber-700 mt-1">
                  In demo mode, all connections are simulated with sample data.
                  Sign in with a real account to connect your services.
                </p>
              </div>
            </div>
          </div>
        )}

        {successMessage && (
          <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-xl flex items-start gap-3">
            <CheckCircle2 className="w-5 h-5 text-green-600 mt-0.5" />
            <p className="text-sm text-green-700">{successMessage}</p>
          </div>
        )}

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl flex items-start gap-3">
            <XCircle className="w-5 h-5 text-red-600 mt-0.5" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        <div className="space-y-4">
          {/* Google Connection */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-4">
                <div className="p-3 bg-gray-100 rounded-xl">
                  <Chrome className="w-6 h-6 text-gray-700" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">Google Workspace</h3>
                  <p className="text-sm text-gray-600 mt-1">
                    Connect to access Google Calendar and Gmail
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-blue-50 text-blue-700">
                      Calendar Events
                    </span>
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-red-50 text-red-700">
                      Email Search
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                {status?.google_connected ? (
                  <>
                    <span className="flex items-center gap-1.5 text-sm text-green-600">
                      <CheckCircle2 className="w-4 h-4" />
                      Connected
                    </span>
                    {!isDemoMode && (
                      <button
                        onClick={() => handleDisconnect('google')}
                        className="text-sm text-red-600 hover:text-red-700"
                      >
                        Disconnect
                      </button>
                    )}
                  </>
                ) : (
                  <button
                    onClick={handleConnectGoogle}
                    disabled={connecting === 'google'}
                    className="inline-flex items-center gap-2 px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {connecting === 'google' ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <ExternalLink className="w-4 h-4" />
                    )}
                    Connect Google
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Slack Connection */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-4">
                <div className="p-3 bg-purple-100 rounded-xl">
                  <MessageSquare className="w-6 h-6 text-purple-700" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">Slack</h3>
                  <p className="text-sm text-gray-600 mt-1">
                    Connect to search messages about meeting attendees
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-purple-50 text-purple-700">
                      Message Search
                    </span>
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-purple-50 text-purple-700">
                      User Lookup
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                {status?.slack_connected ? (
                  <>
                    <span className="flex items-center gap-1.5 text-sm text-green-600">
                      <CheckCircle2 className="w-4 h-4" />
                      Connected
                    </span>
                    {!isDemoMode && (
                      <button
                        onClick={() => handleDisconnect('slack')}
                        className="text-sm text-red-600 hover:text-red-700"
                      >
                        Disconnect
                      </button>
                    )}
                  </>
                ) : (
                  <button
                    onClick={handleConnectSlack}
                    disabled={connecting === 'slack'}
                    className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {connecting === 'slack' ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <ExternalLink className="w-4 h-4" />
                    )}
                    Connect Slack
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Privacy Note */}
        <div className="mt-8 p-4 bg-gray-100 rounded-xl">
          <h4 className="font-medium text-gray-900 mb-2">Privacy & Security</h4>
          <ul className="text-sm text-gray-600 space-y-1">
            <li>• We only read your calendar, emails, and messages - never modify them</li>
            <li>• Your OAuth tokens are encrypted and stored securely</li>
            <li>• You can disconnect at any time to revoke access</li>
            <li>• Data is only used to generate meeting prep documents</li>
          </ul>
        </div>
      </main>
    </div>
  );
}

export default function ConnectPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="w-8 h-8 animate-spin text-purple-600" />
      </div>
    }>
      <ConnectPageContent />
    </Suspense>
  );
}
