from django.db import IntegrityError
from django.test import TestCase

from post_office.models import Email

from contact.models import ContactMessage


class ContactMessageModelTests(TestCase):
    def values(self, **overrides):
        values = {
            'name': 'Alex Example',
            'email': 'visitor@example.com',
            'subject': 'Hello',
            'message': 'A message.',
        }
        values.update(overrides)
        return values

    def test_new_messages_are_unread_and_newest_first(self):
        first = ContactMessage.objects.create(**self.values(subject='First'))
        second = ContactMessage.objects.create(**self.values(subject='Second'))

        self.assertFalse(first.is_read)
        self.assertEqual(list(ContactMessage.objects.all()), [second, first])

    def test_duplicate_submission_hashes_are_rejected_but_legacy_nulls_are_valid(self):
        ContactMessage.objects.create(**self.values(submission_key_hash='a' * 64))
        ContactMessage.objects.create(**self.values(email='one@example.com'))
        ContactMessage.objects.create(**self.values(email='two@example.com'))

        with self.assertRaises(IntegrityError):
            ContactMessage.objects.create(**self.values(submission_key_hash='a' * 64))

    def test_post_office_deletion_unlinks_without_deleting_contact_message(self):
        email = Email.objects.create(
            from_email='no-reply@example.com',
            to='owner@example.com',
            subject='New contact message',
            message='A message.',
        )
        message = ContactMessage.objects.create(**self.values(notification_email=email))

        email.delete()
        message.refresh_from_db()

        self.assertIsNone(message.notification_email_id)
        self.assertTrue(ContactMessage.objects.filter(pk=message.pk).exists())

    def test_model_metadata_contains_unread_and_ip_throttle_indexes(self):
        index_names = {index.name for index in ContactMessage._meta.indexes}

        self.assertIn('contact_unread_created', index_names)
        self.assertIn('contact_ip_created', index_names)
