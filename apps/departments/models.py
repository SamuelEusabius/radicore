from django.db import models
from django.conf import settings


class DepartmentChoices(models.TextChoices):
    TRANSPORT = 'transport', 'Transport'
    LIBRARY = 'library', 'Library'
    LAB = 'lab', 'Laboratory'
    HEALTH = 'health', 'Health / Nurse'
    KITCHEN = 'kitchen', 'Kitchen / Cafeteria'


class DepartmentReport(models.Model):
    """A report submitted by a department staff member."""
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('reviewed', 'Reviewed'),
        ('actioned', 'Actioned'),
    ]
    
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='department_reports'
    )
    department = models.CharField(max_length=20, choices=DepartmentChoices.choices)
    title = models.CharField(max_length=200)
    description = models.TextField()
    report_date = models.DateField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='department_reports_submitted'
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='department_reports_reviewed'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True, default='')
    attachment = models.FileField(upload_to='department_reports/%Y/%m/', null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-report_date', '-created_at']
    
    def __str__(self):
        return f"[{self.get_department_display()}] {self.title} - {self.report_date}"