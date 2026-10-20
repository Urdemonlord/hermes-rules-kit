# Firebase Google sign-in triage

Session-derived review notes for Google login / registration failures in a Next.js + Firebase app.

## What to check first
1. **Popup flow brittleness**
   - `signInWithPopup()` fails in popup-blocked browsers, in-app browsers, and some mobile contexts.
   - If the app only uses popup, add a redirect fallback or explicit error mapping.

2. **Client Firebase config availability**
   - `getFirebaseAuth()` can return `null` if any `NEXT_PUBLIC_FIREBASE_*` client env is missing or not inlined at build time.
   - A falsey auth object makes the UI report a generic config error before Google auth even starts.

3. **Google provider / authorized domain setup**
   - Confirm Google sign-in is enabled in Firebase Auth.
   - Confirm production domains are listed in Authorized domains.
   - Typical failures: `auth/unauthorized-domain`, `auth/operation-not-allowed`.

4. **Backend profile sync can look like auth failure**
   - In this codebase, Google sign-in is only the first step.
   - After popup success, the client immediately calls `/api/auth/profile` and `/api/auth/register` using the Firebase ID token.
   - If either route fails, the user experiences the flow as a failed login even though Firebase popup succeeded.

5. **Admin verification config must match the live Firebase project**
   - Token verification happens server-side through Firebase Admin.
   - A fallback to a hardcoded project ID or a malformed `FIREBASE_SERVICE_ACCOUNT` can make valid client tokens fail verification.

## Common failure signatures
- `auth/popup-blocked`
- `auth/popup-closed-by-user`
- `auth/unauthorized-domain`
- `auth/operation-not-allowed`
- `auth/invalid-api-key`
- backend `401` / `404` / `500` on `/api/auth/profile` or `/api/auth/register`

## Diagnostic order
1. Reproduce with browser console open.
2. Check whether popup opens and returns a user.
3. Inspect the follow-up `/api/auth/profile` and `/api/auth/register` responses.
4. Verify Firebase Admin token validation separately from the popup path.
5. Only then change UI copy or add a popup fallback.

## Useful code anchors in this repo
- `contexts/AuthContext.tsx`
- `lib/firebase.ts`
- `lib/firebase-admin.ts`
- `app/login/page.tsx`
- `app/register/page.tsx`
- `app/api/auth/profile/route.ts`
- `app/api/auth/register/route.ts`
