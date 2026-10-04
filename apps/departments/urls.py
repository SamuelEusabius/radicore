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
        # Trip manifest + PDF
    path('driver/trips/<int:trip_id>/manifest/', views_transport.trip_manifest, name='trip_manifest'),
    path('driver/trips/<int:trip_id>/manifest/pdf/', views_transport.trip_manifest_pdf, name='trip_manifest_pdf'),
        # Report PDFs + Print
    path('reports/<int:report_id>/pdf/', views.report_pdf, name='report_pdf'),
    path('reports/bulk-pdf/', views.reports_bulk_pdf, name='reports_bulk_pdf'),
    path('reports/print/', views.reports_print, name='reports_print'),
    path('reports/<int:report_id>/review/', views.department_report_review, name='department_report_review'),

    # My students
    path('driver/students/', views_transport.my_students, name='my_students'),
    path('driver/students/pdf/', views_transport.my_students_pdf, name='my_students_pdf'),
]
