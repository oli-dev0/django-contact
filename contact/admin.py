from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from post_office.models import STATUS

from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'created_at', 'is_read', 'notification_status')
    list_filter = ('is_read',)
    search_fields = ('name', 'email', 'subject', 'message')
    ordering = ('-created_at', '-pk')
    list_select_related = ('notification_email',)
    fields = ('name', 'email', 'subject', 'message', 'created_at', 'is_read', 'notification_status')
    readonly_fields = ('name', 'email', 'subject', 'message', 'created_at', 'notification_status')

    def has_add_permission(self, request):
        return False

    @admin.display(description=_('Notification'))
    def notification_status(self, obj):
        if obj.notification_email is None:
            return _('Not queued')
        if obj.notification_email.status == STATUS.sent:
            return _('Sent')
        if obj.notification_email.status == STATUS.failed:
            return _('Failed')
        return _('Queued')
