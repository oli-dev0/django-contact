from django.contrib import messages
from django.contrib.messages import get_messages
from django.db import DatabaseError
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from .abuse import (
    AbuseOutcome,
    create_form_token,
    create_verification_challenge,
    get_honeypot_outcome,
    get_signed_form_nonce,
    get_throttle_outcome,
    hash_submission_nonce,
    inspect_form_token,
    normalize_email_for_throttle,
    validate_verification,
    get_client_ip_hash,
)
from .forms import ContactForm
from .services import get_existing_contact_submission, submit_contact_message


def contact_page(request):
    if request.method != 'POST':
        form = ContactForm(initial={'form_token': create_form_token()})
        success_messages = [message for message in get_messages(request) if message.level == messages.SUCCESS]
        return _render_contact(
            request,
            form,
            submission_state='success' if success_messages else None,
            submission_message=success_messages[0] if success_messages else None,
        )

    form = ContactForm(request.POST)
    if not form.is_valid():
        return _render_contact(request, form)

    if get_honeypot_outcome(form.cleaned_data.get('website', '')) == AbuseOutcome.HONEYPOT_REJECTED:
        return _render_contact(
            request,
            _build_rejection_retry_form(request),
            submission_state='rejected',
            submission_message=_(
                'We couldn’t accept this submission right now. '
                'Please wait a little while and try again.'
            ),
        )

    try:
        client_ip_hash = get_client_ip_hash(request)
        form_token_state = inspect_form_token(form.cleaned_data.get('form_token'))
        submission_nonce = form_token_state.nonce

        if submission_nonce:
            submission_key_hash = hash_submission_nonce(submission_nonce)
            if get_existing_contact_submission(submission_key_hash) is not None:
                return _accept_and_redirect(request)

        throttle_outcome = get_throttle_outcome(
            client_ip_hash=client_ip_hash,
            normalized_email=normalize_email_for_throttle(form.cleaned_data['email']),
        )
        if throttle_outcome == AbuseOutcome.RATE_LIMITED:
            return _render_contact(
                request,
                form,
                status=429,
                submission_state='rejected',
                submission_message=_(
                    'We couldn’t accept this submission right now. '
                    'Please wait a little while and try again.'
                ),
            )

        challenge_submitted = 'verification_token' in request.POST or 'verification_answer' in request.POST
        if form_token_state.outcome == AbuseOutcome.VERIFICATION_REQUIRED or challenge_submitted:
            if not challenge_submitted:
                return _render_contact(
                    request,
                    _build_challenge_form(request, nonce=submission_nonce),
                    submission_state='challenge',
                )

            challenged_form = ContactForm(
                request.POST,
                show_verification=True,
                verification_required=True,
            )
            if not challenged_form.is_valid() or not validate_verification(
                token=challenged_form.cleaned_data.get('verification_token'),
                answer=challenged_form.cleaned_data.get('verification_answer'),
                submission_nonce=submission_nonce,
            ):
                return _render_contact(
                    request,
                    _build_challenge_form(
                        request,
                        nonce=submission_nonce,
                        failure=True,
                    ),
                    submission_state='challenge',
                )
            form = challenged_form

        if not submission_nonce:
            return _render_contact(
                request,
                _build_challenge_form(request, failure=True),
                submission_state='challenge',
            )

        submit_contact_message(
            values=form.cleaned_data,
            client_ip_hash=client_ip_hash,
            submission_key_hash=hash_submission_nonce(submission_nonce),
        )
    except DatabaseError:
        return _render_contact(
            request,
            form,
            status=503,
            submission_state='failure',
            submission_message=_('We couldn’t send your message right now. Please try again.'),
        )

    return _accept_and_redirect(request)


def _build_rejection_retry_form(request):
    data = request.POST.copy()
    data['website'] = ''
    data['form_token'] = create_form_token()
    return ContactForm(data)


def _build_challenge_form(request, *, nonce=None, failure=False):
    form_token = create_form_token(nonce=nonce) if nonce else create_form_token()
    nonce = nonce or get_signed_form_nonce(form_token)
    challenge = create_verification_challenge(nonce)
    data = request.POST.copy()
    data['form_token'] = form_token
    data['verification_token'] = challenge.token
    data['verification_answer'] = ''
    form = ContactForm(
        data,
        show_verification=True,
        verification_question=challenge.question,
    )
    if failure:
        form.add_error(
            'verification_answer',
            _('That verification was not completed. Please try again.'),
        )
    return form


def _accept_and_redirect(request):
    messages.success(request, _('Your message has been sent'))
    response = redirect('contact:page')
    return _private_response(response)


def _render_contact(request, form, *, status=200, submission_state=None, submission_message=None):
    error_summary = form.error_summary
    response = render(
        request,
        'contact/page.html',
        {
            'form': form,
            'public_fields': form.public_fields,
            'error_summary': error_summary,
            'show_verification': form.show_verification,
            'verification_question': form.verification_question,
            'verification_answer': form['verification_answer'] if form.show_verification else None,
            'verification_token': form['verification_token'] if form.show_verification else None,
            'submission_state': submission_state,
            'submission_message': submission_message,
            'hide_global_messages': True,
        },
        status=status,
    )
    return _private_response(response)


def _private_response(response):
    response['Cache-Control'] = 'no-store'
    response['Referrer-Policy'] = 'same-origin'
    return response
