from django.urls import path
from . import views
from . import views_transport

urlpatterns = [
    path('driver/', views.driver_dashboard, name='driver_dashboard'),
    path('librarian/', views.librarian_dashboard, name='librarian_dashboard'),
    path('lab/', views.lab_technician_dashboard, name='lab_technician_dashboard'),
    path('nurse/', views.nurse_dashboard, name='nurse_dashboard'),
    path('chef/', views.chief_chef_dashboard, name='chief_chef_dashboard'),
    
    path('reports/new/<slug:department_code>/', views.department_report_create, name='department_report_create'),
    path('reports/inbox/', views.department_reports_inbox, name='department_reports_inbox'),
     # ---------- DRIVER — TRANSPORT MODULE ----------
    path('driver/', views_transport.driver_dashboard, name='driver_dashboard'),
    path('driver/trips/<int:trip_id>/', views_transport.trip_detail, name='trip_detail'),
    path('driver/trips/<int:trip_id>/start/', views_transport.trip_start, name='trip_start'),
    path('driver/trips/<int:trip_id>/complete/', views_transport.trip_complete, name='trip_complete'),
    path('driver/trips/<int:trip_id>/student/<int:student_id>/mark/', views_transport.trip_student_mark, name='trip_student_mark'),
    path('driver/trips/<int:trip_id>/checklist/', views_transport.checklist_update, name='checklist_update'),
    path('driver/fuel/', views_transport.fuel_log_list, name='fuel_log_list'),
    path('driver/fuel/add/', views_transport.fuel_log_add, name='fuel_log_add'),
    path('driver/trips/history/', views_transport.trip_history, name='trip_history'),
]
