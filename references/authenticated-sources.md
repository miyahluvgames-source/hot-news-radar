# Authenticated Sources

Use this reference when a target page requires a logged-in account, workspace permission, SSO, MFA, CAPTCHA, region access, or another user-controlled gate.

## Principle

Authenticated review is allowed only when the user is authorized to access the page and wants the agent to inspect task-relevant visible evidence. The user performs all login steps directly. The agent never handles secrets.

## Preflight

Before opening the page, the agent should ask or confirm:

- What exact URL, account, workspace, or page should be inspected?
- What question must the evidence answer?
- Is the user authorized to access this page?
- Are there private areas that must not be inspected?
- Should screenshots be avoided, redacted, or allowed?
- Should the session be closed or logged out afterward?

## Controlled Login Flow

1. Open the exact target domain in a visible browser controlled by the agent environment.
2. Read the domain aloud or show it in the task log before the user logs in.
3. Pause and ask the user to complete login directly.
4. The user handles password, SSO, passkey, CAPTCHA, MFA, device prompts, and recovery prompts.
5. The agent does not request, read, summarize, or store credentials, MFA codes, cookies, tokens, recovery codes, private messages, or payment details.
6. After login, ask the user to navigate to or confirm the exact page for inspection.
7. Confirm final URL, page title, account/workspace context if relevant, visible timestamp, and loaded state.
8. If the page still shows an error, empty state, rate limit, permission warning, challenge, or paywall, retry once only with user approval.
9. If access remains blocked, record a coverage gap and stop that lane.

## Evidence Collection

Capture only what the task needs:

- final URL,
- page title,
- source or page identity,
- visible publication time or update time,
- task-relevant text,
- task-relevant counters or status labels,
- selected links,
- safe screenshot only when necessary,
- collection time,
- redactions performed,
- unresolved gaps.

## Redaction Rules

Avoid or redact:

- email addresses and phone numbers,
- account IDs, customer IDs, order IDs, balances, billing data, payment data,
- private messages, notification contents, drafts, settings, and personal profile details,
- cookies, tokens, session identifiers, API keys, recovery codes, and MFA codes,
- unrelated page regions.

## Output Language

Use evidence class `authenticated_visible_review` for claims supported by a user-authorized logged-in view.

If the page could not be inspected, use a coverage gap with:

- reason,
- URL,
- visible state,
- whether login was completed by the user,
- whether a permission, CAPTCHA, paywall, rate-limit, or region gate remained,
- safe next step.

Do not write the user's account name or private identifiers unless they are directly necessary and the user asked to include them.

