from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase, override_settings

from post_office.models import Email, STATUS

from contact.models import ContactMessage
from contact.services import submit_contact_message


CONTACT_POST_OFFICE = {
    'BACKENDS': {
        'default': 'django.core.mail.backends.locmem.EmailBackend',
        'transactional': 'django.core.mail.backends.locmem.EmailBackend',
        'bulk': 'django.core.mail.backends.locmem.EmailBackend',
    },
    'BATCH_SIZE': 25,
}


@override_settings(
    CONTACT_OWNER_EMAIL='owner@example.com',
    CONTACT_SENDER_EMAIL='no-reply@example.com',
    POST_OFFICE=CONTACT_POST_OFFICE,
)
class ContactServiceTests(TestCase):
    def values(self, **overrides):
        values = {
            'name': 'Alex Example',
            'email': 'visitor@example.com',
            'subject': 'Hello',
            'message': 'Testing the contact service.',
        }
        values.update(overrides)
        return values

    def submit(self, **overrides):
        return submit_contact_message(
            values=self.values(),
            client_ip_hash='a' * 64,
            submission_key_hash=overrides.pop('submission_key_hash', 'b' * 64),
        )

    def test_new_submission_persists_metadata_and_one_notification(self):
        result = self.submit()

        self.assertTrue(result.created)
        self.assertEqual(result.notification_status, 'sent')
        message = ContactMessage.objects.get()
        self.assertEqual(message.name, 'Alex Example')
        self.assertEqual(message.client_ip_hash, 'a' * 64)
        self.assertEqual(message.submission_key_hash, 'b' * 64)
        self.assertFalse(message.is_read)
        self.assertIsNotNone(message.notification_email)
        self.assertEqual(Email.objects.count(), 1)

        notification = message.notification_email
        self.assertEqual(notification.to, ['owner@example.com'])
        self.assertEqual(notification.from_email, 'no-reply@example.com')
        self.assertEqual(notification.subject, 'New contact message')
        self.assertEqual(notification.backend_alias, 'transactional')
        self.assertIn('Reply-To', notification.headers)
        self.assertEqual(notification.headers['Reply-To'], 'visitor@example.com')
        self.assertIn('Testing the contact service.', notification.message)

    def test_duplicate_submission_returns_existing_message_without_second_notification(self):
        first = self.submit()
        second = submit_contact_message(
            values=self.values(name='Changed'),
            client_ip_hash='c' * 64,
            submission_key_hash='b' * 64,
        )

        self.assertFalse(second.created)
        self.assertEqual(second.notification_status, 'duplicate')
        self.assertEqual(second.message.pk, first.message.pk)
        self.assertEqual(ContactMessage.objects.get().name, 'Alex Example')
        self.assertEqual(Email.objects.count(), 1)

    def test_failed_post_office_status_remains_linked_and_message_unread(self):
        failed_email = Email.objects.create(
            from_email='no-reply@example.com',
            to='owner@example.com',
            subject='New contact message',
            message='failed delivery',
            status=STATUS.failed,
            backend_alias='transactional',
        )
        with patch('contact.services.mail.send', return_value=failed_email):
            result = self.submit()

        self.assertEqual(result.notification_status, 'failed')
        message = ContactMessage.objects.get()
        self.assertEqual(message.notification_email_id, failed_email.pk)
        self.assertFalse(message.is_read)

    def test_notification_exception_keeps_message_and_logs_safe_identifiers(self):
        with patch('contact.services.mail.send', side_effect=RuntimeError('mail setup failed')):
            with self.assertLogs('contact.services', level='WARNING') as captured:
                result = self.submit()

        self.assertTrue(result.created)
        self.assertEqual(result.notification_status, 'not_queued')
        self.assertEqual(ContactMessage.objects.count(), 1)
        self.assertIsNone(ContactMessage.objects.get().notification_email)
        output = '\n'.join(captured.output)
        self.assertIn(str(result.message.pk), output)
        self.assertNotIn('visitor@example.com', output)
        self.assertNotIn('Testing the contact service.', output)
        self.assertNotIn('a' * 64, output)

    def test_persistence_failure_does_not_attempt_notification(self):
        with patch('contact.services.ContactMessage.objects.create', side_effect=DatabaseError('db down')):
            with patch('contact.services.mail.send') as send:
                with self.assertRaises(DatabaseError):
                    self.submit()

        send.assert_not_called()
