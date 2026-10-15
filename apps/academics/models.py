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
    

# ==========================================================
# SYLLABUS COVERAGE
# ==========================================================

class CoverageStatus(models.TextChoices):
    NOT_STARTED = 'not_started', 'Not Started'
    IN_PROGRESS = 'in_progress', 'In Progress'
    COMPLETED   = 'completed',   'Completed'
    BEHIND      = 'behind',      'Behind Schedule'


class SyllabusCoverage(models.Model):
    """
    Tracks syllabus coverage per subject/class/term.
    Updated by teachers; reviewed by DPA Academics.
    """

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='syllabus_coverage',
    )
    class_level = models.ForeignKey(
        ClassLevel, on_delete=models.CASCADE, related_name='syllabus_coverage',
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='syllabus_coverage',
    )
    teacher = models.ForeignKey(
        'teachers.Teacher', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='syllabus_coverage',
    )

    term = models.CharField(max_length=20, blank=True, default='')
    year = models.PositiveIntegerField()

    topic = models.CharField(max_length=200)
    status = models.CharField(
        max_length=15, choices=CoverageStatus.choices, default=CoverageStatus.NOT_STARTED,
    )
    percent_complete = models.PositiveIntegerField(
        default=0, help_text="0-100 progress of this topic",
    )

    planned_week = models.PositiveIntegerField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')

    updated_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='syllabus_updates',
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['class_level', 'subject', 'planned_week', 'topic']
        verbose_name = 'Syllabus Coverage'
        verbose_name_plural = 'Syllabus Coverage'
        indexes = [
            models.Index(fields=['school', 'year', 'term']),
            models.Index(fields=['school', 'class_level', 'subject']),
        ]

    def __str__(self):
        return f"{self.class_level} · {self.subject} · {self.topic}"


# ==========================================================
# LESSON PLANS
# ==========================================================

class LessonPlanStatus(models.TextChoices):
    DRAFT      = 'draft',      'Draft'
    SUBMITTED  = 'submitted',  'Submitted for Review'
    APPROVED   = 'approved',   'Approved'
    REVISION   = 'revision',   'Needs Revision'
    REJECTED   = 'rejected',   'Rejected'


class LessonPlan(models.Model):
    """
    A teacher's lesson plan for a specific class-period.
    Reviewed and approved by DPA Academics.
    """

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='lesson_plans',
    )
    teacher = models.ForeignKey(
        'teachers.Teacher', on_delete=models.CASCADE, related_name='lesson_plans',
    )
    class_level = models.ForeignKey(
        ClassLevel, on_delete=models.CASCADE, related_name='lesson_plans',
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='lesson_plans',
    )

    title = models.CharField(max_length=200)
    week_ending = models.DateField(help_text="Week the plan covers")
    objectives = models.TextField(blank=True, default='')
    activities = models.TextField(blank=True, default='')
    resources = models.TextField(blank=True, default='')
    assessment_method = models.TextField(blank=True, default='')

    status = models.CharField(
        max_length=15, choices=LessonPlanStatus.choices, default=LessonPlanStatus.DRAFT,
    )

    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lesson_plans_reviewed',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comment = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-week_ending', 'teacher']
        verbose_name = 'Lesson Plan'
        verbose_name_plural = 'Lesson Plans'
        indexes = [
            models.Index(fields=['school', 'status']),
            models.Index(fields=['school', 'week_ending']),
            models.Index(fields=['teacher', 'status']),
        ]

    def __str__(self):
        return f"{self.teacher} · {self.subject} · {self.week_ending}"


# ==========================================================
# REMEDIAL CLASSES
# ==========================================================

class RemedialStatus(models.TextChoices):
    SCHEDULED = 'scheduled', 'Scheduled'
    ONGOING   = 'ongoing',   'Ongoing'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'


class RemedialPeriod(models.TextChoices):
    MORNING = 'morning', 'Morning'
    EVENING = 'evening', 'Evening'


