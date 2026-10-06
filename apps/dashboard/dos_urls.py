from django.urls import path
from .views import dos_views

urlpatterns = [
    path('', dos_views.dos_dashboard, name='dos_dashboard'),
    path('classes/', dos_views.dos_classes, name='dos_classes'),
    path('classes/<int:class_id>/', dos_views.dos_class_detail, name='dos_class_detail'),
    path('combine/', dos_views.dos_combine, name='dos_combine'),
    path('analytics/', dos_views.dos_analytics, name='dos_analytics'),
    path('analytics/subject-matrix/', dos_views.dos_subject_matrix, name='dos_subject_matrix'),
    path('analytics/comparison/', dos_views.dos_comparison, name='dos_comparison'),
    path('lessons/', dos_views.dos_lessons, name='dos_lessons'),
    path('teachers/', dos_views.dos_teachers, name='dos_teachers'),
    path('reports/pdf/', dos_views.dos_report_pdf, name='dos_report_pdf'),
    path('combine/pdf/', dos_views.dos_combine_pdf, name='dos_combine_pdf'),
]