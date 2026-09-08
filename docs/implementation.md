# Implementation

The app keeps the public flow server-rendered and separates form handling, abuse decisions, persistence, and presentation into small Django modules.

## Request flow

`contact.urls` exposes one named route, `contact:page`. The consuming project chooses its public path when including those URLs.

`contact.views.contact_page()` handles both methods:

1. `GET` creates a `ContactForm` with a fresh signed form token.
2. `POST` validates the form and rejects a filled honeypot without side effects.
3. The view resolves and hashes the client address, checks token age, detects replay, and applies IP/email limits.
4. Invalid or suspicious token state renders a signed arithmetic challenge while preserving visible values.
5. An accepted form calls `submit_contact_message()`.
6. Success uses Post/Redirect/Get and Django messages, redirecting to `contact:page`.

Database failures before acceptance return HTTP 503. Rate-limited requests return HTTP 429. Other validation and verification states render the page with HTTP 200.

## Form and template

`ContactForm` is a `ModelForm` for `name`, `email`, `subject`, and `message`. It trims required text values, enforces model limits and `CONTACT_MESSAGE_MAX_LENGTH`, and sets autocomplete and accessibility attributes. Conditional verification fields are added only when the view requests them.

`contact/templates/contact/page.html` is a complete default page. It renders linked inline errors and an error summary, the conditional challenge, CSRF protection, and status messages. The static stylesheet provides dark and light color schemes and a narrow responsive layout.

`contact/static/contact/js/contact.js` is progressive enhancement. It marks a valid submission busy, disables the button, changes its label, prevents a second submit, and resets state on `pageshow`. It does not send requests itself or read field values.

## Persistence and notification

`ContactMessage` is ordered newest first. Its unique nullable `submission_key_hash` provides the database-level replay guard. Indexes support unread ordering and IP-window queries. Deleting the linked Post Office row sets `notification_email` to `NULL` without deleting the contact message.

`submit_contact_message()` creates the message inside a transaction. It resolves a concurrent unique-key conflict to the existing message and does not send a second notification. The accepted row is committed before notification I/O so an email failure cannot erase the message.

Notification delivery is synchronous through the Post Office `transactional` backend. The result reports `sent`, `queued`, `failed`, `not_queued`, or `duplicate` for internal consumers.

## Admin integration

`ContactMessageAdmin` disables manual creation, keeps submitted content and notification state read-only, exposes `is_read`, and provides search, filtering, and newest-first ordering.

`get_contact_attention_items(request, admin_site=...)` is an optional selector for a custom Admin dashboard. It checks the registered `ModelAdmin` permissions, counts through `ModelAdmin.get_queryset()`, and returns no item when unavailable. The host project must call and render it; the app does not override the Admin index.

## Known boundaries

- No JSON or DRF API.
- No background worker is required by this app, but synchronous email adds request latency.
- No automatic privacy-policy or retention implementation.
- No automatic custom Admin-dashboard integration.
- No project settings, deployment configuration, or demo site in this repository.
