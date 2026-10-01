from django.db import models


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'P', 'Present'
        ABSENT  = 'A', 'Absent'
        LATE    = 'L', 'Late'
        EXCUSED = 'E', 'Excused'

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    status = models.CharField(max_length=1, choices=Status.choices, default=Status.PRESENT)
    recorded_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ('student', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.student} — {self.date} ({self.status})"