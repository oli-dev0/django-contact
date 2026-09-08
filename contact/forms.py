from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
from django.utils.translation import gettext_lazy as _

from .models import ContactMessage


class ContactForm(forms.ModelForm):
    PUBLIC_FIELD_NAMES = ('name', 'email', 'subject', 'message')

    def __init__(
        self,
        *args,
        show_verification=False,
        verification_required=False,
        verification_question='',
        **kwargs,
    ):
        self.show_verification = show_verification
        self.verification_question = verification_question
        super().__init__(*args, **kwargs)

        self.fields['name'].label = _('Name')
        self.fields['name'].widget.attrs.update({'autocomplete': 'name'})
        self.fields['name'].error_messages.update({
            'max_length': _('Name must be 120 characters or fewer.'),
        })

        self.fields['email'].label = _('Email address')
        self.fields['email'].widget = forms.EmailInput(attrs={'autocomplete': 'email'})

        self.fields['subject'].label = _('Subject')
        self.fields['subject'].error_messages.update({
            'max_length': _('Subject must be 200 characters or fewer.'),
        })

        self.fields['message'].label = _('Message')
        self.fields['message'].max_length = settings.CONTACT_MESSAGE_MAX_LENGTH
        self.fields['message'].widget = forms.Textarea(attrs={'rows': 8})
        max_length_message = _(
            'Message must be %(limit)d characters or fewer.'
        ) % {'limit': settings.CONTACT_MESSAGE_MAX_LENGTH}
        self.fields['message'].validators = [
            validator
            for validator in self.fields['message'].validators
            if not isinstance(validator, MaxLengthValidator)
        ] + [MaxLengthValidator(settings.CONTACT_MESSAGE_MAX_LENGTH, message=max_length_message)]
        self.fields['message'].error_messages.update({
            'max_length': max_length_message,
        })

        self.fields['website'] = forms.CharField(
            required=False,
            widget=forms.HiddenInput(attrs={'aria-hidden': 'true', 'tabindex': '-1'}),
        )
        self.fields['form_token'] = forms.CharField(
            required=False,
            widget=forms.HiddenInput,
        )
        if show_verification:
            self.fields['verification_answer'] = forms.IntegerField(
                label=_('Verification answer'),
                required=verification_required,
                min_value=0,
                widget=forms.NumberInput(attrs={
                    'autocomplete': 'off',
                    'inputmode': 'numeric',
                    # The initial bound challenge stays error-free, but the
                    # browser must still expose and enforce required semantics.
                    'required': True,
                }),
                error_messages={'required': _('This field is required.')},
            )
            self.fields['verification_token'] = forms.CharField(
                required=False,
                widget=forms.HiddenInput,
            )

    def full_clean(self):
        super().full_clean()
        self._apply_accessibility_attributes()

    def _apply_accessibility_attributes(self):
        for field_name, field in self.fields.items():
            attrs = field.widget.attrs
            described_by = []
            if field.help_text and field_name in self.PUBLIC_FIELD_NAMES:
                described_by.append(f'id_{field_name}_help')
            if field_name in self.errors:
                described_by.append(f'id_{field_name}_error')
                attrs['aria-invalid'] = 'true'
            else:
                attrs.pop('aria-invalid', None)
            if described_by:
                attrs['aria-describedby'] = ' '.join(described_by)
            else:
                attrs.pop('aria-describedby', None)
            attrs.pop('autofocus', None)

        if self.show_verification:
            self.fields['verification_answer'].widget.attrs['autofocus'] = True
            return

        for field_name in self.PUBLIC_FIELD_NAMES:
            if field_name in self.errors:
                self.fields[field_name].widget.attrs['autofocus'] = True
                break

    def clean_name(self):
        return self._clean_text('name')

    def clean_subject(self):
        return self._clean_text('subject')

    def clean_message(self):
        return self._clean_text('message')

    def _clean_text(self, field_name):
        value = self.cleaned_data.get(field_name, '')
        value = value.strip()
        if not value:
            raise ValidationError(_('This field is required.'))
        return value

    @property
    def public_fields(self):
        return tuple(self[name] for name in self.PUBLIC_FIELD_NAMES)

    @property
    def error_summary(self):
        summary = []
        for field_name in self.fields:
            if field_name not in self.errors or field_name in {'website', 'form_token', 'verification_token'}:
                continue
            field = self[field_name]
            summary.append({
                'id': field.id_for_label,
                'label': field.label,
                'message': str(self.errors[field_name][0]),
            })
        for error in self.non_field_errors():
            summary.append({'id': '', 'label': '', 'message': str(error)})
        return tuple(summary)

    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message']
