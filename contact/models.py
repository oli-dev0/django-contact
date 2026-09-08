from django.db import models


class ContactMessage(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    submission_key_hash = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)
    client_ip_hash = models.CharField(max_length=64, blank=True, editable=False)
    notification_email = models.OneToOneField(
        'post_office.Email',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name='+',
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_read', 'created_at'], name='contact_unread_created'),
            models.Index(fields=['client_ip_hash', 'created_at'], name='contact_ip_created'),
        ]

    def __str__(self):
        return f'{self.name} <{self.email}>'
