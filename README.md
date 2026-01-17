# Smooth Operator - AI Meeting Prep Assistant

Smooth Operator is an AI-powered web application that generates comprehensive meeting prep documents by analyzing your Google Calendar, Gmail, and Slack communications.

## Features

- **Google Calendar Integration**: Automatically fetches upcoming meetings
- **Gmail Analysis**: Searches for recent emails with meeting attendees
- **Slack Integration**: Finds relevant Slack messages mentioning attendees
- **AI-Powered Prep Documents**: Uses GPT-4 to generate:
  - Context Summary
  - Key Points
  - Suggested Agenda
  - Action Items
- **Demo Mode**: Try the app with sample data without connecting real accounts

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: Next.js 14 (React, TypeScript, Tailwind CSS)
- **Database**: Supabase (PostgreSQL + Auth)
- **AI**: OpenAI GPT-4 API

## Project Structure

```
proactive-pa/
├── backend/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Configuration settings
│   ├── supabase_client.py      # Supabase database client
│   ├── demo_data.py            # Demo mode mock data
│   ├── integrations/
│   │   ├── google_calendar.py  # Google Calendar API client
│   │   ├── gmail.py            # Gmail API client
│   │   └── slack.py            # Slack API client
│   ├── ai/
│   │   └── openai_prep.py      # GPT-4 prep document generator
│   └── models/
│       └── schemas.py          # Pydantic models
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx        # Dashboard
│   │   │   ├── login/page.tsx  # Authentication
│   │   │   └── connect/page.tsx # OAuth connections
│   │   ├── components/
│   │   │   ├── MeetingCard.tsx
│   │   │   ├── PrepDocument.tsx
│   │   │   └── Header.tsx
│   │   ├── context/
│   │   │   └── AuthContext.tsx
│   │   └── lib/
│   │       ├── api.ts          # API client
│   │       └── supabase.ts     # Supabase client
│   └── ...
└── supabase/
    └── migrations/
        └── 001_initial_schema.sql
```

## Setup Instructions

### 1. Supabase Setup

1. Create a new project at [supabase.com](https://supabase.com)
2. Go to SQL Editor and run the migration file: `supabase/migrations/001_initial_schema.sql`
3. Copy your project URL and API keys from Settings > API

### 2. Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Enable Google Calendar API and Gmail API
4. Create OAuth 2.0 credentials
5. Add authorized redirect URI: `http://localhost:8000/auth/google/callback`
6. Download the client credentials

### 3. Slack OAuth Setup

1. Go to [Slack API](https://api.slack.com/apps)
2. Create a new app
3. Add OAuth scopes: `search:read`, `users:read`, `users:read.email`, `channels:history`, `channels:read`
4. Add redirect URL: `http://localhost:8000/auth/slack/callback`
5. Copy the client ID and secret

### 4. OpenAI API Setup

1. Go to [OpenAI Platform](https://platform.openai.com)
2. Create an API key
3. Ensure you have access to GPT-4

### 5. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your credentials

# Run the server
uvicorn main:app --reload --port 8000
```

### 6. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy and configure environment variables
cp .env.example .env.local
# Edit .env.local with your credentials

# Run the development server
npm run dev
```

### 7. Access the App

1. Open http://localhost:3000
2. Click "Enter Demo Mode" to try with sample data, OR
3. Sign up with email and password
4. Connect your Google and Slack accounts
5. View your upcoming meetings
6. Click "Generate Prep" to create AI-powered prep documents

## Environment Variables

### Backend (.env)

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_SERVICE_KEY=your-supabase-service-key

GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

SLACK_CLIENT_ID=your-slack-client-id
SLACK_CLIENT_SECRET=your-slack-client-secret
SLACK_REDIRECT_URI=http://localhost:8000/auth/slack/callback

OPENAI_API_KEY=your-openai-api-key

SECRET_KEY=your-secret-key-for-encryption
FRONTEND_URL=http://localhost:3000
DEMO_MODE=true
```

### Frontend (.env.local)

```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_DEMO_MODE=true
```

## Demo Mode

Set `DEMO_MODE=true` in the backend `.env` to run with sample data without real API connections. This is useful for:
- Testing the UI
- Demonstrating features
- Development without API keys

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/auth/google` | Start Google OAuth flow |
| GET | `/auth/google/callback` | Google OAuth callback |
| GET | `/auth/slack` | Start Slack OAuth flow |
| GET | `/auth/slack/callback` | Slack OAuth callback |
| DELETE | `/auth/{provider}` | Disconnect a provider |
| GET | `/auth/status` | Get connection status |
| GET | `/meetings` | Get upcoming meetings |
| GET | `/meetings/{id}` | Get specific meeting |
| POST | `/prep/generate` | Generate prep document |
| GET | `/prep/{meeting_id}` | Get cached prep document |

## Security Notes

- OAuth tokens are encrypted before storage using Fernet symmetric encryption
- Row Level Security (RLS) ensures users can only access their own data
- All API endpoints require authentication
- Tokens can be revoked at any time by disconnecting

## License

MIT
