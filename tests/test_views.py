from unittest.mock import patch

from django.core.signing import loads
from django.db import DatabaseError
from django.test import TestCase, override_settings

from post_office.models import Email

from contact.abuse import VERIFICATION_TOKEN_SALT, get_client_ip_hash
from contact.models import ContactMessage


CONTACT_POST_OFFICE = {
    'BACKENDS': {
        'default': 'django.core.mail.backends.locmem.EmailBackend',
        'transactional': 'django.core.mail.backends.locmem.EmailBackend',
        'bulk': 'django.core.mail.backends.locmem.EmailBackend',
    },
    'BATCH_SIZE': 25,
}


@override_settings(
    CONTACT_MIN_FORM_FILL_SECONDS=0,
    CONTACT_OWNER_EMAIL='owner@example.com',
    CONTACT_SENDER_EMAIL='no-reply@example.com',
    POST_OFFICE=CONTACT_POST_OFFICE,
)
class ContactPageTests(TestCase):
    def valid_data(self, token, **overrides):
        data = {
            'name': 'Alex Example',
            'email': 'visitor@example.com',
            'subject': 'Hello',
            'message': 'Testing the contact flow.',
            'form_token': token,
        }
        data.update(overrides)
        return data

    def get_form_token(self):
        response = self.client.get('/contact/')
        self.assertEqual(response.status_code, 200)
        return response, response.context['form']['form_token'].value()

    def test_contact_page_renders_form_with_private_response_headers(self):
        response, _token = self.get_form_token()

        self.assertTemplateUsed(response, 'contact/page.html')
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response['Referrer-Policy'], 'same-origin')
        self.assertContains(response, '<h1 id="contact-title">Contact</h1>', html=True)
        self.assertContains(response, 'name="email"', html=False)
        self.assertNotContains(response, '<fieldset', html=False)
        self.assertContains(response, 'data-contact-form', html=False)
        self.assertContains(response, 'data-sending-label="Sending…"', html=False)

    def test_valid_contact_submission_redirects_and_notifies_once(self):
        _get_response, token = self.get_form_token()

        response = self.client.post('/contact/', self.valid_data(token))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/contact/')
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(ContactMessage.objects.count(), 1)
        self.assertEqual(Email.objects.count(), 1)
        result = self.client.get(response.url)
        self.assertContains(result, 'Your message has been sent')
        self.assertNotContains(result, 'Your message has been sent.')
        self.assertContains(result, 'form-status--success')
        self.assertContains(result, 'data-contact-submit')
        self.assertNotContains(result, 'class="messages"')
        self.assertNotContains(result, 'Testing the contact flow.')

        content = result.content.decode()
        self.assertLess(content.index('Your message has been sent'), content.index('name="name"'))

    def test_invalid_visible_fields_preserve_input_without_creating_message(self):
        _get_response, token = self.get_form_token()

        response = self.client.post(
            '/contact/',
            self.valid_data(token, email='not-an-email', name='Entered name'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactMessage.objects.count(), 0)
        self.assertEqual(Email.objects.count(), 0)
        self.assertContains(response, 'Enter a valid email address.')
        self.assertNotContains(response, 'Please correct the errors below.')
        self.assertContains(response, 'value="Entered name"', html=False)
        self.assertContains(response, 'aria-invalid="true"', html=False)

    def test_honeypot_rejection_is_neutral_and_has_no_side_effects(self):
        _get_response, token = self.get_form_token()

        response = self.client.post(
            '/contact/',
            self.valid_data(token, website='bot', name='Preserved name'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'We couldn’t accept this submission right now.')
        self.assertEqual(ContactMessage.objects.count(), 0)
        self.assertEqual(Email.objects.count(), 0)
        self.assertNotContains(response, 'owner@example.com')
        retry_form = response.context['form']
        self.assertEqual(retry_form['website'].value(), '')
        self.assertNotEqual(retry_form['form_token'].value(), token)
        self.assertEqual(retry_form['name'].value(), 'Preserved name')

        retry = self.client.post(
            '/contact/',
            self.valid_data(
                retry_form['form_token'].value(),
                name='Preserved name',
            ),
        )

        self.assertRedirects(retry, '/contact/')
        self.assertEqual(ContactMessage.objects.count(), 1)
        self.assertEqual(Email.objects.count(), 1)

    @override_settings(CONTACT_MIN_FORM_FILL_SECONDS=30)
    def test_suspicious_submission_gets_a_signed_challenge_and_preserves_values(self):
        _get_response, token = self.get_form_token()

        response = self.client.post('/contact/', self.valid_data(token, name='Preserved name'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<fieldset class="contact-verification">', html=False)
        self.assertContains(response, '<legend>', html=False)
        self.assertContains(response, 'Preserved name', html=False)
        self.assertContains(response, 'name="verification_token"', html=False)
        challenge_form = response.context['form']
        self.assertIn('required', str(challenge_form['verification_answer']))
        self.assertNotIn('verification_answer', challenge_form.errors)
        self.assertEqual(ContactMessage.objects.count(), 0)

    @override_settings(CONTACT_MIN_FORM_FILL_SECONDS=30)
    def test_wrong_challenge_returns_fresh_retry_state(self):
        _get_response, token = self.get_form_token()
        challenge_response = self.client.post('/contact/', self.valid_data(token))
        challenge_form = challenge_response.context['form']
        challenge_token = challenge_form['verification_token'].value()
        fresh_form_token = challenge_form['form_token'].value()

        response = self.client.post(
            '/contact/',
            self.valid_data(
                fresh_form_token,
                verification_token=challenge_token,
                verification_answer='0',
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'That verification was not completed. Please try again.')
        self.assertNotEqual(response.context['form']['verification_token'].value(), challenge_token)
        self.assertEqual(ContactMessage.objects.count(), 0)

    @override_settings(CONTACT_MIN_FORM_FILL_SECONDS=30)
    def test_correct_challenge_accepts_the_message(self):
        _get_response, token = self.get_form_token()
        challenge_response = self.client.post('/contact/', self.valid_data(token))
        challenge_form = challenge_response.context['form']
        challenge_token = challenge_form['verification_token'].value()
        fresh_form_token = challenge_form['form_token'].value()
        answer = loads(challenge_token, salt=VERIFICATION_TOKEN_SALT)['answer']

        response = self.client.post(
            '/contact/',
            self.valid_data(
                fresh_form_token,
                verification_token=challenge_token,
                verification_answer=str(answer),
            ),
        )

        self.assertRedirects(response, '/contact/')
        self.assertEqual(ContactMessage.objects.count(), 1)

    @override_settings(CONTACT_IP_LIMIT=1, CONTACT_EMAIL_LIMIT=99)
    def test_rate_limited_submission_returns_neutral_429_without_side_effects(self):
        get_response, token = self.get_form_token()
        ContactMessage.objects.create(
            name='Earlier',
            email='earlier@example.com',
            subject='Earlier',
            message='Earlier message',
            client_ip_hash=get_client_ip_hash(get_response.wsgi_request),
        )

        response = self.client.post('/contact/', self.valid_data(token))

        self.assertEqual(response.status_code, 429)
        self.assertContains(response, 'We couldn’t accept this submission right now.', status_code=429)
        self.assertEqual(ContactMessage.objects.count(), 1)
        self.assertEqual(Email.objects.count(), 0)

    def test_replaying_the_same_signed_submission_is_idempotent(self):
        _get_response, token = self.get_form_token()
        data = self.valid_data(token)

        first = self.client.post('/contact/', data)
        second = self.client.post('/contact/', data)

        self.assertRedirects(first, '/contact/')
        self.assertRedirects(second, '/contact/')
        self.assertEqual(ContactMessage.objects.count(), 1)
        self.assertEqual(Email.objects.count(), 1)

    def test_persistence_failure_returns_safe_503(self):
        _get_response, token = self.get_form_token()
        with patch('contact.views.submit_contact_message', side_effect=DatabaseError('private details')):
            response = self.client.post('/contact/', self.valid_data(token))

        self.assertEqual(response.status_code, 503)
        self.assertContains(response, 'We couldn’t send your message right now. Please try again.', status_code=503)
        self.assertNotContains(response, 'private details', status_code=503)
