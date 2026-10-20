# Terse Operator Continuation Pattern

When the operator responds with short affirmative prompts such as:
- "gas"
- "iya"
- "lanjut"
- "continue"

Treat this as explicit approval to proceed with the next phase of the current mission without asking for clarification or presenting options.

This pattern was observed during the the security gateway positioning + landing page deployment session (June 2026). The operator repeatedly used these prompts to drive fully autonomous execution through the full OmO loop including production deployment.

**Implementation note**: In Phase 7 Minimal Prompt Mode, these tokens should map directly to "continue current lane" rather than triggering clarification dialogs.