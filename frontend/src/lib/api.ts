import { supabase } from './supabase';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface Attendee {
  email: string;
  name: string | null;
  response_status: string | null;
}

export interface Meeting {
  id: string;
  title: string;
  description: string | null;
  start_time: string;
  end_time: string;
  attendees: Attendee[];
  location: string | null;
  meeting_link: string | null;
}

// Legacy prep document format
export interface PrepDocument {
  meeting_id: string;
  context_summary: string;
  key_points: string[];
  suggested_agenda: string[];
  action_items: string[];
  generated_at: string;
}

// Enhanced prep document format
export interface DiscussionPoint {
  point: string;
  source: string;
  priority: 'high' | 'medium' | 'low';
}

export interface AgendaItem {
  item: string;
  duration: string;
  priority: 'high' | 'medium' | 'low';
}

export interface DocumentInsight {
  document: string;
  key_findings: string;
  metrics: string[];
}

export interface ReferencedSource {
  type: 'email' | 'slack' | 'document';
  title: string;
  date?: string;
  link?: string;
}

export interface EnhancedPrepDocument {
  meeting_id: string;
  generated_at: string;
  context_summary: string;
  key_discussion_points: DiscussionPoint[];
  relationship_notes: string[];
  document_insights: DocumentInsight[];
  suggested_agenda: AgendaItem[];
  questions_to_ask: string[];
  action_items: string[];
  referenced_sources: ReferencedSource[];
  context_stats: {
    emails_analyzed: number;
    slack_messages_analyzed: number;
    documents_analyzed: number;
    items_included: number;
    items_excluded: number;
  };
  has_external_attendees: boolean;
  warnings: string[];
  prep_markdown: string;
}

export interface ContextSummary {
  slack_messages: number;
  email_threads: number;
  documents_analyzed: number;
  external_attendees: boolean;
}

export interface EnhancedPrepResponse {
  meeting: Meeting;
  prep_document: EnhancedPrepDocument;
  context_summary: ContextSummary;
  generated_at: string;
}

export interface MeetingPrepResponse {
  meeting: Meeting;
  prep_document: PrepDocument;
}

export interface ConnectionStatus {
  google_connected: boolean;
  slack_connected: boolean;
}

export interface MeetingContext {
  meeting_id: string;
  meeting_title: string;
  attendees: { email: string; name: string | null }[];
  external_attendees: string[];
  stats: {
    total_emails: number;
    total_slack_messages: number;
    total_documents: number;
  };
  email_subjects: string[];
  slack_channels: string[];
  documents: { filename: string; source: string }[];
  errors: string[];
}

class ApiClient {
  private userId: string | null = null;

  setUserId(userId: string | null) {
    this.userId = userId;
  }

  private async fetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = new URL(endpoint, API_URL);

    // Add user_id as query param for demo mode
    if (this.userId) {
      url.searchParams.set('user_id', this.userId);
    }

    // Get the Supabase session token
    const { data: { session } } = await supabase.auth.getSession();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (session?.access_token) {
      headers['Authorization'] = `Bearer ${session.access_token}`;
    }

    const response = await fetch(url.toString(), {
      ...options,
      headers: {
        ...headers,
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || 'Request failed');
    }

    return response.json();
  }

  async getConnectionStatus(): Promise<ConnectionStatus> {
    return this.fetch<ConnectionStatus>('/auth/status');
  }

  async getGoogleAuthUrl(): Promise<{ auth_url: string }> {
    return this.fetch<{ auth_url: string }>('/auth/google');
  }

  async getSlackAuthUrl(): Promise<{ auth_url: string }> {
    return this.fetch<{ auth_url: string }>('/auth/slack');
  }

  async disconnectProvider(provider: 'google' | 'slack'): Promise<void> {
    await this.fetch(`/auth/${provider}`, { method: 'DELETE' });
  }

  async getMeetings(): Promise<Meeting[]> {
    return this.fetch<Meeting[]>('/meetings');
  }

  async getMeeting(meetingId: string): Promise<Meeting> {
    return this.fetch<Meeting>(`/meetings/${meetingId}`);
  }

  // Legacy endpoint
  async generatePrepDocument(
    meetingId: string,
    forceRegenerate = false
  ): Promise<MeetingPrepResponse> {
    return this.fetch<MeetingPrepResponse>('/prep/generate', {
      method: 'POST',
      body: JSON.stringify({
        meeting_id: meetingId,
        force_regenerate: forceRegenerate,
      }),
    });
  }

  // New enhanced endpoint with document analysis
  async generateEnhancedPrep(
    meetingId: string,
    forceRegenerate = false
  ): Promise<EnhancedPrepResponse> {
    const url = `/api/meetings/${meetingId}/generate-prep`;
    const params = forceRegenerate ? '?force_regenerate=true' : '';
    return this.fetch<EnhancedPrepResponse>(`${url}${params}`, {
      method: 'POST',
    });
  }

  async getPrepDocument(meetingId: string): Promise<EnhancedPrepDocument | PrepDocument> {
    return this.fetch<EnhancedPrepDocument | PrepDocument>(`/prep/${meetingId}`);
  }

  async getMeetingContext(meetingId: string): Promise<MeetingContext> {
    return this.fetch<MeetingContext>(`/api/meetings/${meetingId}/context`);
  }

  async getDemoStatus(): Promise<{ demo_mode: boolean }> {
    return this.fetch<{ demo_mode: boolean }>('/demo/status');
  }
}

// Helper to check if a prep document is enhanced
export function isEnhancedPrepDocument(
  doc: EnhancedPrepDocument | PrepDocument
): doc is EnhancedPrepDocument {
  return 'prep_markdown' in doc || 'key_discussion_points' in doc;
}

export const api = new ApiClient();
