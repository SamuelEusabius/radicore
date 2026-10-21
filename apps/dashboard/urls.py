from django.urls import path, include
from django.views.generic import RedirectView
from apps.dashboard.views.students import student_bio_page as student_bio_view
from django.shortcuts import render, redirect, get_object_or_404

from . import views
from apps.finance import store_views

urlpatterns = [ 
                   # Global search
    path('search/', views.global_search, name='global_search'),
    path('', include('apps.security.urls')),
    path('', include('apps.secretary.urls')), 
    path('students/<int:student_id>/bio/',
         views.students.student_bio_page, name='student_bio_page'),     
    path('subscribe/', RedirectView.as_view(
     url='/dashboard/subscriptions/', permanent=False
    )),
    
           # Deputy Principal — Administration
    path('dpa-admin/', views.dpa_admin_dashboard, name='dpa_admin_dashboard'),
    path('dpa-admin/discipline/', views.dpa_discipline_list, name='dpa_discipline_list'),
    path('dpa-admin/discipline/new/', views.dpa_discipline_create, name='dpa_discipline_create'),
    path('dpa-admin/discipline/<int:record_id>/', views.dpa_discipline_detail, name='dpa_discipline_detail'),
    path('dpa-admin/discipline/<int:record_id>/edit/', views.dpa_discipline_edit, name='dpa_discipline_edit'),
    path('dpa-admin/discipline/<int:record_id>/escalate/', views.dpa_discipline_escalate, name='dpa_discipline_escalate'),
    path('dpa-admin/discipline/<int:record_id>/leave-out/new/', views.dpa_leave_out_create, name='dpa_leave_out_create'),
    path('dpa-admin/leave-outs/', views.dpa_leave_out_list, name='dpa_leave_out_list'),
    path('dpa-admin/leave-outs/<int:leave_out_id>/', views.dpa_leave_out_detail, name='dpa_leave_out_detail'),
    path('dpa-admin/leave-outs/<int:leave_out_id>/approve/', views.dpa_leave_out_approve, name='dpa_leave_out_approve'),
    path('dpa-admin/leave-outs/<int:leave_out_id>/notify/', views.dpa_leave_out_toggle_notify, name='dpa_leave_out_toggle_notify'),
    path('dpa-admin/leave/<int:leave_id>/approve/', views.dpa_approve_leave, name='dpa_approve_leave'),
    path('dpa-admin/leave/<int:leave_id>/reject/', views.dpa_reject_leave, name='dpa_reject_leave'),
    path('dpa-admin/reports/discipline/',
         views.dpa_discipline_report, name='dpa_discipline_report'),
    path('dpa-admin/reports/discipline/pdf/',
         views.dpa_discipline_report_pdf, name='dpa_discipline_report_pdf'),
    
        # Professionalism
    path('dpa-admin/professionalism/', views.dpa_professionalism_list, name='dpa_professionalism_list'),
    path('dpa-admin/professionalism/new/', views.dpa_professionalism_create, name='dpa_professionalism_create'),
    path('dpa-admin/professionalism/new/<int:user_id>/', views.dpa_professionalism_create, name='dpa_professionalism_create_for'),
    path('dpa-admin/professionalism/<int:note_id>/', views.dpa_professionalism_detail, name='dpa_professionalism_detail'),
    path('dpa-admin/professionalism/<int:note_id>/delete/', views.dpa_professionalism_delete, name='dpa_professionalism_delete'),
    path('dpa-admin/professionalism/<int:note_id>/pdf/', views.dpa_professionalism_pdf, name='dpa_professionalism_pdf'),
        # Staff management
    path('dpa-admin/staff/attendance/', views.dpa_staff_attendance, name='dpa_staff_attendance'),
    path('dpa-admin/staff/attendance/history/', views.dpa_staff_attendance_history, name='dpa_staff_attendance_history'),
    path('dpa-admin/staff/duty-roster/', views.dpa_duty_roster, name='dpa_duty_roster'),
    path('dpa-admin/staff/duty-roster/new/', views.dpa_duty_create, name='dpa_duty_create'),
    path('dpa-admin/staff/duty-roster/<int:duty_id>/toggle/', views.dpa_duty_toggle_complete, name='dpa_duty_toggle_complete'),
    path('dpa-admin/staff/duty-roster/<int:duty_id>/delete/', views.dpa_duty_delete, name='dpa_duty_delete'),
    path('dpa-admin/staff/leave/', views.dpa_leave_list, name='dpa_leave_list'),
    path('dpa-admin/staff/leave/<int:leave_id>/', views.dpa_leave_detail, name='dpa_leave_detail'),
    path('dpa-admin/staff/leave/<int:leave_id>/principal-approve/', views.dpa_leave_principal_approve, name='dpa_leave_principal_approve'),
    path('dpa-admin/staff/movement/', views.dpa_staff_movement, name='dpa_staff_movement'),
    path('dpa-admin/staff/movement/new/', views.dpa_staff_movement_create, name='dpa_staff_movement_create'),
    path('dpa-admin/staff/', views.dpa_staff_directory, name='dpa_staff_directory'),
    path('dpa-admin/staff/<int:user_id>/', views.dpa_staff_detail, name='dpa_staff_detail'),
    path('dpa-admin/staff/duty-roster/pdf/', views.dpa_duty_roster_pdf, name='dpa_duty_roster_pdf'),
    path('dpa-admin/leave-outs/<int:leave_out_id>/pdf/',views.dpa_leave_out_pdf, name='dpa_leave_out_pdf'),
    
        # Student administration
    path('dpa-admin/students/attendance/', views.dpa_student_attendance, name='dpa_student_attendance'),
    path('dpa-admin/students/attendance/<path:class_level>/', views.dpa_student_attendance_class, name='dpa_student_attendance_class'),
    path('dpa-admin/students/movement/', views.dpa_student_movement, name='dpa_student_movement'),
    path('dpa-admin/students/movement/new/', views.dpa_student_movement_create, name='dpa_student_movement_create'),
    path('dpa-admin/students/movement/<int:movement_id>/return/', views.dpa_student_movement_return, name='dpa_student_movement_return'),
    path('dpa-admin/students/cases/', views.dpa_admin_cases, name='dpa_admin_cases'),
    path('dpa-admin/students/cases/new/', views.dpa_admin_case_create, name='dpa_admin_case_create'),
    path('dpa-admin/students/cases/<int:case_id>/', views.dpa_admin_case_detail, name='dpa_admin_case_detail'),
    path('dpa-admin/students/cases/<int:case_id>/update/', views.dpa_admin_case_update, name='dpa_admin_case_update'),
    
    path('placeholder/', views.dashboard_placeholder, name='dashboard_placeholder'),
    path('', views.redirect_dashboard, name='dashboard_home'),
    path('timetable/pdf/', views.timetable_pdf, name='timetable_pdf'),
    
        # Student Clearance & Leaving Certificate
    path('students/<int:student_id>/clear/', views.clear_student, name='clear_student'),
    path('students/<int:student_id>/leaving-certificate/', views.leaving_certificate, name='leaving_certificate'),
    path('students/<int:student_id>/leaving-certificate/pdf/', views.leaving_certificate_pdf, name='leaving_certificate_pdf'),
    path('students/<int:student_id>/biodata/pdf/', views.student_biodata_pdf, name='student_biodata_pdf'),

    # Dashboards
    path('super-admin/', views.super_admin_dash, name='dash_super_admin'),
    path('school-admin/', views.school_admin_dash, name='dash_school_admin'),
    path('teacher/', views.teacher_dash, name='dash_teacher'),
    path('parent/', views.parent_dash, name='dash_parent'),
    path('accountant/', views.accountant_dash, name='dash_accountant'),
    path('student/', views.student_dash, name='dash_student'),
    path('class-teacher/', views.class_teacher_dashboard, name='class_teacher_dashboard'),

        # People Management
        
    path('students/', views.students_list, name='students_list'),
    path('students/add/', views.add_student, name='add_student'),
    path('students/<int:student_id>/delete/', views.delete_student, name='delete_student'),
    path('teachers/', views.teachers_list, name='teachers_list'),
    path('teachers/add/', views.add_teacher, name='add_teacher'),
    path('teachers/<int:teacher_id>/delete/', views.delete_teacher, name='delete_teacher'),
    path('parents/', views.parents_list, name='parents_list'),
    path('parents/add/', views.add_parent, name='add_parent'),
    path('parents/<int:parent_id>/delete/', views.delete_parent, name='delete_parent'),
    path('parents/<int:parent_id>/link-children/', views.link_parent_children, name='link_parent_children'),
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/add/', views.add_staff, name='add_staff'),
    path('staff/<int:staff_id>/delete/', views.delete_staff, name='delete_staff'),
    
        # Parent portal sub-pages
    path('parent/children/', views.parent_children, name='parent_children'),
    path('parent/child/<int:student_id>/', views.parent_child_detail, name='parent_child_detail'),
    
    # Users
    path('users/', views.manage_users, name='manage_users'),
    path('users/create/', views.create_user, name='create_user'),
    path('users/<int:user_id>/change-password/', views.user_change_password, name='user_change_password'),

    # Academics
    path('academics/classes/', views.manage_classes, name='manage_classes'),
    path('academics/subjects/', views.manage_subjects, name='manage_subjects'),

    # Timetable
    path('timetable/', views.timetable_view, name='timetable_view'),
    path('timetable/add/', views.timetable_add, name='timetable_add'),
    path('timetable/<int:entry_id>/delete/', views.timetable_delete, name='timetable_delete'),
    path('teacher/timetable/', views.teacher_timetable, name='teacher_timetable'),

    # Teacher tools
    path('teacher/attendance/', views.teacher_attendance, name='teacher_attendance'),
    path('grades/exams/', views.manage_exams, name='manage_exams'),
    path('grades/enter/', views.enter_grades, name='enter_grades'),
    
        # ========== CLASS TEACHER ==========
            path('teacher/my-class/grades/',
         views.class_teacher_grades,
         name='class_teacher_grades'),

    path('teacher/my-class/grades/new-exam/',
         views.class_teacher_new_exam,
         name='class_teacher_new_exam'),

    path('teacher/my-class/rankings/',
         views.class_teacher_rankings,
         name='class_teacher_rankings'),
        path('admin/alerts/',
         views.admin_alerts_list,
         name='admin_alerts_list'),

    path('admin/alerts/<int:alert_id>/resolve/',
         views.admin_alert_resolve,
         name='admin_alert_resolve'),
     path('teacher/my-class/attendance/pdf/',
         views.class_teacher_attendance_pdf,
         name='class_teacher_attendance_pdf'),
         path('teacher/my-class/results-sheet/pdf/',
         views.class_teacher_results_sheet_pdf,
         name='class_teacher_results_sheet_pdf'),

    path('teacher/my-class/report-cards/zip/',
         views.class_teacher_all_report_cards_zip,
         name='class_teacher_all_report_cards_zip'),

    path('teacher/my-class/report-cards/merged/',
         views.class_teacher_all_report_cards_merged,
         name='class_teacher_all_report_cards_merged'),
    
     path('parent/child/<int:student_id>/statement/pdf/',
         views.parent_child_statement_pdf,
         name='parent_child_statement_pdf'),
     
     path('accountant/generate-invoices/', views.generate_invoices, name='generate_invoices'),

    path('teacher/my-class/rankings/download/',
         views.class_teacher_rankings_download,
         name='class_teacher_rankings_download'),
        path('accountant/student/<int:student_id>/invoice/',
         views.invoice_student_quick,
         name='invoice_student_quick'),
     path('academics/subjects/<int:subject_id>/delete/',
         views.subject_delete,
         name='subject_delete'),
     path('subscriptions/manage/',
         views.subscription_admin_picker,
         name='subscription_admin_picker'),
     path('subscriptions/',
         views.subscription_plans,
         name='subscription_plans'),
    path('subscriptions/confirm/',
         views.subscription_confirm,
         name='subscription_confirm'),

    path('subscriptions/payment/',
         views.subscription_payment,
         name='subscription_payment'),
     path('accountant/transactions/report.pdf/',
         views.financial_report_pdf,
         name='financial_report_pdf'),
     path('students/<int:student_id>/',
         views.student_detail,
         name='student_detail'),
         path('users/<int:user_id>/deactivate/',
         views.user_deactivate,
         name='user_deactivate'),

    path('users/<int:user_id>/delete/',
         views.user_delete,
         name='user_delete'),

    path('users/<int:user_id>/change-role/',
         views.user_change_role,
         name='user_change_role'),
    path('teacher/my-class/attendance/',
         views.class_teacher_attendance,
         name='class_teacher_attendance'),
    
        path('admin/attendance/',
         views.admin_attendance_overview,
         name='admin_attendance_overview'),
        
     path('admin/attendance/class/<int:class_id>/',
          views.admin_class_attendance,
          name='admin_class_attendance'),
        

    path('admin/attendance/export/',
         views.admin_attendance_export,
         name='admin_attendance_export'),

    path('admin/student/<int:student_id>/',
         views.admin_student_detail,
         name='admin_student_detail'),
    
     path('admin/attendance/',
         views.admin_attendance_overview,
         name='admin_attendance_overview'),

    path('teacher/my-class/attendance/sheet/',
         views.class_teacher_attendance_sheet,
         name='class_teacher_attendance_sheet'),

    path('teacher/my-class/grades/',
         views.class_teacher_grades,
         name='class_teacher_grades'),

    path('teacher/my-class/parents/',
         views.class_teacher_parents,
         name='class_teacher_parents'),

       path('teacher/my-class/student/<int:student_id>/',
         views.class_teacher_view_student,
         name='class_teacher_view_student'),
        path('teacher/my-class/parents/<int:parent_id>/',
         views.class_teacher_view_parent,
         name='class_teacher_view_parent'),

    path('teacher/my-class/parents/download/',
         views.class_teacher_parents_download,
         name='class_teacher_parents_download'),

    # Class Results
    path('class-results/', views.class_results, name='class_results'),
    path('class-results/pdf/', views.class_results_pdf, name='class_results_pdf'),
    
    path('teachers/add/', views.add_teacher, name='add_teacher'),
    path('teachers/<int:teacher_id>/delete/', views.delete_teacher, name='delete_teacher'),
    path('staff/add/', views.add_staff, name='add_staff'),
    path('staff/<int:staff_id>/delete/', views.delete_staff, name='delete_staff'),
    path('my-dashboard/', views.redirect_to_own_dashboard, name='redirect_to_own_dashboard'),
    
    path('teacher/professionalism/', views.my_professionalism, name='my_professionalism'),
    path('teacher/professionalism/<int:note_id>/', views.my_professionalism_detail, name='my_professionalism_detail'),
    path('teacher/professionalism/<int:note_id>/acknowledge/', views.my_professionalism_acknowledge, name='my_professionalism_acknowledge'),

    # Accountant
        # Fee Structures
    path('accountant/fee-structures/',
         views.fee_structure_list, name='fee_structure_list'),

    path('accountant/fee-structures/add/',
         views.fee_structure_add, name='fee_structure_add'),

    path('accountant/fee-structures/bulk/',
         views.fee_structure_bulk, name='fee_structure_bulk'),

    path('accountant/fee-structures/<int:fee_id>/edit/',
         views.fee_structure_edit, name='fee_structure_edit'),

    path('accountant/fee-structures/<int:fs_id>/delete/',
         views.fee_structure_delete, name='fee_structure_delete'),

    # Fee Structure Matrix (bulk draft editor)
    path('accountant/fee-structures/matrix/',
         views.fee_structure_matrix, name='fee_structure_matrix'),

    path('accountant/fee-structures/matrix/save/',
         views.fee_structure_matrix_save, name='fee_structure_matrix_save'),

    # Fee Structure PDF (per class)
    path('accountant/fee-structures/class/<path:class_name>/pdf/',
         views.fee_structure_class_pdf, name='fee_structure_class_pdf'),
    path('accountant/invoices/', views.accountant_invoices, name='accountant_invoices'),
    path('accountant/generate-invoices/', views.generate_invoices, name='generate_invoices'),
    path('accountant/invoice/<int:invoice_id>/payment/', views.record_payment, name='record_payment'),
    path('accountant/transactions/', views.accountant_transactions, name='accountant_transactions'),
    path('accountant/expenditure/add/', views.add_expenditure, name='add_expenditure'),
    path('accountant/students/', views.accountant_students, name='accountant_students'),
    path('accountant/class-statement/', views.class_fee_statement, name='class_fee_statement'),
    path('accountant/class-statement/<int:class_id>/pdf/', views.class_fee_statement_pdf, name='class_fee_statement_pdf'),
        # Expenditure
    path('accountant/expenditures/', views.expenditure_list, name='expenditure_list'),
    path('accountant/expenditures/add/', views.expenditure_add, name='expenditure_add'),
    path('accountant/expenditures/<int:expenditure_id>/edit/', views.expenditure_edit, name='expenditure_edit'),
    path('accountant/expenditures/<int:expenditure_id>/delete/', views.expenditure_delete, name='expenditure_delete'),
    path('accountant/expenditures/pdf/', views.expenditure_pdf, name='expenditure_pdf'),
    
        # Fee Structure
    path('accountant/fee-structures/', views.fee_structure_list, name='fee_structure_list'),
    path('accountant/fee-structures/add/', views.fee_structure_add, name='fee_structure_add'),
    path('accountant/fee-structures/bulk/', views.fee_structure_bulk, name='fee_structure_bulk'),
    path('accountant/fee-structures/<int:fee_id>/edit/', views.fee_structure_edit, name='fee_structure_edit'),
    path('accountant/fee-structures/<int:fee_id>/delete/', views.fee_structure_delete, name='fee_structure_delete'),

    # Notifications
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/<int:notif_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_read, name='mark_all_read'),

    # Smart Alerts
    path('alerts/', views.alerts_dashboard, name='alerts_dashboard'),
    path('alerts/scan/', views.run_scan, name='run_scan'),
    path('alerts/<int:alert_id>/resolve/', views.alert_resolve, name='alert_resolve'),
    path('alerts/<int:alert_id>/dismiss/', views.alert_dismiss, name='alert_dismiss'),

    # Super Admin — Schools
    path('schools/', views.schools_manage, name='schools_manage'),
    path('schools/add/', views.school_add, name='school_add'),
    path('schools/<int:school_id>/toggle/', views.school_toggle_active, name='school_toggle_active'),
    path('schools/<int:school_id>/password/', views.school_change_admin_password, name='school_change_admin_password'),
    path('schools/<int:school_id>/delete/', views.school_delete, name='school_delete'),
    path('super-admin/performance/', views.super_admin_performance, name='super_admin_performance'),
    path('schools/<int:school_id>/edit/', views.school_edit, name='school_edit'),
    path('schools/<int:school_id>/remove-logo/', views.school_remove_logo, name='school_remove_logo'),
    path('schools/<int:school_id>/board/add/', views.board_member_add, name='board_member_add'),
    path('schools/board/<int:member_id>/delete/', views.board_member_delete, name='board_member_delete'),
    path('subscriptions/<int:school_id>/edit/', views.subscription_edit_admin, name='subscription_edit_admin'),
    path('schools/<int:school_id>/modules/', views.school_modules_manage,
    name='school_modules_manage'),
    
        # Internal Messaging
    path('messages/', views.messages_inbox, name='messages_inbox'),
    path('messages/compose/', views.compose_message, name='compose_message'),
    path('messages/sent/', views.messages_sent, name='messages_sent'),
    path('messages/<int:recipient_id>/', views.message_detail, name='message_detail'),
    path('messages/<int:recipient_id>/archive/', views.message_archive, name='message_archive'),
    path('messages/<int:message_id>/delete/', views.message_delete, name='message_delete'),
    
        # Subscription payment flow
    path('subscription/<int:school_id>/pending/', views.subscription_payment_pending, name='subscription_payment_pending'),
    path('subscription/<int:school_id>/status/', views.subscription_payment_status, name='subscription_payment_status'),
    path('subscription/<int:school_id>/confirm/', views.confirm_subscription_payment, name='confirm_subscription_payment'),
        # Departments Hub (School Admin)
    path('departments/', views.departments_hub, name='departments_hub'),
    path('departments/transport/', views.departments_transport, name='departments_transport'),
    path('departments/library/', views.departments_library, name='departments_library'),
    path('departments/lab/', views.departments_lab, name='departments_lab'),
    path('departments/health/', views.departments_health, name='departments_health'),
    path('departments/kitchen/', views.departments_kitchen, name='departments_kitchen'),
        # Transport — Vehicle CRUD
    path('departments/transport/vehicles/add/', views.transport_vehicle_form, name='transport_vehicle_add'),
    path('departments/transport/vehicles/<int:vehicle_id>/edit/', views.transport_vehicle_form, name='transport_vehicle_edit'),
    path('departments/transport/vehicles/<int:vehicle_id>/delete/', views.transport_vehicle_delete, name='transport_vehicle_delete'),

    # Transport — Route CRUD
    path('departments/transport/routes/add/', views.transport_route_form, name='transport_route_add'),
    path('departments/transport/routes/<int:route_id>/edit/', views.transport_route_form, name='transport_route_edit'),
    path('departments/transport/routes/<int:route_id>/delete/', views.transport_route_delete, name='transport_route_delete'),

    # Transport — Trip CRUD
    path('departments/transport/trips/add/', views.transport_trip_form, name='transport_trip_add'),
    path('departments/transport/trips/<int:trip_id>/edit/', views.transport_trip_form, name='transport_trip_edit'),
    path('departments/transport/trips/<int:trip_id>/delete/', views.transport_trip_delete, name='transport_trip_delete'),

    # Transport — Fuel Log CRUD
    path('departments/transport/fuel/add/', views.transport_fuel_form, name='transport_fuel_add'),
    path('departments/transport/fuel/<int:fuel_id>/edit/', views.transport_fuel_form, name='transport_fuel_edit'),
    path('departments/transport/fuel/<int:fuel_id>/delete/', views.transport_fuel_delete, name='transport_fuel_delete'),
        # Transport — Trip student assignment
    path('departments/transport/trips/<int:trip_id>/students/', views.transport_trip_students, name='transport_trip_students'),
    path('departments/transport/trips/<int:trip_id>/auto-assign/', views.transport_trip_auto_assign, name='transport_trip_auto_assign'),
    
    # Subscription
    path('subscribe/', RedirectView.as_view(
        url='/dashboard/subscriptions/',
        permanent=False,
    ), name='subscription_view_legacy'),
    # Bulk SMS
    path('tools/bulk-sms/', views.bulk_sms, name='bulk_sms'),

    # Test SMS
    path('tools/sms-test/', views.send_test_sms_view, name='send_test_sms'),
    path('modules/<slug:module_code>/', views.school_module_placeholder, name='school_module_placeholder'),
        # Director of Studies
    path('dos/', include('apps.dashboard.dos_urls')),
        # Placeholder dashboards (until modules built)
        # Store Keeper
    path('store-keeper/', views.store_keeper_dashboard, name='store_keeper_dashboard'),
    path('store-keeper/items/', views.store_items_list, name='store_items_list'),
    path('store-keeper/items/new/', views.store_item_form, name='store_item_create'),
    path('store-keeper/items/<int:item_id>/', views.store_item_detail, name='store_item_detail'),
    path('store-keeper/items/<int:item_id>/edit/', views.store_item_form, name='store_item_edit'),
    #store keeper valuation and Audits
    
    path('store-keeper/valuation/',
         store_views.store_valuation_report,
         name='store_valuation_report'),

    path('store-keeper/valuation/pdf/',
         store_views.store_valuation_pdf,
         name='store_valuation_pdf'),

    path('store-keeper/movements/',
         store_views.store_movements,
         name='store_movements'),

    path('store-keeper/issues/', views.store_issue_list, name='store_issue_list'),
    path('store-keeper/issues/new/', views.store_issue_create, name='store_issue_create'),
    path('store-keeper/issues/<int:issue_id>/', views.store_issue_detail, name='store_issue_detail'),

    path('store-keeper/receipts/', views.store_receipt_list, name='store_receipt_list'),
    path('store-keeper/receipts/new/', views.store_receipt_create, name='store_receipt_create'),

    path('store-keeper/low-stock/', views.store_low_stock, name='store_low_stock'),
    path('store-keeper/categories/', views.store_categories, name='store_categories'),
    path('store-keeper/suppliers/', views.store_suppliers, name='store_suppliers'),
    path('boarding/', views.boarding_dashboard_placeholder, name='boarding_dashboard'),
    
           # Deputy Principal — Academics
    path('dpa-acad/', views.dpa_acad_dashboard, name='dpa_acad_dashboard'),
    path('dpa-acad/exams/', views.dpa_acad_exams, name='dpa_acad_exams'),
    path('dpa-acad/exams/<int:exam_id>/', views.dpa_acad_exam_detail, name='dpa_acad_exam_detail'),
    path('dpa-acad/mark-sheets/', views.dpa_acad_mark_sheets, name='dpa_acad_mark_sheets'),
    path('dpa-acad/mark-sheets/<int:sheet_id>/', views.dpa_acad_mark_sheet_detail, name='dpa_acad_mark_sheet_detail'),
    path('dpa-acad/mark-sheets/<int:sheet_id>/approve/', views.dpa_acad_mark_sheet_approve, name='dpa_acad_mark_sheet_approve'),
    path('dpa-acad/mark-sheets/<int:sheet_id>/reject/', views.dpa_acad_mark_sheet_reject, name='dpa_acad_mark_sheet_reject'),
    path('dpa-acad/mark-sheets/<int:sheet_id>/publish/', views.dpa_acad_mark_sheet_publish, name='dpa_acad_mark_sheet_publish'),
        # Deputy Principal — Academics
    path('dpa-acad/', views.dpa_acad_dashboard, name='dpa_acad_dashboard'),

    # Exams + mark sheets
    path('dpa-acad/exams/', views.dpa_acad_exams, name='dpa_acad_exams'),
    path('dpa-acad/exams/<int:exam_id>/', views.dpa_acad_exam_detail, name='dpa_acad_exam_detail'),
    path('dpa-acad/mark-sheets/', views.dpa_acad_mark_sheets, name='dpa_acad_mark_sheets'),
    path('dpa-acad/mark-sheets/<int:sheet_id>/', views.dpa_acad_mark_sheet_detail, name='dpa_acad_mark_sheet_detail'),
    path('dpa-acad/mark-sheets/<int:sheet_id>/approve/', views.dpa_acad_mark_sheet_approve, name='dpa_acad_mark_sheet_approve'),
    path('dpa-acad/mark-sheets/<int:sheet_id>/reject/', views.dpa_acad_mark_sheet_reject, name='dpa_acad_mark_sheet_reject'),
    path('dpa-acad/mark-sheets/<int:sheet_id>/publish/', views.dpa_acad_mark_sheet_publish, name='dpa_acad_mark_sheet_publish'),

    # Syllabus
    path('dpa-acad/syllabus/', views.dpa_acad_syllabus, name='dpa_acad_syllabus'),

    # Lesson plans
    path('dpa-acad/lesson-plans/', views.dpa_acad_lesson_plans, name='dpa_acad_lesson_plans'),
    path('dpa-acad/lesson-plans/<int:plan_id>/', views.dpa_acad_lesson_plan_detail, name='dpa_acad_lesson_plan_detail'),
    path('dpa-acad/lesson-plans/<int:plan_id>/approve/', views.dpa_acad_lesson_plan_approve, name='dpa_acad_lesson_plan_approve'),
    path('dpa-acad/lesson-plans/<int:plan_id>/revision/', views.dpa_acad_lesson_plan_revision, name='dpa_acad_lesson_plan_revision'),

    # Subject allocation
    path('dpa-acad/subject-allocation/', views.dpa_acad_subject_allocation, name='dpa_acad_subject_allocation'),
    path('dpa-acad/subject-allocation/<int:subject_id>/assign/', views.dpa_acad_subject_assign, name='dpa_acad_subject_assign'),
        # Teachers
    path('dpa-acad/teachers/', views.dpa_acad_teachers, name='dpa_acad_teachers'),
    path('dpa-acad/teachers/<int:teacher_id>/', views.dpa_acad_teacher_detail, name='dpa_acad_teacher_detail'),

    # Timetable conflicts
    path('dpa-acad/timetable-conflicts/', views.dpa_acad_timetable_conflicts, name='dpa_acad_timetable_conflicts'),

    # Remedial classes
    path('dpa-acad/remedial/', views.dpa_acad_remedial, name='dpa_acad_remedial'),
    path('dpa-acad/remedial/new/', views.dpa_acad_remedial_create, name='dpa_acad_remedial_create'),
    path('dpa-acad/remedial/<int:class_id>/update/', views.dpa_acad_remedial_update, name='dpa_acad_remedial_update'),
    path('dpa-acad/teachers/<int:teacher_id>/pdf/', views.dpa_acad_teacher_pdf, name='dpa_acad_teacher_pdf'),
        # Stream-subject assignment
    path('dpa-acad/stream-subjects/', views.dpa_acad_stream_subjects, name='dpa_acad_stream_subjects'),
    path('dpa-acad/stream-subjects/assign/', views.dpa_acad_stream_subject_assign, name='dpa_acad_stream_subject_assign'),
        # Timetables — stream + teacher
    path('dpa-acad/timetables/', views.dpa_acad_timetable_list, name='dpa_acad_timetable_list'),
    path('dpa-acad/timetables/stream/<int:class_id>/', views.dpa_acad_timetable_stream, name='dpa_acad_timetable_stream'),
    path('dpa-acad/timetables/stream/<int:class_id>/pdf/', views.dpa_acad_timetable_stream_pdf, name='dpa_acad_timetable_stream_pdf'),
    path('dpa-acad/timetables/teacher/<int:teacher_id>/pdf/', views.dpa_acad_teacher_timetable_pdf, name='dpa_acad_teacher_timetable_pdf'),
        # Teacher personal timetable (any teacher can access)
    path('teacher/my-timetable/', views.teacher_my_timetable, name='teacher_my_timetable'),
    path('teacher/my-timetable/pdf/', views.teacher_my_timetable_pdf, name='teacher_my_timetable_pdf'),
    path('dpa-acad/_test-header/', views._test_header_pdf, name='_test_header_pdf'),
    path('dpa-acad/exams/new/', views.dpa_acad_exam_create, name='dpa_acad_exam_create'),
    path('teacher/remedial/pdf/', views.teacher_remedial_timetable_pdf, name='teacher_remedial_timetable_pdf'),
    path('dpa-acad/exams/<int:exam_id>/edit/', views.dpa_acad_exam_edit, name='dpa_acad_exam_edit'),
    path('dpa-acad/exams/<int:exam_id>/delete/', views.dpa_acad_exam_delete, name='dpa_acad_exam_delete'),
    path('teacher/remedial/', views.teacher_remedial_schedule, name='teacher_remedial_schedule'),
        # Teacher mark sheet submission
    path('teacher/marksheets/', views.teacher_my_marksheets, name='teacher_my_marksheets'),
    path('teacher/marksheets/<int:sheet_id>/', views.teacher_marksheet_enter, name='teacher_marksheet_enter'),
    path('teacher/lesson-plans/', views.teacher_my_lesson_plans, name='teacher_my_lesson_plans'),
    path('teacher/lesson-plans/new/', views.teacher_lesson_plan_form, name='teacher_lesson_plan_create'),
    path('teacher/lesson-plans/<int:plan_id>/edit/', views.teacher_lesson_plan_form, name='teacher_lesson_plan_edit'),
    path('teacher/syllabus/', views.teacher_my_syllabus, name='teacher_my_syllabus'),
    path('teacher/syllabus/<int:class_id>/<int:subject_id>/', views.teacher_syllabus_detail, name='teacher_syllabus_detail'),
    path('dpa-acad/reports/', views.dpa_acad_reports, name='dpa_acad_reports'),
    path('dpa-admin/staff/<int:user_id>/attendance/pdf/', views.dpa_staff_attendance_pdf_personal, name='dpa_staff_attendance_pdf_personal'),
    path('dpa-admin/staff/attendance/pdf/', views.dpa_staff_attendance_pdf_overall, name='dpa_staff_attendance_pdf_overall'),
    
        # Staff self-service leave
    path('my/leave/', views.my_leave_requests, name='my_leave_requests'),
    path('my/leave/new/', views.my_leave_request_create, name='my_leave_request_create'),
    path('my/leave/<int:leave_id>/', views.my_leave_request_detail, name='my_leave_request_detail'),
    path('my/leave/<int:leave_id>/cancel/', views.my_leave_request_cancel, name='my_leave_request_cancel'),

    # Principal leave review
    path('principal/leave/', views.principal_leave_review, name='principal_leave_review'),
    path('principal/leave/<int:leave_id>/', views.principal_leave_detail, name='principal_leave_detail'),
    path('principal/leave/<int:leave_id>/approve/', views.principal_leave_approve, name='principal_leave_approve'),
    path('principal/leave/<int:leave_id>/reject/', views.principal_leave_reject, name='principal_leave_reject'),
    path('principal/', views.principal_dashboard, name='principal_dashboard'),
    path('dpa-admin/staff/leave/<int:leave_id>/pdf/', views.dpa_leave_pdf, name='dpa_leave_pdf'),
    path('dpa-acad/remedial/schedule/', views.dpa_acad_remedial_schedule, name='dpa_acad_remedial_schedule'),
    path('dpa-acad/remedial/schedule/pdf/', views.dpa_acad_remedial_timetable_pdf, name='dpa_acad_remedial_timetable_pdf'),
]