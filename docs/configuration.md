# Configuration

The consuming Django project owns all configuration. The app does not read environment variables directly and does not define fallback settings internally.

## Install and route the app

Add the app and Post Office to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "post_office",
    "contact",
]
```

Mount the URLs:

```python
from django.urls import include, path

urlpatterns = [
    path("contact/", include("contact.urls")),
]
```

Apply both applications’ migrations:

```bash
python manage.py migrate
```

The project must use Django template and static-files loaders that discover app-owned files. The default page is `contact/page.html`, with assets under `contact/static/contact/`.

## Required contact settings

Every setting in this table must exist in the consuming project.

| Setting | Purpose | Example |
| --- | --- | --- |
| `CONTACT_OWNER_EMAIL` | Recipient for accepted contact notifications | `"you@example.com"` |
| `CONTACT_SENDER_EMAIL` | Fixed sender used for notifications | `"no-reply@example.com"` |
| `CONTACT_IP_LIMIT` | Accepted-message limit per hashed client IP | `5` |
| `CONTACT_IP_WINDOW_SECONDS` | Time window for the IP limit | `3600` |
| `CONTACT_EMAIL_LIMIT` | Accepted-message limit per normalized email address | `3` |
| `CONTACT_EMAIL_WINDOW_SECONDS` | Time window for the email limit | `86400` |
| `CONTACT_MIN_FORM_FILL_SECONDS` | Minimum form age before verification is required | `3` |
| `CONTACT_FORM_TOKEN_MAX_AGE_SECONDS` | Maximum signed form-token age | `3600` |
| `CONTACT_VERIFICATION_MAX_AGE_SECONDS` | Maximum signed challenge age | `600` |
| `CONTACT_MESSAGE_MAX_LENGTH` | Maximum message length enforced by the form | `5000` |
| `CONTACT_TRUSTED_PROXY_CIDRS` | Networks allowed to supply forwarded client-IP headers | `["127.0.0.1/32", "::1/128"]` |

These examples are starting points, not automatic defaults. Use positive integer limits and review them for the project’s traffic.

## Trusted proxies

The app starts with `REMOTE_ADDR`. It reads `X-Forwarded-For` or `X-Real-IP` only when `REMOTE_ADDR` belongs to `CONTACT_TRUSTED_PROXY_CIDRS`.

Only list networks controlled by your deployment. Adding a public or overly broad network can let clients influence the address used for throttling. When `X-Forwarded-For` contains multiple values, the app uses the last hop.

## Email delivery

Configure `django-post-office` with a backend named `transactional`. The app sends notifications with `priority="now"`, so the request attempts delivery synchronously.

The notification uses:

- `CONTACT_SENDER_EMAIL` as the fixed sender;
- `CONTACT_OWNER_EMAIL` as the only recipient;
- the visitor’s validated email address as `Reply-To`;
- a fixed subject of `New contact message`;
- a plain-text body.

An email setup or delivery exception does not remove an accepted `ContactMessage`. The public flow still reports success, while the Admin notification status and application logs provide the operational signal.

## Template customization

The included template is a complete HTML page. A project can override `contact/page.html` through Django’s normal template precedence, or edit the copied app template directly. Keep the field IDs, error associations, hidden protection fields, CSRF token, and ordinary POST behavior when changing the markup.
