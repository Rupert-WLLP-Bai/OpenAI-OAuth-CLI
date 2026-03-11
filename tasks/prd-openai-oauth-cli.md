# PRD: OpenAI OAuth CLI

## 1. Introduction

Build a standalone Python CLI that accepts an OpenAI account email address and password, automates the browser login flow, handles verification and consent screens, captures the OAuth callback, exchanges the authorization code for tokens, and prints the resulting `refresh_token`.

The tool exists to turn a manually usable OpenAI account into a machine-usable `refresh_token` with a single local CLI command.

## 2. Goals

- Accept `email` and `password` as CLI input
- Default the password to the fixed project-wide value when omitted
- Use browser automation to complete the OpenAI web login flow
- Use mailbox metadata from the local account export file when email verification is required
- Capture the OAuth callback on localhost
- Exchange the authorization code for tokens
- Print only the `refresh_token` to stdout

## 3. User Stories

### US-001: Start login from the terminal
**Description:** As an operator, I want to run one command with an email and password so that I can get a `refresh_token` without manual browser copying steps.

**Acceptance Criteria:**
- [ ] `openai-oauth-cli login --email user@example.com` starts the login flow
- [ ] `--password` is optional and defaults to the project password
- [ ] CLI exits non-zero on failure

### US-002: Handle browser login states
**Description:** As an operator, I want the tool to move through email, password, verification, consent, and callback screens so that slow page transitions do not break login.

**Acceptance Criteria:**
- [ ] Login flow uses a unified state machine
- [ ] Password page transitions tolerate delayed rendering
- [ ] Consent screen clicks are handled through the same state machine
- [ ] Error pages fail explicitly

### US-003: Read verification codes from mailbox metadata
**Description:** As an operator, I want the tool to load mailbox credentials for an account so that verification codes can be fetched automatically when OpenAI asks for them.

**Acceptance Criteria:**
- [ ] Account export file is parsed into mailbox metadata records
- [ ] Email lookup must be unique
- [ ] Verification code provider can fetch a code for the selected account

### US-004: Receive callback and exchange token
**Description:** As an operator, I want the tool to receive the OAuth callback and exchange the code for tokens so that I do not have to manually copy callback URLs.

**Acceptance Criteria:**
- [ ] Local callback server starts on a configurable port
- [ ] Callback captures `code`, `state`, and OAuth errors
- [ ] `state` must be validated before token exchange
- [ ] Token exchange returns a `refresh_token`

### US-005: Print only the result token
**Description:** As an operator, I want stdout to contain only the `refresh_token` so that I can script around the CLI easily.

**Acceptance Criteria:**
- [ ] Success path prints only the `refresh_token`
- [ ] Logs and progress go to stderr
- [ ] Missing `refresh_token` is treated as failure

## 4. Functional Requirements

- FR-1: The CLI must expose a `login` command.
- FR-2: The `login` command must require `--email`.
- FR-3: The `login` command must accept `--password` and default to the project password when omitted.
- FR-4: The system must generate PKCE material for each login attempt.
- FR-5: The system must launch a `patchright` browser session.
- FR-6: The system must classify page states as `email`, `password`, `verification_code`, `consent`, `callback`, `error`, or `unknown`.
- FR-7: The system must fetch mailbox metadata from the local account export file.
- FR-8: The system must fetch verification codes through a mailbox provider when required.
- FR-9: The system must start a localhost callback server and wait for the OAuth callback.
- FR-10: The system must exchange the authorization code for tokens using the OpenAI token endpoint.
- FR-11: The system must print only the `refresh_token` on success.

## 5. Non-Goals

- No batch-account processing
- No upstream proxying
- No account registration automation
- No token persistence as the primary workflow
- No remote service or web UI

## 6. Design Considerations

- Keep the browser automation flow behind a small browser driver interface.
- Keep page detection separate from page actions.
- Keep mailbox access behind a verification-code provider abstraction.

## 7. Technical Considerations

- `patchright` is required for browser automation.
- `aiohttp` is used for both callback server and token exchange.
- The account export file is treated as a local secret input and should stay under `secrets/`.
- The fixed password is intentionally hardcoded as the project default.

## 8. Success Metrics

- One command can produce a `refresh_token` for a valid account.
- Slow page transitions no longer fail at the password step.
- Tests cover OAuth helpers, callback server, mailbox parsing, page classification, state-machine behavior, and CLI wiring.

## 9. Open Questions

- Whether the project should later support alternative mailbox providers
- Whether refresh tokens should later be written to a file in addition to stdout
