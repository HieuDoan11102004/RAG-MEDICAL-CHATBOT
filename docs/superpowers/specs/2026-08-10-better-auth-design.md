# Better-Auth Implementation Design

**Date:** 2026-08-10
**Status:** Approved

## Overview
Add email/password authentication to the medical chatbot with SQLite storage. Users can sign up, sign in, and sign out. Chat routes are protected — anonymous users must log in first.

## Technology Stack
- **Auth Framework:** better-auth
- **Database:** SQLite (file-based, auto-created)
- **Frontend SDK:** @better-auth/react

## Backend Changes

### Dependencies
Add `better-sqlite3` to `backend/pyproject.toml`:
```toml
dependencies = [
    ...
    "better-sqlite3>=11.0.0",
]
```

### New File: `backend/app/auth.py`
- Initialize better-auth with SQLite adapter
- Configure email/password credentials
- Define session management
- Export auth instance and API routes

### Modified: `backend/app/application.py`
- Import and mount auth routes at `/api/auth/*`
- Add auth middleware to protect `/api/messages` and `/api/chat`
- Inject authenticated user info into request context
- Return user info in chat responses

### Database
- SQLite file at `backend/data/auth.db`
- Created automatically by better-auth on first run
- Tables: users, sessions, credentials

## Frontend Changes

### Dependencies
Add to `frontend/package.json`:
```json
{
  "dependencies": {
    "@better-auth/react": "^1.0.0"
  }
}
```

### New Component: `frontend/src/components/AuthModal.tsx`
- Modal overlay with login/signup forms
- Email + password inputs with validation
- Toggle between sign in and sign up modes
- Error message display
- Loading states

### Modified: `frontend/src/App.tsx`
- Wrap app with better-auth provider
- Check auth state on load
- Show `AuthModal` if not logged in
- Pass user info to Sidebar
- Conditionally enable chat composer based on auth state

### Modified: `frontend/src/components/Sidebar.tsx`
- Display logged-in user email instead of "Guest user"
- Add sign out button
- Show user avatar

### Modified: `frontend/src/api/chat.ts`
- Include auth session cookie with requests (better-auth handles this automatically)

## API Endpoints

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/api/auth/signup` | POST | Create new account | No |
| `/api/auth/sign-in` | POST | Sign in | No |
| `/api/auth/sign-out` | POST | Sign out | Yes |
| `/api/auth/session` | GET | Get current session | No |
| `/api/messages` | POST | Chat | Yes |
| `/api/chat` | POST | Chat (legacy) | Yes |

## Data Flow

1. **Sign Up**: User enters email/password → POST `/api/auth/signup` → Create user in SQLite → Return session cookie
2. **Sign In**: POST `/api/auth/sign-in` → Validate credentials → Return session cookie
3. **Protected Request**: Browser sends session cookie → Flask middleware validates → Process chat request → Include user_id in response
4. **Sign Out**: POST `/api/auth/sign-out` → Invalidate session → Clear cookie

## Security Considerations
- Passwords hashed by better-auth (bcrypt)
- Session tokens are secure, httpOnly cookies
- Protected routes return 401 if not authenticated
- User ID from authenticated session replaces anonymous user tracking

## Testing Plan
- Backend: Test auth endpoints with pytest
- Frontend: Manual testing of login/logout flow
- Integration: Verify chat requests include user context
