from django.db import models


class ClassLevel(models.Model):
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('school', 'name')
        ordering = ['order']

    def __str__(self):
        return self.name


class Subject(models.Model):
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True)
    teacher = models.ForeignKey('accounts.User', on_delete=models.SET_NULL,
                                null=True, blank=True,
                                limit_choices_to={'role': 'teacher'})

    class Meta:
        unique_together = ('school', 'name')

    def __str__(self):
        return self.name


class Timetable(models.Model):
    class Day(models.TextChoices):
        MONDAY    = 'MON', 'Monday'
        TUESDAY   = 'TUE', 'Tuesday'
        WEDNESDAY = 'WED', 'Wednesday'
        THURSDAY  = 'THU', 'Thursday'
        FRIDAY    = 'FRI', 'Friday'
        SATURDAY  = 'SAT', 'Saturday'
        SUNDAY    = 'SUN', 'Sunday'

    school = models.ForeignKey('schools.School', on_delete=models.CASCADE)
    class_level = models.ForeignKey(ClassLevel, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    day_of_week = models.CharField(max_length=10, choices=Day.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        return f"{self.class_level} - {self.subject} ({self.get_day_of_week_display()})"