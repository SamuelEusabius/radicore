from django.urls import path
from . import views
from django.views.generic import RedirectView

urlpatterns = [ 
    path('subscribe/', RedirectView.as_view(
     url='/dashboard/subscriptions/', permanent=False
    )),
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
]