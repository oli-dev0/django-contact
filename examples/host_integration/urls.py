"""Reference root URL wiring for the Contact app."""

from django.urls import include, path


urlpatterns = [
    path('contact/', include('contact.urls')),
]
