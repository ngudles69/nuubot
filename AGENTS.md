# AGENTS.md

Rules for agents in `D:\rust\nuubot`.

## Start Here

- Fresh session: read `AGENTS.md`, then `wiki/AGENTS.md`.
- Use `wiki/AGENTS.md` as the wiki map. Follow files from there only when
  needed.
- Startup output starts with `READY.`, gives one concrete recommendation, then
  stops.

## Truth

- `wiki/**`: durable project knowledge and facts. Follow `wiki/AGENTS.md`.
- `.project/**`: project management. Follow `.project/AGENTS.md`.
- `.research/**`: transient project facts valid for specific tasks only.
  Follow `.research/AGENTS.md`.
- `.project/**` and `.research/**` can be out of date and are not facts.
- Repo files beat memory and chat.
- If sources conflict, say so.

## Reference Repos

- `D:\rust\nuutrader6`: working reference code. Use it for patterns, not
  wholesale copying.
- `D:\rust\nuutrader-references\BlackBot`: grid-bot behavior reference. Use it
  to understand the strategy, not as a codebase to paste in.

## Work

- Direct. Short. Concrete.
- Separate fact, inference, and recommendation.
- Evidence for real claims: path, command, artifact, or runtime state.
- Inspect local docs/code before asking.
- Read only the docs needed for the task.
- Do not code from talk.
- Code only after explicit edit/create/add/change/migrate/install/run/fix/proceed.
- No fallback unless the user explicitly approves it.
- Do not revert user changes unless the user asks.

## Commands

- Use repo commands directly.
- Use PowerShell only when there is no practical Unix-style alternative.
- Search with `rg -n ...`.
- Find files with `rg --files`.
- In PowerShell, single-quote `rg` regex patterns. Do not wrap regex patterns
  in double quotes. PowerShell mangles `|`, `()`, backslashes, and embedded
  quotes before `rg` sees them.
- Use simple repeated `rg -n literal ...` searches instead of complex
  alternation when quoting gets noisy.
- Never use PowerShell for regex/search work.
- If PowerShell is needed, use:
  `powershell -NoProfile -Command '...'`.
- Keep PowerShell commands simple.
- Use `apply_patch` for manual file edits.
- Before delete operations, print or count the exact target list first.

## Code

- Follow Ponytail rules: unless needed now, do not add it.
- Use the standard library before custom code.
- Use the platform or installed library directly before wrapping it.
- Delete over add.
- Boring over clever.
- Fewest files wins.
- No boilerplate.
- No scaffold for later.
- No interface with one implementation.
- No factory for one product.
- No config for a value that never changes.
- Fail fast. Fail loud.
- Validate at boundaries: file parse, DB load, generated config, and component
  init. After init succeeds, trust initialized runtime objects.
- Do not hide bad input, bad output, or source errors.
- Keep one owner for each job.
- No future helpers. No future wrappers. No dead stubs.
- Remove unused helpers.
- Comments explain intent, not method.
- Test real code paths by default.
- Use focused proof after each finished slice.

## User Phrases

- `stop` or `standby for more instructions`: stop tool use. Wait.
- `startup`, `$startup`, `read context`: run the startup flow and stop.
- `project setup`, `structural stuff`, `not domain`: structure only.
- `should`, `can we`, `what if`, `why`, `recommend`, `what are we doing`:
  answer only. Not approval.
