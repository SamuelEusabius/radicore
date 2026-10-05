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

# ============================================================
# DRIVER — Transport Module
# ============================================================

class Vehicle(models.Model):
    """A school vehicle (bus, van, etc.)."""
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='vehicles'
    )
    plate_number = models.CharField(max_length=20)
    make = models.CharField(max_length=50, blank=True)
    model = models.CharField(max_length=50, blank=True)
    capacity = models.PositiveIntegerField(default=40)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['plate_number']
        unique_together = ('school', 'plate_number')

    def __str__(self):
        return f"{self.plate_number} ({self.make} {self.model})"


class Route(models.Model):
    """A bus route with pickup/dropoff stops."""
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='routes'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    morning_departure = models.TimeField(null=True, blank=True)
    evening_departure = models.TimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Trip(models.Model):
    """A single trip (morning or evening) for a route."""
    DIRECTION_CHOICES = [
        ('morning', 'Morning (Home -> School)'),
        ('evening', 'Evening (School -> Home)'),
    ]
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='trips'
    )
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='trips')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True)
    driver = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        related_name='trips_driven'
    )

    date = models.DateField()
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    departure_time = models.TimeField(null=True, blank=True)
    arrival_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'direction']

    def __str__(self):
        return f"{self.route.name} - {self.date} - {self.get_direction_display()}"

    @property
    def student_count(self):
        return self.trip_students.count()


class TripStudent(models.Model):
    """A student on a specific trip."""
    BOARDING_STATUS = [
        ('pending', 'Pending'),
        ('boarded', 'Boarded'),
        ('dropped', 'Dropped Off'),
        ('absent', 'Absent'),
    ]

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='trip_students')
    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE,
        related_name='trips'
    )
    boarding_status = models.CharField(
        max_length=20, choices=BOARDING_STATUS, default='pending'
    )
    boarded_at = models.DateTimeField(null=True, blank=True)
    dropped_at = models.DateTimeField(null=True, blank=True)
    stop_name = models.CharField(max_length=100, blank=True)
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ('trip', 'student')

    def __str__(self):
        return f"{self.student.full_name} on {self.trip}"


class FuelLog(models.Model):
    """Fuel/energy purchase log for a vehicle."""
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('mpesa', 'M-Pesa'),
        ('card', 'Fuel Card'),
        ('credit', 'Credit (Supplier)'),
        ('other', 'Other'),
    ]

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='fuel_logs'
    )
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='fuel_logs')
    driver = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        related_name='fuel_logs'
    )

    date = models.DateField()
    amount_kes = models.DecimalField(max_digits=10, decimal_places=2)
    litres = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    odometer_reading = models.PositiveIntegerField(null=True, blank=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    payment_reference = models.CharField(max_length=100, blank=True)
    station_name = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    receipt = models.FileField(upload_to='fuel_receipts/%Y/%m/', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.vehicle.plate_number} - KES {self.amount_kes}"


class PreTripChecklist(models.Model):
    """Pre-trip vehicle inspection."""
    trip = models.OneToOneField(Trip, on_delete=models.CASCADE, related_name='checklist')
    brakes_ok = models.BooleanField(default=False)
    tyres_ok = models.BooleanField(default=False)
    lights_ok = models.BooleanField(default=False)
    mirrors_ok = models.BooleanField(default=False)
    fuel_sufficient = models.BooleanField(default=False)
    first_aid_kit = models.BooleanField(default=False)
    fire_extinguisher = models.BooleanField(default=False)
    seatbelts_ok = models.BooleanField(default=False)
    issues_found = models.TextField(blank=True)
    is_cleared = models.BooleanField(default=False)
    cleared_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Checklist for {self.trip}"
    

# ============================================================
# LIBRARY MODULE
# ============================================================

class Book(models.Model):
    """A book in the school library."""
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('out_of_stock', 'Out of Stock'),
        ('archived', 'Archived'),
    ]

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='books'
    )
    title = models.CharField(max_length=300)
    author = models.CharField(max_length=200, blank=True)
    isbn = models.CharField(max_length=30, blank=True)
    category = models.CharField(max_length=100, blank=True)
    publisher = models.CharField(max_length=150, blank=True)
    edition = models.CharField(max_length=50, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)

    total_copies = models.PositiveIntegerField(default=1)
    shelf_location = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    cover = models.ImageField(upload_to='library/covers/', null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return f"{self.title} ({self.author})"

    @property
    def available_copies(self):
        """Count copies not currently issued."""
        issued = self.issues.filter(status='issued').count()
        return max(0, self.total_copies - issued)

    @property
    def is_available(self):
        return self.available_copies > 0


class BookIssue(models.Model):
    """A book issue/return record."""
    STATUS_CHOICES = [
        ('issued', 'Issued'),
        ('returned', 'Returned'),
        ('lost', 'Lost'),
        ('damaged', 'Damaged'),
    ]

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='book_issues'
    )
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='issues')
    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE,
        related_name='book_issues'
    )

    issue_date = models.DateField()
    due_date = models.DateField()
    return_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='issued')
    fine_kes = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    fine_paid = models.BooleanField(default=False)

    issued_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        related_name='books_issued'
    )
    returned_to = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='books_received'
    )

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-issue_date']

    def __str__(self):
        return f"{self.book.title} → {self.student.full_name}"

    @property
    def is_overdue(self):
        if self.status != 'issued':
            return False
        from datetime import date
        return self.due_date < date.today()

    @property
    def days_overdue(self):
        if not self.is_overdue:
            return 0
        from datetime import date
        return (date.today() - self.due_date).days