from django.db import models


class Parent(models.Model):
    class Relationship(models.TextChoices):
        FATHER   = 'father',   'Father'
        MOTHER   = 'mother',   'Mother'
        GUARDIAN = 'guardian', 'Guardian'
        OTHER    = 'other',    'Other'

    user = models.OneToOneField('accounts.User', on_delete=models.CASCADE, related_name='parent_profile')

    # Personal
    first_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80, blank=True)
    id_number = models.CharField(max_length=20, blank=True, help_text="National ID")
    occupation = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    photo = models.ImageField(upload_to='parents/photos/', blank=True, null=True)

    relationship = models.CharField(max_length=20, choices=Relationship.choices, default=Relationship.GUARDIAN)

    students = models.ManyToManyField('students.Student', related_name='parents', blank=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.email