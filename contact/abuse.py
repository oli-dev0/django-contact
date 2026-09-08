import secrets
import time
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, loads, salted_hmac, dumps
from django.utils import timezone

from .models import ContactMessage


def _ip_is_allowed(client_ip, allowed_cidrs):
    from ipaddress import ip_address, ip_network

    try:
        parsed_ip = ip_address(client_ip)
    except ValueError:
        return False
    return any(
        parsed_ip in ip_network(cidr, strict=False)
        for cidr in allowed_cidrs
        if _valid_network(cidr)
    )


def _valid_network(cidr):
    from ipaddress import ip_network

    try:
        ip_network(cidr, strict=False)
    except ValueError:
        return False
    return True


def _get_trusted_client_ip(request, trusted_proxy_cidrs):
    remote_addr = request.META.get('REMOTE_ADDR', '').strip()
    if not _ip_is_allowed(remote_addr, trusted_proxy_cidrs):
        return remote_addr
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[-1].strip()
    real_ip = request.META.get('HTTP_X_REAL_IP')
    return real_ip.strip() if real_ip else remote_addr


FORM_TOKEN_SALT = 'contact.form-token'
VERIFICATION_TOKEN_SALT = 'contact.verification-token'
SUBMISSION_KEY_SALT = 'contact.submission-key'
CLIENT_IP_SALT = 'contact.client-ip'


class AbuseOutcome(StrEnum):
    ALLOWED = 'allowed'
    VERIFICATION_REQUIRED = 'verification_required'
    HONEYPOT_REJECTED = 'honeypot_rejected'
    RATE_LIMITED = 'rate_limited'


@dataclass(frozen=True)
class FormTokenState:
    outcome: AbuseOutcome
    nonce: str | None


@dataclass(frozen=True)
class VerificationChallenge:
    question: str
    token: str
    nonce: str


def create_form_token(*, nonce=None):
    nonce = nonce or secrets.token_urlsafe(24)
    return dumps(
        {'nonce': nonce, 'issued_at': int(time.time())},
        salt=FORM_TOKEN_SALT,
    )


def _load_form_token(token, *, max_age=None):
    return loads(token, salt=FORM_TOKEN_SALT, max_age=max_age)


def get_signed_form_nonce(token):
    """Return a nonce from a correctly signed token, even when its age expired."""
    if not token:
        return None
    try:
        data = _load_form_token(token)
    except (BadSignature, TypeError, ValueError):
        return None
    nonce = data.get('nonce')
    return nonce if isinstance(nonce, str) and nonce else None


def inspect_form_token(token, *, now=None):
    if not token:
        return FormTokenState(AbuseOutcome.VERIFICATION_REQUIRED, None)

    try:
        data = _load_form_token(token, max_age=settings.CONTACT_FORM_TOKEN_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return FormTokenState(AbuseOutcome.VERIFICATION_REQUIRED, get_signed_form_nonce(token))

    nonce = data.get('nonce')
    issued_at = data.get('issued_at')
    if not isinstance(nonce, str) or not nonce or not isinstance(issued_at, int):
        return FormTokenState(AbuseOutcome.VERIFICATION_REQUIRED, None)

    current_time = time.time() if now is None else now
    if current_time - issued_at < settings.CONTACT_MIN_FORM_FILL_SECONDS:
        return FormTokenState(AbuseOutcome.VERIFICATION_REQUIRED, nonce)
    return FormTokenState(AbuseOutcome.ALLOWED, nonce)


def create_verification_challenge(nonce):
    first = secrets.randbelow(9) + 1
    second = secrets.randbelow(9) + 1
    return VerificationChallenge(
        question=f'{first} + {second} = ?',
        token=dumps(
            {
                'answer': first + second,
                'nonce': nonce,
                'issued_at': int(time.time()),
                'challenge_id': secrets.token_urlsafe(12),
            },
            salt=VERIFICATION_TOKEN_SALT,
        ),
        nonce=nonce,
    )


def validate_verification(*, token, answer, submission_nonce):
    if not token or not submission_nonce:
        return False
    try:
        data = loads(
            token,
            salt=VERIFICATION_TOKEN_SALT,
            max_age=settings.CONTACT_VERIFICATION_MAX_AGE_SECONDS,
        )
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return False

    if data.get('nonce') != submission_nonce:
        return False
    try:
        submitted_answer = int(str(answer).strip())
    except (TypeError, ValueError):
        return False
    expected_answer = data.get('answer')
    return isinstance(expected_answer, int) and secrets.compare_digest(
        str(submitted_answer),
        str(expected_answer),
    )


def normalize_email_for_throttle(email):
    return email.strip().lower()


def hash_submission_nonce(nonce):
    return salted_hmac(
        SUBMISSION_KEY_SALT,
        nonce,
        secret=settings.SECRET_KEY,
        algorithm='sha256',
    ).hexdigest()


def get_client_ip_hash(request):
    client_ip = _get_trusted_client_ip(request, settings.CONTACT_TRUSTED_PROXY_CIDRS)
    return salted_hmac(
        CLIENT_IP_SALT,
        client_ip,
        secret=settings.SECRET_KEY,
        algorithm='sha256',
    ).hexdigest()


def get_honeypot_outcome(value):
    return AbuseOutcome.HONEYPOT_REJECTED if value.strip() else AbuseOutcome.ALLOWED


def get_throttle_outcome(*, client_ip_hash, normalized_email, now=None):
    current_time = now or timezone.now()
    ip_cutoff = current_time - timedelta(seconds=settings.CONTACT_IP_WINDOW_SECONDS)
    email_cutoff = current_time - timedelta(seconds=settings.CONTACT_EMAIL_WINDOW_SECONDS)
    ip_count = ContactMessage.objects.filter(
        client_ip_hash=client_ip_hash,
        created_at__gte=ip_cutoff,
    ).count()
    if ip_count >= settings.CONTACT_IP_LIMIT:
        return AbuseOutcome.RATE_LIMITED

    email_count = ContactMessage.objects.filter(
        email__iexact=normalized_email,
        created_at__gte=email_cutoff,
    ).count()
    if email_count >= settings.CONTACT_EMAIL_LIMIT:
        return AbuseOutcome.RATE_LIMITED
    return AbuseOutcome.ALLOWED
