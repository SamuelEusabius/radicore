from . import views
from . import views_transport
from django.urls import path
from . import views, views_transport, views_library, views_health
from . import views, views_transport, views_library, views_health, views_kitchen
from . import views, views_transport, views_library, views_health, views_kitchen, views_lab

urlpatterns = [
        # Driver PDF Reports
    path('driver/trips/pdf/',
         views_transport.driver_trip_history_pdf,
         name='driver_trip_history_pdf'),
    path('driver/fuel/pdf/',
         views_transport.driver_fuel_report_pdf,
         name='driver_fuel_report_pdf'),
    path('driver/', views.driver_dashboard, name='driver_dashboard'),
    path('librarian/', views.librarian_dashboard, name='librarian_dashboard'),
    path('lab/', views.lab_technician_dashboard, name='lab_technician_dashboard'),
    path('nurse/', views.nurse_dashboard, name='nurse_dashboard'),
    path('chef/', views.chief_chef_dashboard, name='chief_chef_dashboard'),
    
    path('reports/new/<slug:department_code>/', views.department_report_create, name='department_report_create'),
    path('reports/inbox/', views.department_reports_inbox, name='department_reports_inbox'),
        # ============================================================
    # HEALTH / NURSE MODULE
    # ============================================================
    path('nurse/', views_health.nurse_dashboard, name='nurse_dashboard'),

        # Nurse — Referral & PDFs
    path('nurse/visits/<int:visit_id>/refer/',
         views_health.refer_to_facility, name='nurse_refer_visit'),
    path('nurse/visits/<int:visit_id>/referral-pdf/',
         views_health.referral_note_pdf, name='nurse_referral_note_pdf'),
    path('nurse/students/<int:student_id>/medical-report/',
         views_health.student_medical_report_pdf, name='nurse_medical_report_pdf'),
    path('nurse/medicines/<int:medicine_id>/log-pdf/',
         views_health.medicine_log_pdf, name='nurse_medicine_log_pdf'),
    path('nurse/visits/', views_health.health_visit_list, name='health_visit_list'),
    path('nurse/visits/add/', views_health.health_visit_form, name='health_visit_add'),
    path('nurse/visits/<int:visit_id>/', views_health.health_visit_detail, name='health_visit_detail'),
        # Student Medical Report PDF
    path('nurse/students/<int:student_id>/medical-report/', views_health.student_medical_report_pdf, name='student_medical_report_pdf'),
    path('nurse/visits/<int:visit_id>/edit/', views_health.health_visit_form, name='health_visit_edit'),

    # Medicine
    path('nurse/medicines/', views_health.medicine_list, name='medicine_list'),
    path('nurse/medicines/add/', views_health.medicine_form, name='medicine_add'),
    path('nurse/medicines/<int:medicine_id>/edit/', views_health.medicine_form, name='medicine_edit'),
    path('nurse/medicines/<int:medicine_id>/stock-in/', views_health.medicine_stock_in, name='medicine_stock_in'),
    path('nurse/medicines/<int:medicine_id>/stock-out/', views_health.medicine_stock_out, name='medicine_stock_out'),
    path('nurse/medicines/logs/', views_health.medicine_logs, name='medicine_logs'),
    path('nurse/medicines/<int:medicine_id>/logs/', views_health.medicine_logs, name='medicine_logs_for'),

    # Reports
    path('nurse/reports/pdf/', views_health.health_report_pdf, name='health_report_pdf'),
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
        # ============================================================
    # LIBRARY MODULE
    # ============================================================

    # Librarian dashboard
    path('librarian/', views_library.librarian_dashboard, name='librarian_dashboard'),

    # Books catalog
    path('librarian/books/', views_library.book_list, name='book_list'),
    path('librarian/books/add/', views_library.book_form, name='book_add'),
    path('librarian/books/<int:book_id>/', views_library.book_detail, name='book_detail'),
    path('librarian/books/<int:book_id>/edit/', views_library.book_form, name='book_edit'),
    path('librarian/books/<int:book_id>/delete/', views_library.book_delete, name='book_delete'),

    # Issue / Return
    path('librarian/issue/', views_library.issue_book, name='issue_book'),
    path('librarian/issue/<int:book_id>/', views_library.issue_book, name='issue_book_for_book'),
    path('librarian/return/<int:issue_id>/', views_library.return_book, name='return_book'),
    path('librarian/issues/', views_library.book_issue_list, name='book_issue_list'),
    path('librarian/overdue/', views_library.overdue_list, name='overdue_list'),

    # Reports
    path('librarian/reports/pdf/', views_library.library_report_pdf, name='library_report_pdf'),
        # ============================================================
    # KITCHEN / CHEF MODULE
    # ============================================================
    path('chef/', views_kitchen.chef_dashboard, name='chef_dashboard'),

    # Meals
    path('chef/meals/', views_kitchen.meal_list, name='meal_list'),
    path('chef/meals/add/', views_kitchen.meal_form, name='meal_add'),
    path('chef/meals/<int:meal_id>/edit/', views_kitchen.meal_form, name='meal_edit'),

    # Meal Plans (menu)
    path('chef/menu/', views_kitchen.meal_plan_list, name='meal_plan_list'),
    path('chef/menu/add/', views_kitchen.meal_plan_form, name='meal_plan_add'),
    path('chef/menu/<int:plan_id>/edit/', views_kitchen.meal_plan_form, name='meal_plan_edit'),
    path('chef/menu/<int:plan_id>/delete/', views_kitchen.meal_plan_delete, name='meal_plan_delete'),
    path('chef/menu/<int:plan_id>/serve/', views_kitchen.meal_serving_form, name='meal_serving_form'),

    # Kitchen Stock
    path('chef/stock/', views_kitchen.kitchen_stock_list, name='kitchen_stock_list'),
    path('chef/stock/add/', views_kitchen.kitchen_stock_form, name='kitchen_stock_add'),
    path('chef/stock/<int:item_id>/edit/', views_kitchen.kitchen_stock_form, name='kitchen_stock_edit'),
    path('chef/stock/<int:item_id>/action/', views_kitchen.kitchen_stock_action, name='kitchen_stock_action'),
    path('chef/stock/logs/', views_kitchen.kitchen_logs, name='kitchen_logs'),
    path('chef/stock/<int:item_id>/logs/', views_kitchen.kitchen_logs, name='kitchen_logs_for'),

    # Reports
    path('chef/reports/pdf/', views_kitchen.kitchen_report_pdf, name='kitchen_report_pdf'),
        # ============================================================
    # LABORATORY / LAB TECHNICIAN MODULE
    # ============================================================
    path('lab/', views_lab.lab_dashboard, name='lab_dashboard'),

    # Equipment
    path('lab/equipment/', views_lab.lab_equipment_list, name='lab_equipment_list'),
    path('lab/equipment/add/', views_lab.lab_equipment_form, name='lab_equipment_add'),
    path('lab/equipment/<int:item_id>/edit/', views_lab.lab_equipment_form, name='lab_equipment_edit'),
    path('lab/equipment/<int:item_id>/delete/', views_lab.lab_equipment_delete, name='lab_equipment_delete'),

    # Incidents
    path('lab/incidents/', views_lab.lab_incident_list, name='lab_incident_list'),
    path('lab/incidents/add/', views_lab.lab_incident_form, name='lab_incident_add'),
    path('lab/incidents/<int:incident_id>/edit/', views_lab.lab_incident_form, name='lab_incident_edit'),

    # Practicals
    path('lab/practicals/', views_lab.practical_list, name='practical_list'),
    path('lab/practicals/add/', views_lab.practical_form, name='practical_add'),
    path('lab/practicals/<int:practical_id>/edit/', views_lab.practical_form, name='practical_edit'),
    path('lab/practicals/<int:practical_id>/delete/', views_lab.practical_delete, name='practical_delete'),

    # Reports
    path('lab/reports/pdf/', views_lab.lab_report_pdf, name='lab_report_pdf'),
]
