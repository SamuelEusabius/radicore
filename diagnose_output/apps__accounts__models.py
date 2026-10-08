from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN         = 'super_admin',         'Super Admin'
        SCHOOL_ADMIN        = 'school_admin',        'School Admin'
        TEACHER             = 'teacher',             'Teacher'
        PARENT              = 'parent',              'Parent'
        ACCOUNTANT          = 'accountant',          'Accountant'
        STUDENT             = 'student',             'Student'
        DRIVER              = 'driver',              'Driver'
        LIBRARIAN           = 'librarian',           'Librarian'
        LAB_TECHNICIAN      = 'lab_technician',      'Lab Technician'
        NURSE               = 'nurse',               'Nurse'
        CHIEF_CHEF          = 'chief_chef',          'Chief Chef'
        DIRECTOR_OF_STUDIES = 'director_of_studies', 'Director of Studies'
        STORE_KEEPER        = 'store_keeper',        'Store Keeper'
        BOARDING_MASTER     = 'boarding_master',     'Boarding Master'
        
        
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    phone = models.CharField(max_length=20, blank=True)
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        null=True, blank=True, related_name='users'
    )
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.get_full_name() or self.email} ({self.role})"

    @property
    def is_super_admin(self):  return self.role == self.Role.SUPER_ADMIN
    @property
    def is_school_admin(self): return self.role == self.Role.SCHOOL_ADMIN
    @property
    def is_teacher(self):      return self.role == self.Role.TEACHER
    @property
    def is_parent(self):       return self.role == self.Role.PARENT
    @property
    def is_accountant(self):   return self.role == self.Role.ACCOUNTANT
    @property
    def is_student(self):      return self.role == self.Role.STUDENT