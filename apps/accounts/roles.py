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