# A small Django contact form

I built this as a focused contact app for Django projects that need a proper form without pulling in a larger frontend or contact-management system.

It gives visitors four fields, stores accepted messages in the database, sends a plain-text notification, and keeps the form usable when JavaScript is disabled. It also includes a few quiet protections against common automated submissions: a honeypot, signed form timing, a small verification challenge when needed, throttling, and replay protection.

The default template is included, so the app works immediately once it is added to a Django project. You can keep the template as it is, extend it from your own site shell, or replace it completely.

## What is included

- A server-rendered `GET /contact/` and `POST /contact/` flow.
- `ContactMessage` storage and a read-only Django Admin view.
- Plain-text notification delivery through `django-post-office`.
- Signed form tokens and verification challenges using Django’s signing tools.
- Hashed client-IP and email throttling values. Raw IP addresses are not stored.
- A dark-first responsive default template with a light colour-scheme fallback.
- Focused tests covering the form, model, abuse checks, service, Admin, and views.

## Install it

Copy the `contact/` package into your project and add the app and its dependency:

```python
INSTALLED_APPS = [
    # ...
    "post_office",
    "contact",
]
```

Include the URLs wherever you want the form to live:

```python
from django.urls import include, path

urlpatterns = [
    path("contact/", include("contact.urls")),
]
```

Then run:

```bash
python manage.py migrate
```

The project must use Django’s normal template and static-files loaders. The app owns its default template and static assets, so no other project app is required for presentation.

Copy-ready URL and settings snippets are available in the
[`examples/host_integration/`](examples/host_integration/) folder.

## Settings

The two notification addresses are required for real delivery:

```python
CONTACT_OWNER_EMAIL = "you@example.com"
CONTACT_SENDER_EMAIL = "no-reply@example.com"
```

The app also expects a normal `SECRET_KEY` and these settings. The numeric values below are sensible starting points, but I would review them for the traffic and proxy setup of each project:

```python
CONTACT_IP_LIMIT = 5
CONTACT_IP_WINDOW_SECONDS = 3600
CONTACT_EMAIL_LIMIT = 3
CONTACT_EMAIL_WINDOW_SECONDS = 86400
CONTACT_MIN_FORM_FILL_SECONDS = 3
CONTACT_FORM_TOKEN_MAX_AGE_SECONDS = 3600
CONTACT_VERIFICATION_MAX_AGE_SECONDS = 600
CONTACT_MESSAGE_MAX_LENGTH = 5000
CONTACT_TRUSTED_PROXY_CIDRS = ["127.0.0.1/32", "::1/128"]
```

Only add your real reverse-proxy networks to `CONTACT_TRUSTED_PROXY_CIDRS`. Do not trust arbitrary forwarded headers from the public internet.

Configure `django-post-office` with a `transactional` backend, or adjust `contact/services.py` to use the email delivery approach already used by your project. In development, a console or in-memory email backend is enough.

## Customise the page

The default page lives at `contact/templates/contact/page.html`. It is deliberately ordinary Django template code. You can override it in your project with the same template path, or copy it into a site-owned template and change the shell, copy, and styling.

The default assets live under `contact/static/contact/`. They are small on purpose. There is no frontend framework and no API dependency.

## Documentation

- [Overview](docs/overview.md)
- [Configuration](docs/configuration.md)
- [Security and privacy](docs/security-and-privacy.md)
- [Implementation](docs/implementation.md)
- [Testing](docs/testing.md)

## Security and privacy notes

The app stores the visitor’s name, email address, subject, message, creation time, read state, and the hashes needed for replay and throttle checks. It sends accepted messages to the configured owner address through the configured email backend.

The app does not provide a public message API, visitor accounts, self-service deletion, or a separate mobile client. Add those as separate decisions if your project needs them.

Use HTTPS, protect Django Admin as you normally would, keep `SECRET_KEY` private, and configure database and email retention to match your privacy requirements.

## Tests

The test suite expects a Django test project that includes `contact`, `post_office`, a database, and the settings listed above. Run it from the project that contains your Django settings:

```bash
python manage.py test tests
```

This repository is a reusable app showcase rather than a complete Django project. It intentionally does not include project settings, deployment configuration, or a demo site.

## License

MIT. See [LICENSE](LICENSE).
