"""
Dashboard views package.

Re-exports all views so that `from . import views` continues to work in urls.py.
"""

from .core import (
    redirect_dashboard,
    redirect_to_own_dashboard,
    dashboard_placeholder,
    super_admin_dash,
    school_admin_dash,
    store_keeper_dashboard_placeholder,
    boarding_dashboard_placeholder,
)

from .subscription import (
    subscription_view,
    subscription_edit_admin,
    subscription_admin_picker,
    subscription_payment_pending,
    subscription_payment_status,
    confirm_subscription_payment,
    subscription_plans,
    subscription_confirm,
    subscription_payment,
)

from .students import (
    students_list,
    student_dash,
    add_student,
    delete_student,
    clear_student,
    leaving_certificate,
    leaving_certificate_pdf,
    student_biodata_pdf,
    student_detail,
)

from .parents import (
    parents_list,
    parent_dash,
    parent_children,
    parent_child_detail,
    add_parent,
    delete_parent,
    link_parent_children,
    parent_child_statement_pdf,
)

from .teachers import (
    teachers_list,
    teacher_dash,
    teacher_timetable,
    add_teacher,
    delete_teacher,
    class_teacher_dashboard,
    class_teacher_parents,
    class_teacher_view_parent,
    class_teacher_view_student,
    class_teacher_parents_download,
    _ct_teacher_and_class,
)

from .attendance import (
    teacher_attendance,
    class_teacher_attendance,
    class_teacher_attendance_sheet,
    class_teacher_attendance_pdf,
    admin_attendance_overview,
    admin_class_attendance,
    admin_attendance_export,
)

from .grades import (
    manage_exams,
    enter_grades,
    class_results,
    class_results_pdf,
    class_teacher_grades,
    class_teacher_new_exam,
    class_teacher_rankings,
    class_teacher_rankings_download,
    _ct_build_rankings,
    class_teacher_results_sheet_pdf,
    class_teacher_all_report_cards_zip,
    class_teacher_all_report_cards_merged,
    _render_report_card_pdf,
)

from .finance import (
    accountant_dash,
    accountant_invoices,
    accountant_transactions,
    accountant_students,
    generate_invoices,
    invoice_student_quick,
    record_payment,
    financial_report_pdf,
    class_fee_statement,
    class_fee_statement_pdf,
    fee_structure_list,
    fee_structure_add,
    fee_structure_edit,
    fee_structure_delete,
    fee_structure_bulk,
    fee_structure_matrix,
    fee_structure_matrix_save,
    fee_structure_class_pdf,
    expenditure_list,
    expenditure_add,
    expenditure_edit,
    expenditure_delete,
    expenditure_pdf,
    add_expenditure,
)

from .communication import (
    notifications_list,
    mark_notification_read,
    mark_all_read,
    alerts_dashboard,
    alert_resolve,
    alert_dismiss,
    run_scan,
    send_test_sms_view,
    bulk_sms,
    messages_inbox,
    message_detail,
    message_archive,
    compose_message,
    messages_sent,
    message_delete,
    admin_alerts_list,
    admin_alert_resolve,
)

from .admin_schools import (
    super_admin_dash,
    manage_users,
    create_user,
    schools_manage,
    school_add,
    school_toggle_active,
    school_change_admin_password,
    school_delete,
    school_edit,
    school_remove_logo,
    board_member_add,
    board_member_delete,
    super_admin_performance,
    admin_student_detail,
    school_modules_manage,
)

from .users import (
    staff_list,
    add_staff,
    delete_staff,
    user_deactivate,
    user_delete,
    user_change_role,
    user_change_password,
)

from .academics import (
    manage_classes,
    manage_subjects,
    subject_delete,
)

from .timetable import (
    timetable_view,
    timetable_add,
    timetable_delete,
    timetable_pdf,
)

from .modules import *
from .departments_admin import (
    departments_hub,
    departments_transport,
    departments_library,
    departments_lab,
    departments_health,
    departments_kitchen,
)
from .departments_admin import (
    transport_vehicle_form,
    transport_vehicle_delete,
    transport_route_form,
    transport_route_delete,
    transport_trip_form,
    transport_trip_delete,
    transport_fuel_form,
    transport_fuel_delete,
)
from .departments_admin import (
    transport_vehicle_form, transport_vehicle_delete,
    transport_route_form, transport_route_delete,
    transport_trip_form, transport_trip_delete,
    transport_fuel_form, transport_fuel_delete,
    transport_trip_students, transport_trip_auto_assign,

)
from . import dos_views
from .dpa_admin import (
    dpa_admin_dashboard,
    dpa_approve_leave,
    dpa_reject_leave,
    dpa_discipline_list,
    dpa_discipline_detail,
    dpa_discipline_create,
    dpa_discipline_edit,
    dpa_discipline_escalate,
    dpa_leave_out_create,
    dpa_leave_out_approve,
    dpa_leave_out_detail,
    dpa_leave_out_toggle_notify,
    dpa_leave_out_list,
    dpa_discipline_report,
    dpa_discipline_report_pdf,
    dpa_staff_attendance,
    dpa_staff_attendance_history,
    dpa_duty_roster,
    dpa_duty_create,
    dpa_duty_roster_pdf,
    dpa_duty_toggle_complete,
    dpa_duty_delete,
    dpa_leave_detail,
    dpa_leave_list,
    dpa_leave_principal_approve,
    dpa_leave_out_pdf,
    dpa_staff_movement,
    dpa_staff_movement_create,
    dpa_staff_directory,
    dpa_staff_detail,
    dpa_student_attendance,
    dpa_student_attendance_class,
    dpa_student_movement,
    dpa_student_movement_create,
    dpa_student_movement_return,
    dpa_admin_cases,
    dpa_admin_case_create,
    dpa_admin_case_detail,
    dpa_admin_case_update,
)

from .dpa_academics import (
    dpa_acad_dashboard,
    dpa_acad_exams,
    dpa_acad_exam_detail,
    dpa_acad_mark_sheets,
    dpa_acad_mark_sheet_detail,
    dpa_acad_mark_sheet_approve,
    dpa_acad_mark_sheet_reject,
    dpa_acad_mark_sheet_publish,
    dpa_acad_syllabus,
    dpa_acad_lesson_plans,
    dpa_acad_lesson_plan_detail,
    dpa_acad_lesson_plan_approve,
    dpa_acad_lesson_plan_revision,
    dpa_acad_subject_allocation,
    dpa_acad_subject_assign,
    dpa_acad_teachers,
    dpa_acad_teacher_detail,
    dpa_acad_timetable_conflicts,
    dpa_acad_remedial,
    dpa_acad_remedial_create,
    dpa_acad_remedial_update,
    dpa_acad_teacher_pdf,
    dpa_acad_stream_subjects,
    dpa_acad_stream_subject_assign,
    dpa_acad_timetable_list,
    dpa_acad_timetable_stream,
    dpa_acad_timetable_stream_pdf,
    teacher_my_timetable,
    teacher_my_timetable_pdf,
    dpa_acad_teacher_timetable_pdf,
    _test_header_pdf,
    dpa_acad_exam_create,
    dpa_acad_exam_edit,
    dpa_acad_exam_delete,
    teacher_my_marksheets,
    teacher_marksheet_enter,
    teacher_my_lesson_plans,
    teacher_lesson_plan_form,
    teacher_my_syllabus,
    teacher_syllabus_detail,
    dpa_acad_reports,
    dpa_staff_attendance_pdf_personal,
    dpa_staff_attendance_pdf_overall,
)