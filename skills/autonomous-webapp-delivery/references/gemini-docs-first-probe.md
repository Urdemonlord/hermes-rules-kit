# Gemini docs-first probe (AgentWA VPS)

## Why this exists
A recurring failure mode was misclassifying Gemini as "broken/limit" without first validating model/version and request shape per latest docs.

## Fast probe order (must follow)
1. **Validate key/project access**
   - `GET https://generativelanguage.googleapis.com/v1beta/models?key=...`
   - Expect `200` + model list.
2. **Generate on current recommended models**
   - First: `gemini-2.5-flash-lite`
   - Fallback: `gemini-2.5-flash`
   - Endpoint: `POST /v1beta/models/{model}:generateContent?key=...`
   - Body shape: `contents: [{ parts: [{ text }] }]`
3. **Classify outcome explicitly**
   - `200` with candidate text: model usable
   - `429`: quota/rate limit on project/model
   - `401/403`: auth/key/project permission issue

## Important pitfall
Do not infer global Gemini status from older model paths only (e.g., 2.0 checks). A key can fail one path and succeed on 2.5 models.

## Security
- Never print full key in logs/chat.
- If key was pasted in chat, rotate after debugging.
