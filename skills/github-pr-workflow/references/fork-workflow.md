# Fork Workflow for Third-Party Contributions

When contributing to a repository where the authenticated user does not have write access (e.g., an open-source project or another user's repository), pushing directly to the original (`origin`) remote will result in a `403 Permission denied` error.

**Standard Workflow for Third-Party Repositories:**

1. **Verify Access / Fork First:** Do not attempt to push directly to a repository unless you are certain the authenticated user has write access. If they don't, ask the user to fork the repository on GitHub first.
2. **Configure Remotes:**
   - Rename the original repository remote to `upstream`: `git remote rename origin upstream`
   - Add the user's fork as the new `origin`: `git remote add origin https://github.com/<User>/<Repo>.git`
3. **Branch & Commit:** Work on a feature branch (`git checkout -b feature-branch`).
4. **Push to Fork:** `git push -u origin feature-branch`
5. **Open Pull Request:** Open the PR against the `upstream` repository.
   - The `head` must include the fork owner's username: `<fork-owner>:<branch-name>`
   - Example via GitHub API (if `gh` CLI is not available):
     ```bash
     curl -s -H "Authorization: token $GITHUB_TOKEN" \
          -H "Accept: application/vnd.github.v3+json" \
          -X POST https://api.github.com/repos/<upstream-owner>/<repo>/pulls \
          -d '{"title":"...","head":"<fork-owner>:<branch-name>","base":"main","body":"..."}'
     ```