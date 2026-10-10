from django.db import models
from django.conf import settings

class Exam(models.Model):
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    term = models.CharField(max_length=20)
    year = models.PositiveIntegerField()
    date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} — {self.term} {self.year}"


class Grade(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='grades')
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE)
    subject = models.ForeignKey('academics.Subject', on_delete=models.CASCADE)
    marks = models.DecimalField(max_digits=5, decimal_places=2)
    out_of = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    remarks = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ('exam', 'student', 'subject')

    @property
    def percentage(self):
        return (self.marks / self.out_of) * 100 if self.out_of else 0

    def __str__(self):
        return f"{self.student} - {self.subject} ({self.marks}/{self.out_of})"
    
    

# ==========================================================
# MARK SHEET (per class-exam-subject submission)
# ==========================================================

class MarkSheetStatus(models.TextChoices):
    DRAFT      = 'draft',      'Draft'
    SUBMITTED  = 'submitted',  'Submitted'
    APPROVED   = 'approved',   'Approved'
    PUBLISHED  = 'published',  'Published'
    REJECTED   = 'rejected',   'Rejected'


class MarkSheet(models.Model):
    """
    Wraps the collection of grades for one subject in one class for one exam.
    Provides the approval and publish workflow.
    """

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='mark_sheets',
    )
    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE, related_name='mark_sheets',
    )
    class_level = models.ForeignKey(
        'academics.ClassLevel', on_delete=models.CASCADE, related_name='mark_sheets',
    )
    subject = models.ForeignKey(
        'academics.Subject', on_delete=models.CASCADE, related_name='mark_sheets',
    )
    teacher = models.ForeignKey(
        'teachers.Teacher', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='mark_sheets',
    )

    status = models.CharField(
        max_length=15, choices=MarkSheetStatus.choices, default=MarkSheetStatus.DRAFT,
    )

    total_students = models.PositiveIntegerField(default=0)
    total_graded = models.PositiveIntegerField(default=0)

    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='mark_sheets_submitted',
    )

    reviewed_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='mark_sheets_reviewed',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comment = models.TextField(blank=True, default='')

    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='mark_sheets_published',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-exam__date', 'class_level', 'subject']
        unique_together = [('exam', 'class_level', 'subject')]
        verbose_name = 'Mark Sheet'
        verbose_name_plural = 'Mark Sheets'
        indexes = [
            models.Index(fields=['school', 'status']),
            models.Index(fields=['exam', 'class_level']),
        ]

    def __str__(self):
        return f"{self.exam} · {self.class_level} · {self.subject}"

    @property
    def completion_percent(self):
        if self.total_students == 0:
            return 0
        return round((self.total_graded / self.total_students) * 100)