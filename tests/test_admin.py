from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import DatabaseError
from django.test import RequestFactory, TestCase
from django.urls import NoReverseMatch

from contact.models import ContactMessage
from contact.selectors import get_contact_attention_items


class ContactAdminTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.model_admin = admin.site._registry[ContactMessage]

    def make_user(self, username, *codenames):
        user = get_user_model().objects.create_user(username=username, password='password')
        permissions = Permission.objects.filter(
            content_type__app_label='contact',
            codename__in=codenames,
        )
        user.user_permissions.add(*permissions)
        return user

    def make_request(self, user):
        request = self.factory.get('/admin/')
        request.user = user
        return request

    def make_message(self, *, is_read=False, subject='Hello'):
        return ContactMessage.objects.create(
            name='Alex Example',
            email='visitor@example.com',
            subject=subject,
            message='A message.',
            is_read=is_read,
        )

    def test_contact_admin_keeps_message_content_readonly_but_allows_is_read(self):
        readonly = self.model_admin.get_readonly_fields(self.make_request(self.make_user('admin')), None)

        self.assertEqual(
            readonly,
            ('name', 'email', 'subject', 'message', 'created_at', 'notification_status'),
        )
        self.assertIn('is_read', self.model_admin.fields)
        self.assertNotIn('client_ip_hash', self.model_admin.fields)
        self.assertNotIn('submission_key_hash', self.model_admin.fields)
        self.assertIn('message', self.model_admin.search_fields)
        self.assertEqual(self.model_admin.ordering, ('-created_at', '-pk'))

    def test_permission_aware_selector_returns_singular_and_plural_items(self):
        user = self.make_user('viewer', 'view_contactmessage')
        self.make_message()
        request = self.make_request(user)

        self.assertEqual(
            get_contact_attention_items(request, admin_site=admin.site),
            ({
                'label': '1 unread contact message',
                'url': '/admin/contact/contactmessage/',
            },),
        )
        self.make_message(subject='Second')
        self.assertEqual(
            get_contact_attention_items(request, admin_site=admin.site)[0]['label'],
            '2 unread contact messages',
        )

    def test_user_without_contact_permission_receives_no_item(self):
        self.make_message()

        self.assertEqual(
            get_contact_attention_items(
                self.make_request(self.make_user('without-permission')),
                admin_site=admin.site,
            ),
            (),
        )

    def test_selector_respects_permission_scoped_queryset(self):
        user = self.make_user('scoped-viewer', 'view_contactmessage')
        self.make_message(subject='Visible')
        self.make_message(subject='Hidden')
        request = self.make_request(user)
        with patch.object(
            self.model_admin,
            'get_queryset',
            return_value=ContactMessage.objects.filter(subject='Visible'),
        ):
            items = get_contact_attention_items(request, admin_site=admin.site)

        self.assertEqual(items[0]['label'], '1 unread contact message')

    def test_selector_fails_closed_for_unregistered_database_or_reverse_errors(self):
        user = self.make_user('error-viewer', 'view_contactmessage')
        request = self.make_request(user)
        self.make_message()

        with patch.object(self.model_admin, 'get_queryset', side_effect=DatabaseError):
            self.assertEqual(get_contact_attention_items(request, admin_site=admin.site), ())
        with patch('contact.selectors.reverse', side_effect=NoReverseMatch):
            self.assertEqual(get_contact_attention_items(request, admin_site=admin.site), ())

        class UnregisteredAdminSite:
            _registry = {}

        self.assertEqual(
            get_contact_attention_items(request, admin_site=UnregisteredAdminSite()),
            (),
        )

    def test_admin_index_context_combines_contact_attention_with_newsletter_items(self):
        user = self.make_user('index-viewer', 'view_contactmessage')
        self.make_message()
        response = admin.site.index(self.make_request(user))

        self.assertEqual(
            response.context_data['contact_attention'],
            ({
                'label': '1 unread contact message',
                'url': '/admin/contact/contactmessage/',
            },),
        )
        self.assertEqual(response.context_data['newsletter_attention'], ())
