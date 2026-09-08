# Contact app overview

This is a reusable, server-rendered Django contact form. It collects a visitor’s name, email address, subject, and message, stores accepted submissions in the database, and attempts to notify one configured recipient by email.

The repository contains the Django app and focused tests. It is not a complete Django project, so the consuming project provides settings, the root URL configuration, database, email backend, and deployment setup.

The showcase includes a self-contained default page that a host project can customize.

## Public flow

Mount `contact.urls` at the path you want to use. The included examples use `/contact/`.

- `GET` renders a fresh form with a signed form token.
- `POST` validates the visible fields and applies the abuse checks.
- A normal accepted submission creates one `ContactMessage`, attempts one owner notification, and redirects back to `contact:page`.
- Validation, verification, throttling, and persistence failures render the same page with an appropriate status.

The form works without JavaScript. The included script only prevents repeat clicks while a valid submission is navigating and restores the button after browser history navigation.

## Staff flow

`ContactMessage` is registered with Django Admin. Submitted content is read-only, while authorized staff can change `is_read`. The list supports unread filtering, searching, newest-first ordering, and notification status.

`get_contact_attention_items()` is an optional integration helper for a custom Admin dashboard. The app does not alter Django’s Admin index automatically. A consuming project can call the helper from its own Admin index context if it wants an unread-message reminder.

## Main dependencies

- Django for forms, templates, signing, persistence, messages, Admin, and translations.
- `django-post-office` for notification delivery and retained delivery status.
- A configured database and a `transactional` Post Office backend.

## Public boundaries

The app intentionally does not include a JSON API, visitor accounts, a CRM, multiple recipients, deployment configuration, or a complete demo project. The default template and static assets are included and can be replaced by the consuming project.

See [Configuration](configuration.md) before integrating the app and [Security and privacy](security-and-privacy.md) before deploying it.
