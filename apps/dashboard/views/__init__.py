"""
Dashboard views package.

Re-exports all views so that `from . import views` continues to work in urls.py.

As we split views_old.py into modules, add new imports here.
"""

from .core import (
    redirect_to_own_dashboard,
    super_admin_dash,
    school_admin_dash,
)


# ==========================================================
# TEMPORARY: import remaining views from views_old.py
# ==========================================================
# This keeps urls.py working during the refactor.
# As we move views into modules, we remove them from here.
# When views_old.py is empty, delete this import.

from ..views_old import *  # noqa: F401, F403