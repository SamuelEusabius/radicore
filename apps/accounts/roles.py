"""
Central role definitions for ElimuCore.

Single source of truth for all roles in the system.
Changing roles here does NOT change the database by itself —
a migration is required to update the choices stored in User.role.
"""
from django.db import models
class Role(models.TextChoices):
    # ---------- Platform ----------
    SUPER_ADMIN = 'super_admin', 'Super Admin'

    # ---------- School leadership ----------
    PRINCIPAL = 'principal', 'Principal'
    DEPUTY_ADMIN = 'deputy_admin', 'Deputy Principal — Administration'
    DEPUTY_ACADEMICS = 'deputy_academics', 'Deputy Principal — Academics'
    DIRECTOR_OF_STUDIES = 'director_of_studies', 'Director of Studies'

    # ---------- Teaching ----------
    CLASS_TEACHER = 'class_teacher', 'Class Teacher'
    TEACHER = 'teacher', 'Teacher'

    # ---------- Finance / admin ----------
    ACCOUNTANT = 'accountant', 'Accountant / Bursar'
    SECRETARY = 'secretary', 'Secretary'

    # ---------- Operations ----------
    STORE_KEEPER = 'store_keeper', 'Store Keeper'
    BOARDING_MASTER = 'boarding_master', 'Boarding Master'
    CHIEF_CHEF = 'chief_chef', 'Chief Chef'
    SECURITY_OFFICER = 'security_officer', 'Chief Security Officer'
    DRIVER = 'driver', 'Driver'
    LAB_TECHNICIAN = 'lab_technician', 'Lab Technician'
    LIBRARIAN = 'librarian', 'Librarian'
    NURSE = 'nurse', 'Nurse'

    # ---------- End users ----------
    STUDENT = 'student', 'Student'
    PARENT = 'parent', 'Parent'


# ---------------- Convenience groupings ----------------

SCHOOL_LEADERSHIP = frozenset({
    Role.PRINCIPAL,
    Role.DEPUTY_ADMIN,
    Role.DEPUTY_ACADEMICS,
    Role.DIRECTOR_OF_STUDIES,
})

TEACHING_STAFF = frozenset({
    Role.PRINCIPAL,
    Role.DEPUTY_ADMIN,
    Role.DEPUTY_ACADEMICS,
    Role.DIRECTOR_OF_STUDIES,
    Role.CLASS_TEACHER,
    Role.TEACHER,
})

OPERATIONS_STAFF = frozenset({
    Role.STORE_KEEPER,
    Role.BOARDING_MASTER,
    Role.CHIEF_CHEF,
    Role.SECURITY_OFFICER,
    Role.DRIVER,
    Role.LAB_TECHNICIAN,
    Role.LIBRARIAN,
    Role.NURSE,
})

SCHOOL_STAFF = SCHOOL_LEADERSHIP | TEACHING_STAFF | OPERATIONS_STAFF | frozenset({
    Role.ACCOUNTANT,
    Role.SECRETARY,
})

ASSIGNABLE_SCHOOL_ROLES = SCHOOL_STAFF | frozenset({
    Role.STUDENT,
    Role.PARENT,
})


# Legacy role names → new names (used by data migration)
LEGACY_ROLE_MAP = {
    'school_admin': Role.PRINCIPAL.value,
}
# ============================================================
# ROLE CREATION POLICY
# ============================================================

SCHOOL_ADMIN_CREATABLE_ROLES = (
    'deputy_admin',
    'deputy_academics',
    'director_of_studies',
    'secretary',
    'boarding_master',
    'teacher',
    'accountant',
    'security_officer',
    'store_keeper',
    'chief_chef',
    'nurse',
    'librarian',
    'lab_technician',
    'driver',
    'parent',
    'student',
)
SUPER_ADMIN_CREATABLE_ROLES = (
    'principal',
)
SCHOOL_ADMIN_ROLE_LABELS = {
    'deputy_admin': 'Deputy Principal — Administration',
    'deputy_academics': 'Deputy Principal — Academics',
    'director_of_studies': 'Director of Studies',
    'secretary': 'Secretary',
    'boarding_master': 'Boarding Master',
    'teacher': 'Teacher',
    'accountant': 'Accountant',
    'security_officer': 'Chief Security Officer',
    'store_keeper': 'Store Keeper',
    'chief_chef': 'Chief Chef',
    'nurse': 'Nurse',
    'librarian': 'Librarian',
    'lab_technician': 'Lab Technician',
    'driver': 'Driver',
    'parent': 'Parent',
    'student': 'Student',
}


def creatable_roles_for(actor_role):
    """
    Return an ordered list of (value, label) pairs the given
    actor role is permitted to create/assign.

    Order follows SCHOOL_ADMIN_ROLE_LABELS; any role present in
    the allow list but missing a label falls back to Role.choices.
    """
    if actor_role == 'super_admin':
        allowed = SUPER_ADMIN_CREATABLE_ROLES
    elif actor_role == 'principal':
        allowed = SCHOOL_ADMIN_CREATABLE_ROLES
    else:
        return []

    choices_map = dict(Role.choices)
    ordered = []
    for value in allowed:
        label = SCHOOL_ADMIN_ROLE_LABELS.get(value) or choices_map.get(value, value)
        ordered.append((value, label))
    return ordered


def can_create_role(actor_role, target_role):
    """True if `actor_role` may create or assign `target_role`."""
    if actor_role == 'super_admin':
        return target_role in SUPER_ADMIN_CREATABLE_ROLES
    if actor_role == 'principal':
        return target_role in SCHOOL_ADMIN_CREATABLE_ROLES
    return False