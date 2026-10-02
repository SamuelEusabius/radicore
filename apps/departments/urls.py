from django.urls import path
from . import views

urlpatterns = [
    path('driver/', views.driver_dashboard, name='driver_dashboard'),
    path('librarian/', views.librarian_dashboard, name='librarian_dashboard'),
    path('lab/', views.lab_technician_dashboard, name='lab_technician_dashboard'),
    path('nurse/', views.nurse_dashboard, name='nurse_dashboard'),
    path('chef/', views.chief_chef_dashboard, name='chief_chef_dashboard'),
    
    path('reports/new/<slug:department_code>/', views.department_report_create, name='department_report_create'),
    path('reports/inbox/', views.department_reports_inbox, name='department_reports_inbox'),
]