import logging

from django.db import DatabaseError
from django.urls import NoReverseMatch, reverse
from django.utils.translation import ngettext

from .models import ContactMessage


logger = logging.getLogger(__name__)


def get_contact_attention_items(request, *, admin_site):
    model_admin = admin_site._registry.get(ContactMessage)
    if model_admin is None:
        return ()
    if not (
        model_admin.has_view_permission(request)
        or model_admin.has_change_permission(request)
    ):
        return ()

    try:
        unread_count = model_admin.get_queryset(request).filter(is_read=False).count()
        if not unread_count:
            return ()
        url = reverse(f'{admin_site.name}:contact_contactmessage_changelist')
    except (DatabaseError, NoReverseMatch):
        logger.warning('Contact Admin attention item could not be resolved')
        return ()

    return ({
        'label': ngettext(
            '%(count)d unread contact message',
            '%(count)d unread contact messages',
            unread_count,
        ) % {'count': unread_count},
        'url': url,
    },)
