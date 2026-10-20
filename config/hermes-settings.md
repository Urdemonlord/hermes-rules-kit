# Hermes runtime settings that matter for this kit

Sanitized excerpt of a working single-operator setup, trimmed to the knobs that change how an agent executes work.
Not a full config. See the Hermes docs for the complete schema.

```yaml
agent:
  max_turns: 40            # hard ceiling per turn; stop long tool chains from running away
  gateway_timeout: 600
  api_max_retries: 5
  tool_use_enforcement: auto
  verify_on_stop: false    # set true if you want a verification pass before every stop
  environment_probe: true  # inject runtime facts so the agent stops guessing about the host

terminal:
  backend: local
  timeout: 180
  auto_source_bashrc: true

compression:
  enabled: true
  threshold: 0.5           # compress at half the context budget
  target_ratio: 0.2
  protect_last_n: 20       # keep the recent tail verbatim

context:
  engine: compressor

memory:
  memory_enabled: true
  user_profile_enabled: true
  memory_char_limit: 2200  # keep memory small; task detail belongs in skills and notes
  user_char_limit: 1375

delegation:
  max_concurrent_children: 1   # raise only when subtasks are truly independent
  max_spawn_depth: 1           # depth 2+ multiplies cost without multiplying proof
  child_timeout_seconds: 300
  orchestrator_enabled: true
  subagent_auto_approve: false # subagent side effects still need a human gate

skills:
  external_dirs: []        # extra skill roots outside ~/.hermes/skills
  guard_agent_created: false
  disabled: []             # disable a skill by name instead of deleting it
```

## Why these values

- **Small memory, big skills.** Memory is injected into every turn; anything that is not true for every session belongs in a skill. The char limits force that discipline.
- **Compression threshold at 0.5 with a protected tail.** Compression that runs too late loses the evidence that justified recent decisions.
- **Delegation depth 1.** Nested subagents are hard to verify; a subagent that reports success is a claim, not a proof.
- **Terminal timeout, not infinite waits.** Long jobs belong in a background process you poll once, not a blocked call.
- **Disable instead of delete.** Keeping a disabled entry documents why the capability is off.

## Not published here

Provider credentials, gateway endpoints, channel IDs, and paths specific to one operator. Keep those in your own config, out of the repo.
