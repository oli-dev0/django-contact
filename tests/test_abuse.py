import time
from unittest.mock import patch

from django.core.signing import SignatureExpired
from django.test import RequestFactory, TestCase, override_settings

from contact.abuse import (
    AbuseOutcome,
    create_form_token,
    create_verification_challenge,
    get_client_ip_hash,
    get_honeypot_outcome,
    get_signed_form_nonce,
    get_throttle_outcome,
    hash_submission_nonce,
    inspect_form_token,
    normalize_email_for_throttle,
    validate_verification,
)
from contact.models import ContactMessage


class ContactAbuseTests(TestCase):
    def test_form_age_token_passes_after_minimum_and_before_expiry(self):
        token = create_form_token()
        issued_at = int(time.time())

        state = inspect_form_token(token, now=issued_at + 4)

        self.assertEqual(state.outcome, AbuseOutcome.ALLOWED)
        self.assertIsNotNone(state.nonce)

    @override_settings(CONTACT_MIN_FORM_FILL_SECONDS=3)
    def test_too_fast_missing_tampered_and_expired_tokens_require_verification(self):
        token = create_form_token()
        issued_at = int(time.time())

        self.assertEqual(inspect_form_token(token, now=issued_at).outcome, AbuseOutcome.VERIFICATION_REQUIRED)
        self.assertEqual(inspect_form_token('', now=issued_at).outcome, AbuseOutcome.VERIFICATION_REQUIRED)
        self.assertEqual(inspect_form_token(f'{token}tampered', now=issued_at).outcome, AbuseOutcome.VERIFICATION_REQUIRED)

        with patch('contact.abuse._load_form_token', side_effect=SignatureExpired('expired')):
            self.assertEqual(inspect_form_token(token, now=issued_at + 5).outcome, AbuseOutcome.VERIFICATION_REQUIRED)

    def test_challenge_requires_matching_nonce_and_fresh_signed_answer(self):
        challenge = create_verification_challenge('nonce-a')

        # The question is presentation-only; the signed answer is the authority.
        from django.core.signing import loads
        expected = loads(challenge.token, salt='contact.verification-token')['answer']

        self.assertTrue(validate_verification(
            token=challenge.token,
            answer=expected,
            submission_nonce='nonce-a',
        ))
        self.assertFalse(validate_verification(
            token=challenge.token,
            answer=int(expected) + 1,
            submission_nonce='nonce-a',
        ))
        self.assertFalse(validate_verification(
            token=challenge.token,
            answer=expected,
            submission_nonce='nonce-b',
        ))
        self.assertFalse(validate_verification(
            token=f'{challenge.token}tampered',
            answer=expected,
            submission_nonce='nonce-a',
        ))

        with override_settings(CONTACT_VERIFICATION_MAX_AGE_SECONDS=0):
            self.assertFalse(validate_verification(
                token=challenge.token,
                answer=expected,
                submission_nonce='nonce-a',
            ))

    def test_trusted_proxy_resolution_hashes_only_the_resolved_address(self):
        factory = RequestFactory()
        request = factory.post(
            '/contact/',
            REMOTE_ADDR='10.0.0.2',
            HTTP_X_FORWARDED_FOR='203.0.113.8, 198.51.100.4',
        )
        with override_settings(CONTACT_TRUSTED_PROXY_CIDRS=['10.0.0.0/8']):
            trusted_hash = get_client_ip_hash(request)

        direct_request = factory.post(
            '/contact/',
            REMOTE_ADDR='203.0.113.8',
            HTTP_X_FORWARDED_FOR='198.51.100.4',
        )
        with override_settings(CONTACT_TRUSTED_PROXY_CIDRS=['10.0.0.0/8']):
            direct_hash = get_client_ip_hash(direct_request)

        self.assertEqual(len(trusted_hash), 64)
        self.assertNotEqual(trusted_hash, direct_hash)
        self.assertNotIn('198.51.100.4', trusted_hash)

    @override_settings(CONTACT_IP_LIMIT=2, CONTACT_EMAIL_LIMIT=2)
    def test_ip_and_normalized_email_limits_use_accepted_messages(self):
        ip_hash = hash_submission_nonce('client')
        ContactMessage.objects.create(
            name='Alex Example',
            email='Visitor@Example.com',
            subject='One',
            message='One',
            client_ip_hash=ip_hash,
        )

        self.assertEqual(
            get_throttle_outcome(
                client_ip_hash=ip_hash,
                normalized_email=normalize_email_for_throttle(' visitor@example.com '),
            ),
            AbuseOutcome.ALLOWED,
        )
        ContactMessage.objects.create(
            name='Alex Example',
            email='visitor@example.com',
            subject='Two',
            message='Two',
            client_ip_hash=ip_hash,
        )
        self.assertEqual(
            get_throttle_outcome(
                client_ip_hash=ip_hash,
                normalized_email='visitor@example.com',
            ),
            AbuseOutcome.RATE_LIMITED,
        )

    def test_honeypot_outcome_is_explicit_and_no_message_is_created_by_helper(self):
        self.assertEqual(get_honeypot_outcome(''), AbuseOutcome.ALLOWED)
        self.assertEqual(get_honeypot_outcome('filled'), AbuseOutcome.HONEYPOT_REJECTED)
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_signed_nonce_hash_has_a_purpose_specific_length(self):
        nonce = get_signed_form_nonce(create_form_token())

        self.assertEqual(len(hash_submission_nonce(nonce)), 64)
