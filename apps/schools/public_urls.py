from django.urls import path
from . import public_views

urlpatterns = [
    path('resources/', public_views.resource_centre, name='resource_centre'),
    path('', public_views.landing, name='landing'),
    path('signup/', public_views.school_signup, name='school_signup'),
    path('contact/', public_views.contact, name='contact'),
    path('help/', public_views.help_page, name='help_page'),
    path('about/', public_views.about, name='about'),
    path('privacy/', public_views.privacy, name='privacy'),
    path('terms/', public_views.terms, name='terms'),
]