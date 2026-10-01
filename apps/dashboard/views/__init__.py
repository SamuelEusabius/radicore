"""
Dashboard views package.

Re-exports all views so that `from . import views` continues to work in urls.py.
"""

from .core import (
    redirect_to_own_dashboard,
    super_admin_dash,
    school_admin_dash,
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


# TEMPORARY: import remaining views from views_old.py
from ..views_old import *  # noqa: F401, F403