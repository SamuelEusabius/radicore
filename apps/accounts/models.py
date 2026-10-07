from django.contrib.auth.models import AbstractUser
from django.db import models

from .roles import Role


class User(AbstractUser):
    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=32,
        choices=Role.choices,
        default=Role.STUDENT,
    )
    phone = models.CharField(max_length=20, blank=True)
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='users',
    )
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.get_full_name() or self.email} ({self.role})"

    # ---------------- Role helpers ----------------
    @property
    def is_super_admin(self):
        return self.role == Role.SUPER_ADMIN

    @property
    def is_principal(self):
        return self.role == Role.PRINCIPAL

    @property
    def is_deputy_admin(self):
        return self.role == Role.DEPUTY_ADMIN

    @property
    def is_deputy_academics(self):
        return self.role == Role.DEPUTY_ACADEMICS

    @property
    def is_director_of_studies(self):
        return self.role == Role.DIRECTOR_OF_STUDIES

    @property
    def is_class_teacher(self):
        return self.role == Role.CLASS_TEACHER

    @property
    def is_teacher(self):
        return self.role in (Role.TEACHER, Role.CLASS_TEACHER)

    @property
    def is_accountant(self):
        return self.role == Role.ACCOUNTANT

    @property
    def is_secretary(self):
        return self.role == Role.SECRETARY

    @property
    def is_store_keeper(self):
        return self.role == Role.STORE_KEEPER

    @property
    def is_boarding_master(self):
        return self.role == Role.BOARDING_MASTER

    @property
    def is_chief_chef(self):
        return self.role == Role.CHIEF_CHEF

    @property
    def is_security_officer(self):
        return self.role == Role.SECURITY_OFFICER

    @property
    def is_driver(self):
        return self.role == Role.DRIVER

    @property
    def is_lab_technician(self):
        return self.role == Role.LAB_TECHNICIAN

    @property
    def is_librarian(self):
        return self.role == Role.LIBRARIAN

    @property
    def is_nurse(self):
        return self.role == Role.NURSE

    @property
    def is_student(self):
        return self.role == Role.STUDENT

    @property
    def is_parent(self):
        return self.role == Role.PARENT