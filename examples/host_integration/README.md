# Host Integration Reference

The Contact app is already portable as the root-level `contact` package. Adapt
the accompanying URL and settings snippets in an existing Django project, add
`contact` and Django Post Office to `INSTALLED_APPS`, then run migrations and
collect static files.

Keep the trusted-proxy list narrow. The example trusts loopback only; add a
proxy network only when it is controlled by the deployment.
