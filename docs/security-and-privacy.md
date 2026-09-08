# Security and privacy

The app uses several small controls together. None of them should be treated as full DDoS protection or a replacement for normal Django and infrastructure security.

## Submission controls

- Django validates the four visible fields and escapes submitted content in normal template and Admin rendering.
- A hidden `website` field acts as a honeypot. A filled honeypot creates no message or notification and receives neutral public feedback.
- Each rendered form receives a signed random nonce and issue time.
- A missing, invalid, expired, or unusually fast form token triggers a signed arithmetic challenge.
- The challenge answer is signed, expires, and is bound to the form nonce.
- Accepted-message counts limit repeated submissions by hashed client IP and normalized email address.
- A unique hash of the signed form nonce prevents the same form from creating duplicate messages.

The signing and hashes use the consuming project’s `SECRET_KEY` with separate purpose-specific salts. Keep `SECRET_KEY` private and rotate it only with an understanding that existing form and challenge tokens will stop validating.

## Stored data

`ContactMessage` stores:

- name;
- email address;
- subject;
- message;
- creation time;
- unread/read state;
- a unique submission-nonce hash;
- a client-IP hash;
- an optional link to the Post Office notification record.

The app does not store the raw client IP. It does store the visitor’s contact details and message, and Post Office may retain a second copy in the notification record. The consuming project must choose suitable database and email-retention rules and describe this processing in its privacy notice.

## Response and logging behavior

Contact responses set `Cache-Control: no-store` and `Referrer-Policy: same-origin`. Public errors do not include the configured owner address, raw IP, signed answer, or internal exception details.

Notification failures log the message primary key and exception type. The service is designed not to log the visitor’s name, email, subject, message, hashes, or notification body in that failure message. Review the consuming project’s broader request and error logging separately.

## Admin and deployment

Protect Django Admin with the project’s normal authentication, authorization, HTTPS, and network controls. Submitted content is read-only in the included `ModelAdmin`; authorized staff can change only the read state.

Before deployment:

- use HTTPS;
- configure `ALLOWED_HOSTS`, CSRF, cookies, and proxy headers correctly;
- verify `CONTACT_TRUSTED_PROXY_CIDRS` against the actual proxy path;
- set real sender and recipient addresses outside source control;
- configure email and database retention;
- add edge rate limiting if the project’s exposure requires it;
- test failure behavior without using real visitor data.
