from django.db import models


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