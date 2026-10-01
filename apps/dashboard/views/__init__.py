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


# TEMPORARY: import remaining views from views_old.py
from ..views_old import *  # noqa: F401, F403