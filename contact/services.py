import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from post_office import mail
from post_office.models import STATUS

from .models import ContactMessage


logger = logging.getLogger(__name__)

CONTACT_NOTIFICATION_SUBJECT = 'New contact message'


@dataclass(frozen=True)
class ContactSubmissionResult:
    message: ContactMessage
    created: bool
    notification_status: str


def submit_contact_message(*, values, client_ip_hash, submission_key_hash):
    message_values = {
        'name': values['name'],
        'email': values['email'],
        'subject': values['subject'],
        'message': values['message'],
        'client_ip_hash': client_ip_hash,
        'submission_key_hash': submission_key_hash,
        'is_read': False,
    }

    with transaction.atomic():
        try:
            with transaction.atomic():
                message = ContactMessage.objects.create(**message_values)
        except IntegrityError:
            # The unique signed nonce is the final duplicate-write guard when
            # two workers accept the same rendered form concurrently.
            message = ContactMessage.objects.filter(
                submission_key_hash=submission_key_hash,
            ).first()
            if message is None:
                raise
            created = False
        else:
            created = True

    if not created:
        return ContactSubmissionResult(
            message=message,
            created=False,
            notification_status='duplicate',
        )

    # Keep the accepted message committed before synchronous SMTP/Post Office I/O
    # so a delivery problem never rolls back the owner's unread contact record.
    notification_status = _send_owner_notification(message)
    return ContactSubmissionResult(
        message=message,
        created=True,
        notification_status=notification_status,
    )


def get_existing_contact_submission(submission_key_hash):
    return ContactMessage.objects.filter(submission_key_hash=submission_key_hash).first()


def _send_owner_notification(message):
    try:
        validate_email(message.email)
        owner_email = settings.CONTACT_OWNER_EMAIL
        sender_email = settings.CONTACT_SENDER_EMAIL
        body = _render_notification_body(message)
        email = mail.send(
            sender=sender_email,
            recipients=[owner_email],
            subject=CONTACT_NOTIFICATION_SUBJECT,
            message=body,
            headers={'Reply-To': message.email},
            backend='transactional',
            priority='now',
        )
        message.notification_email = email
        message.save(update_fields=['notification_email'])
    except Exception as error:
        # Queue/configuration errors are deliberately contained at the notification
        # boundary. The accepted message remains available for Admin review.
        logger.warning(
            'Contact owner notification was not queued for message %s (%s)',
            message.pk,
            type(error).__name__,
        )
        return 'not_queued'

    if email.status == STATUS.failed:
        logger.warning('Contact owner notification failed for message %s', message.pk)
        return 'failed'
    if email.status == STATUS.sent:
        return 'sent'
    return 'queued'


def _render_notification_body(message):
    return '\n'.join((
        f'Name: {message.name}',
        f'Email: {message.email}',
        f'Subject: {message.subject}',
        '',
        message.message,
    ))
