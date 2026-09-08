from django.test import TestCase, override_settings

from contact.forms import ContactForm


def valid_form_data(**overrides):
    data = {
        'name': 'Alex Example',
        'email': 'visitor@example.com',
        'subject': 'Hello',
        'message': 'Testing the contact form.',
    }
    data.update(overrides)
    return data


class ContactFormTests(TestCase):
    def test_contact_form_keeps_exactly_four_visible_product_fields(self):
        form = ContactForm()

        self.assertEqual(
            [field.name for field in form.visible_fields()],
            ['name', 'email', 'subject', 'message'],
        )
        self.assertEqual(
            [name for name, field in form.fields.items() if field.widget.is_hidden],
            ['website', 'form_token'],
        )

    def test_valid_input_strips_surrounding_text_whitespace(self):
        form = ContactForm(data=valid_form_data(
            name='  Alex Example  ',
            email=' visitor@example.com ',
            subject='  Hello  ',
            message='  Testing the contact form.  ',
        ))

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['name'], 'Alex Example')
        self.assertEqual(form.cleaned_data['email'], 'visitor@example.com')
        self.assertEqual(form.cleaned_data['subject'], 'Hello')
        self.assertEqual(form.cleaned_data['message'], 'Testing the contact form.')

    def test_contact_form_requires_valid_email(self):
        form = ContactForm(data=valid_form_data(email='not-an-email'))

        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertEqual(str(form.errors['email'][0]), 'Enter a valid email address.')

    def test_whitespace_only_text_is_required(self):
        form = ContactForm(data=valid_form_data(name='   ', message='\t'))

        self.assertFalse(form.is_valid())
        self.assertEqual(str(form.errors['name'][0]), 'This field is required.')
        self.assertEqual(str(form.errors['message'][0]), 'This field is required.')

    @override_settings(CONTACT_MESSAGE_MAX_LENGTH=5000)
    def test_message_length_is_bounded_at_the_form_boundary(self):
        form = ContactForm(data=valid_form_data(message='x' * 5001))

        self.assertFalse(form.is_valid())
        self.assertEqual(str(form.errors['message'][0]), 'Message must be 5000 characters or fewer.')

    def test_accessibility_metadata_associates_help_and_errors(self):
        form = ContactForm(data=valid_form_data(email='bad'))

        self.assertFalse(form.is_valid())
        email = str(form['email'])
        self.assertIn('type="email"', email)
        self.assertIn('autocomplete="email"', email)
        self.assertIn('aria-describedby="id_email_error"', email)
        self.assertIn('aria-invalid="true"', email)
        self.assertIn('autofocus', email)

    def test_verification_fields_are_conditional_and_preserve_values(self):
        form = ContactForm(
            data=valid_form_data(),
            show_verification=True,
            verification_question='2 + 2 = ?',
        )

        self.assertTrue(form.is_valid())
        self.assertIn('verification_answer', form.fields)
        self.assertIn('verification_token', form.fields)
        self.assertEqual(form.cleaned_data['message'], 'Testing the contact form.')
        self.assertEqual(form['verification_answer'].field.widget.input_type, 'number')
        self.assertIn('required', str(form['verification_answer']))
