from django.urls import path

from . import views

urlpatterns = [
    path('locations/constituencies/', views.api_constituencies, name='api_constituencies'),
    path('locations/wards/', views.api_wards, name='api_wards'),
]