class RemedialClass(models.Model):
    """
    A recurring (or one-off) remedial / extra-tuition session.

    Either `day_of_week` (recurring weekly) or `scheduled_date` (one-off)
    should be set. Both can be set if the session repeats on that date too.
    """

    class SessionPeriod(models.TextChoices):
        MORNING = 'morning', 'Morning (before school)'
        EVENING = 'evening', 'Evening (after school)'

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='remedial_classes',
    )
    class_level = models.ForeignKey(
        ClassLevel, on_delete=models.CASCADE, related_name='remedial_classes',
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='remedial_classes',
    )
    teacher = models.ForeignKey(
        'teachers.Teacher', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='remedial_classes',
    )

    title = models.CharField(max_length=200)
    focus_area = models.TextField(blank=True, default='', help_text="Topics or skills targeted")

    # Schedule — recurring or one-off
    day_of_week = models.CharField(
        max_length=10,
        choices=[
            ('monday', 'Monday'), ('tuesday', 'Tuesday'), ('wednesday', 'Wednesday'),
            ('thursday', 'Thursday'), ('friday', 'Friday'), ('saturday', 'Saturday'),
        ],
        blank=True, default='',
        help_text="For recurring weekly sessions",
    )
    scheduled_date = models.DateField(
        null=True, blank=True,
        help_text="For one-off sessions",
    )
    session_period = models.CharField(
        max_length=10,
        choices=SessionPeriod.choices,
        default=SessionPeriod.EVENING,
    )
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=120, blank=True, default='')

    # Students enrolled
    students = models.ManyToManyField(
        'students.Student', blank=True, related_name='remedial_classes',
    )

    # Status
    status = models.CharField(
        max_length=15,
        choices=RemedialStatus.choices,
        default=RemedialStatus.SCHEDULED,
    )
    notes = models.TextField(blank=True, default='')

    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='remedial_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['day_of_week', 'start_time']
        verbose_name = 'Remedial Class'
        verbose_name_plural = 'Remedial Classes'
        indexes = [
            models.Index(fields=['school', 'status']),
            models.Index(fields=['school', 'day_of_week']),
            models.Index(fields=['class_level', 'day_of_week']),
        ]

    def __str__(self):
        day = self.get_day_of_week_display() if self.day_of_week else (
            self.scheduled_date.strftime('%d %b') if self.scheduled_date else '?'
        )
        return f"{self.title} — {self.class_level.name} — {day}"

    @property
    def time_range(self):
        if self.start_time and self.end_time:
            return f"{self.start_time.strftime('%H:%M')} – {self.end_time.strftime('%H:%M')}"
        if self.start_time:
            return self.start_time.strftime('%H:%M')
        return '—'
    
    

# ==========================================================
# STREAM-SUBJECT TEACHER ASSIGNMENT
# ==========================================================

class StreamSubjectTeacher(models.Model):
    """
    Assigns a teacher to a subject in a specific stream (class_level).

    Source of truth for "who teaches Mathematics in Grade 7 East".
    Timetable entries look up this relationship when created or regenerated.
    """

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='stream_subject_teachers',
    )
    class_level = models.ForeignKey(
        ClassLevel, on_delete=models.CASCADE, related_name='subject_assignments',
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='stream_assignments',
    )
    teacher = models.ForeignKey(
        'teachers.Teacher', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='stream_subject_assignments',
    )

    academic_year = models.PositiveIntegerField(
        help_text="Year this assignment applies to",
    )
    term = models.CharField(
        max_length=20, blank=True, default='',
        help_text="Optional term for term-scoped reassignments",
    )

    notes = models.TextField(blank=True, default='')

    assigned_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='subject_assignments_made',
    )
    assigned_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['class_level__order', 'subject__name']
        unique_together = [('class_level', 'subject', 'academic_year', 'term')]
        verbose_name = 'Stream Subject Teacher'
        verbose_name_plural = 'Stream Subject Teachers'
        indexes = [
            models.Index(fields=['school', 'academic_year']),
            models.Index(fields=['school', 'class_level', 'subject']),
            models.Index(fields=['teacher', 'academic_year']),
        ]

    def __str__(self):
        teacher_name = (
            f"{self.teacher.first_name} {self.teacher.last_name}"
            if self.teacher else "Unassigned"
        )
        return f"{self.class_level.name} · {self.subject.name} → {teacher_name}"