# Testing

The repository contains focused Django tests under `tests/`. They require a host Django test project with `contact` and `post_office` installed, a database, URL routing for `/contact/`, and the required contact settings.

## Coverage

- `test_forms.py` covers visible fields, hidden protection fields, trimming, required values, email validation, message limits, error metadata, and autofocus behavior.
- `test_abuse.py` covers form-token age and tampering, challenge binding and expiry, trusted-proxy handling, hashed throttles, honeypot outcomes, and nonce hashing.
- `test_models.py` covers unread defaults, newest-first ordering, unique submission hashes, Post Office deletion behavior, and indexes.
- `test_services.py` covers persistence, plain-text notification details, duplicate protection, failed delivery state, contained notification exceptions, and database failure behavior.
- `test_views.py` covers rendering, private response headers, Post/Redirect/Get, validation, honeypot rejection, verification, rate limiting, replay idempotency, and safe 503 responses.
- `test_admin.py` covers read-only submitted content, read-state editing, permissions, queryset scoping, safe selector failures, and the optional attention-item contract.

## Running the tests

From a Django project that includes this repository’s `tests` package:

```bash
python manage.py test tests
```

The test settings should use an isolated database and a non-network Post Office backend. The existing tests use Django’s in-memory email backend for `default`, `transactional`, and `bulk` aliases.

## Additional checks

Run the checks already used by the consuming project. At minimum:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput
```

Also run the project’s Python linter and check `contact/static/contact/js/contact.js` with its JavaScript tooling.

## Known gaps

This repository does not contain a standalone Django settings module, `manage.py`, browser automation suite, or deployment test environment. The default page should therefore receive manual browser checks inside the consuming project for:

- narrow layouts;
- keyboard-only submission and error navigation;
- dark and light system color schemes;
- JavaScript-disabled submission;
- browser back/forward button reset;
- console errors and missing static assets;
- real email-provider behavior in a safe non-production environment.
