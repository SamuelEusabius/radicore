from django.urls import path
from . import unallocated_views

urlpatterns = [
    path('', unallocated_views.unallocated_queue, name='unallocated_queue'),
    path('<int:payment_id>/', unallocated_views.unallocated_detail, name='unallocated_detail'),
    path('<int:payment_id>/reassign/', unallocated_views.unallocated_reassign, name='unallocated_reassign'),
    path('<int:payment_id>/split/', unallocated_views.unallocated_split, name='unallocated_split'),
    path('<int:payment_id>/reject/', unallocated_views.unallocated_reject, name='unallocated_reject'),
    path('reports/', unallocated_views.unallocated_reports, name='unallocated_reports'),
]