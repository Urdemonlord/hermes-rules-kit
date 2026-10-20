# Dropbox API Patterns

Provider-specific implementation details for Dropbox OAuth integration.

## API Endpoints

Dropbox uses TWO separate API domains:

- **RPC endpoints**: `https://api.dropboxapi.com/2/*` — JSON request/response
- **Content endpoints**: `https://content.dropboxapi.com/2/*` — binary/stream operations

## Download Implementation

File downloads use the **content** API with a special header pattern:

```go
endpoint := "https://content.dropboxapi.com/2/files/download"

// File path goes in header, not URL
arg := map[string]string{"path": providerFileID}
argJSON, _ := json.Marshal(arg)

req.Header.Set("Authorization", "Bearer "+accessToken)
req.Header.Set("Dropbox-API-Arg", string(argJSON))

resp, _ := client.Do(req)
// Response body IS the file content stream
// Metadata is in response header:
metaJSON := resp.Header.Get("Dropbox-API-Result")
```

**Critical**: Do NOT use `defer resp.Body.Close()` at the top of the function. The caller needs the open stream. Close only on error paths.

## User Account Info

Requires `account_info.read` scope:

```bash
POST https://api.dropboxapi.com/2/users/get_current_account
Authorization: Bearer <token>
Content-Type: application/json

null  # body is literally null
```

Response includes `account_id`, `name`, `email`.

## File Listing

Requires `files.metadata.read` scope:

```bash
POST https://api.dropboxapi.com/2/files/list_folder
Authorization: Bearer <token>
Content-Type: application/json

{
  "path": "",
  "recursive": false,
  "include_media_info": false
}
```

Pagination via `has_more` + `cursor` fields.

## Scope Requirements

| Endpoint | Minimum Scope |
|----------|---------------|
| `/users/get_current_account` | `account_info.read` |
| `/files/list_folder` | `files.metadata.read` |
| `/files/download` | `files.content.read` |
| `/files/upload` | `files.content.write` |

## Error Handling

Dropbox returns HTTP 409 for logical errors (e.g., file not found):

```json
{
  "error_summary": "path/not_found/...",
  "error": {
    ".tag": "path",
    "path": {".tag": "not_found"}
  }
}
```

Parse the `.tag` field to get error type.

## Token Refresh

Dropbox uses standard OAuth 2.0 refresh:

```bash
POST https://api.dropbox.com/oauth2/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token
&refresh_token=<refresh_token>
&client_id=<client_id>
&client_secret=<client_secret>
```

## Common Pitfalls

1. **Using wrong domain**: Download MUST use `content.dropboxapi.com`, not `api.dropboxapi.com`
2. **Missing scope**: Calling `/users/get_current_account` without `account_info.read` → 401
3. **Body on null endpoint**: Some RPC endpoints require `null` as body, not `{}`
4. **Closing stream early**: Download response body must stay open for caller
