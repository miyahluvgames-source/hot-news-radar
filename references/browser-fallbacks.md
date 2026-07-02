# Browser Fallbacks

Browser fallback is a recovery path, not a bypass mechanism.

## Use Browser Review When

- HTTP fetch returns 401, 403, 429, redirect loops, blank text, or challenge content.
- The page requires JavaScript rendering.
- A social page shows an error state, empty results, or personalized content.
- The user explicitly asks to inspect a logged-in or profile-dependent page they are authorized to access.
- A claim depends on visible state, buttons, reply counts, chart values, video thumbnails, or dynamic content.

## Safe Recovery Plan

1. Open the target in a user-controlled visible browser session when allowed.
2. Confirm the page title, URL, and visible text.
3. Capture evidence: screenshot, DOM text, selected links, timestamps, and visible status.
4. Record whether the page requires login, payment, CAPTCHA, permission, or region access.
5. If the page remains blocked, report a coverage gap and use alternate public sources.

For login-gated pages, use `--auth-session-guide` and follow `references/authenticated-sources.md`.

## Do Not

- Do not bypass login, paywalls, CAPTCHAs, permission gates, robots rules, or anti-abuse controls.
- Do not treat an error page as evidence.
- Do not scrape personal or private content without authorization.
- Do not hide partial coverage from the user.

## Optional Playwright Mode

`--browser-fallback playwright` renders user-provided URLs with headless Chromium. It is useful for JavaScript pages that are publicly accessible. It is not a replacement for authenticated visible review.

Do not use headless browser mode for credentials, MFA, SSO, or account-sensitive pages unless the user explicitly controls that environment and accepts the privacy implications. The safer default is a visible browser where the user performs login directly.

