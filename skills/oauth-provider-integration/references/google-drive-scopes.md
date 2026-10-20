# Google Drive API Scope Requirements

OAuth scope requirements for Google Drive API endpoints, organized by operation.

## Scope Hierarchy

Google Drive has a hierarchy of scopes from most to least permissive:

1. `https://www.googleapis.com/auth/drive` — Full access (read/write/delete)
2. `https://www.googleapis.com/auth/drive.file` — Per-file access (only files created by app)
3. `https://www.googleapis.com/auth/drive.readonly` — Read-only access to all files
4. `https://www.googleapis.com/auth/drive.metadata.readonly` — Metadata only, no content

**Plus user profile scopes** (often required):
- `openid` — OpenID Connect
- `email` — User email address
- `profile` — User profile info (name, photo)

## Common Endpoint Requirements

| Endpoint | Minimum Scope | Notes |
|----------|---------------|-------|
| `/drive/v3/about?fields=user` | `openid`, `email`, `profile` | Fetches user account info |
| `/drive/v3/files` (list) | `drive.metadata.readonly` | List files, metadata only |
| `/drive/v3/files/{id}` (metadata) | `drive.metadata.readonly` | Get file metadata |
| `/drive/v3/files/{id}?alt=media` (download) | `drive.readonly` | Download file content |
| `/drive/v3/files` (create) | `drive.file` or `drive` | Upload new file |
| `/drive/v3/files/{id}` (update) | `drive.file` or `drive` | Update existing file |

## The /about Endpoint Gotcha

**Common mistake**: Using only `drive.metadata.readonly` scope but calling `/drive/v3/about?fields=user`.

The `/about` endpoint with `fields=user` returns **user profile information**, which requires user profile scopes, NOT just Drive scopes.

**Symptom**: 403 Forbidden with error message like "Insufficient Permission" or "Request had insufficient authentication scopes."

**Fix**: Add profile scopes to OAuth configuration:

```go
Scopes: []string{
    "https://www.googleapis.com/auth/drive.readonly",
    "openid",
    "email", 
    "profile",
}
```

## Scope Change Migration

When you add scopes to your OAuth config:
1. New users get new scopes automatically
2. **Existing users keep old scopes** (tokens don't auto-upgrade)
3. Users must revoke and reconnect to get new scopes

**User migration steps**:
1. Go to https://myaccount.google.com/permissions
2. Find your app in "Third-party apps with account access"
3. Click "Remove access"
4. Return to your app and reconnect

## Download Implementation

Google Drive downloads require `alt=media` query parameter:

```bash
GET https://www.googleapis.com/drive/v3/files/{fileId}?alt=media
Authorization: Bearer <access_token>
```

Response body is the file content stream. Metadata comes from separate metadata request.

## Token Refresh

Standard OAuth 2.0 refresh:

```bash
POST https://oauth2.googleapis.com/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token
&refresh_token=<refresh_token>
&client_id=<client_id>
&client_secret=<client_secret>
```

## OAuth Consent Screen

**Important**: During development, OAuth consent screen status affects access:

- **Testing**: Only test users listed in Google Cloud Console can authorize
- **In production**: App must be verified by Google for sensitive/restricted scopes

If user sees "This app isn't verified" during OAuth, they need to:
- Click "Advanced"
- Click "Go to [your app] (unsafe)"
- Proceed with authorization

**Or** you need to add them as a test user in Google Cloud Console.

## Common Errors

### 403: Insufficient Permission
- **Cause**: Token scopes don't cover requested endpoint
- **Fix**: Check endpoint scope requirements, update OAuth config, user must reconnect

### 403: Access Not Configured
- **Cause**: Google Drive API not enabled in Google Cloud Console
- **Fix**: Go to "APIs & Services" → "Enabled APIs" → enable "Google Drive API"

### 401: Invalid Credentials
- **Cause**: Token expired and refresh failed, or token revoked
- **Fix**: Prompt user to reconnect

### 404: File Not Found
- **Cause**: File doesn't exist or user doesn't have access
- **Fix**: Verify file ID, check file permissions

## Scope Testing Checklist

When implementing Google Drive OAuth:

1. ✅ List files metadata → `drive.metadata.readonly`
2. ✅ Download file content → `drive.readonly`
3. ✅ Get user account info → `openid`, `email`, `profile`
4. ✅ Create files → `drive.file` or `drive`
5. ✅ Test with fresh account (no cached tokens)
6. ✅ Test token refresh flow
7. ✅ Verify error messages are user-friendly

## Related Documentation

- [Google Drive API Scopes](https://developers.google.com/drive/api/guides/api-specific-auth)
- [OAuth 2.0 for Web Server Apps](https://developers.google.com/identity/protocols/oauth2/web-server)
