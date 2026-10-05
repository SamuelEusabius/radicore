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
    

# ============================================================
# HEALTH / NURSE MODULE
# ============================================================

class HealthVisit(models.Model):
    """A student's visit to the school nurse."""
    VISIT_TYPES = [
        ('routine', 'Routine Check'),
        ('illness', 'Illness'),
        ('injury', 'Injury'),
        ('emergency', 'Emergency'),
        ('followup', 'Follow-up'),
    ]

    OUTCOME_CHOICES = [
        ('treated', 'Treated & Returned to Class'),
        ('resting', 'Resting in Sick Bay'),
        ('sent_home', 'Sent Home'),
        ('referred', 'Referred to Hospital'),
        ('observation', 'Under Observation'),
    ]

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='health_visits'
    )
    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE,
        related_name='health_visits'
    )

    visit_date = models.DateField()
    visit_time = models.TimeField(null=True, blank=True)
    visit_type = models.CharField(max_length=20, choices=VISIT_TYPES, default='illness')

    symptoms = models.TextField(help_text="What the student reported / what the nurse observed")
    diagnosis = models.CharField(max_length=200, blank=True)
    treatment = models.TextField(blank=True, help_text="What was administered")

    outcome = models.CharField(
        max_length=20, choices=OUTCOME_CHOICES, default='treated'
    )
    referred_to = models.CharField(
        max_length=200, blank=True,
        help_text="Hospital / clinic name if referred"
    )
    guardian_notified = models.BooleanField(default=False)
    guardian_notified_at = models.DateTimeField(null=True, blank=True)

    attended_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        related_name='health_visits_attended'
    )
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-visit_date', '-created_at']

    def __str__(self):
        return f"{self.student.full_name} — {self.visit_date}"


class Medicine(models.Model):
    """Medicine stock in the school clinic."""
    CATEGORY_CHOICES = [
        ('painkiller', 'Painkiller / Analgesic'),
        ('antibiotic', 'Antibiotic'),
        ('antimalarial', 'Antimalarial'),
        ('antihistamine', 'Antihistamine / Allergy'),
        ('firstaid', 'First Aid Supply'),
        ('vitamin', 'Vitamin / Supplement'),
        ('other', 'Other'),
    ]

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='medicines'
    )
    name = models.CharField(max_length=150)
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default='other'
    )
    unit = models.CharField(
        max_length=20, blank=True, default='tablets',
        help_text="e.g. tablets, ml, sachets, tubes"
    )
    quantity = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(
        default=10, help_text="Alert when quantity drops below this"
    )
    expiry_date = models.DateField(null=True, blank=True)
    supplier = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.quantity} {self.unit})"

    @property
    def is_low_stock(self):
        return self.quantity <= self.reorder_level

    @property
    def is_expiring_soon(self):
        if not self.expiry_date:
            return False
        from datetime import date, timedelta
        return self.expiry_date <= date.today() + timedelta(days=30)

    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        from datetime import date
        return self.expiry_date < date.today()


class MedicineLog(models.Model):
    """Stock movement — in/out."""
    ACTION_CHOICES = [
        ('in', 'Stock In (Purchase)'),
        ('out', 'Stock Out (Dispensed)'),
        ('adjust', 'Adjustment'),
        ('expired', 'Removed (Expired)'),
        ('damaged', 'Removed (Damaged)'),
    ]

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='medicine_logs'
    )
    medicine = models.ForeignKey(
        Medicine, on_delete=models.CASCADE, related_name='logs'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    quantity = models.PositiveIntegerField()
    balance_after = models.PositiveIntegerField(default=0)

    related_visit = models.ForeignKey(
        HealthVisit, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='medicine_logs',
        help_text="If dispensed during a visit"
    )
    reason = models.CharField(max_length=200, blank=True)
    recorded_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} {self.quantity} {self.medicine.name}"
    

# ============================================================
# KITCHEN / CHIEF CHEF MODULE
# ============================================================

class Meal(models.Model):
    """A meal served in the school (breakfast, lunch, etc.)."""
    MEAL_TYPES = [
        ('breakfast', 'Breakfast'),
        ('mid_morning', 'Mid-Morning Snack'),
        ('lunch', 'Lunch'),
        ('afternoon', 'Afternoon Snack'),
        ('supper', 'Supper'),
    ]

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='meals'
    )
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPES)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    served_time = models.TimeField(null=True, blank=True)
    cost_per_head = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text="Estimated cost per student in KES"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['meal_type', 'name']
        unique_together = ('school', 'meal_type', 'name')

    def __str__(self):
        return f"{self.name} ({self.get_meal_type_display()})"


class MealPlan(models.Model):
    """A meal planned for a specific date."""
    DAYS_OF_WEEK = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    ]

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='meal_plans'
    )
    date = models.DateField()
    meal = models.ForeignKey(
        Meal, on_delete=models.CASCADE, related_name='plans'
    )
    head_count = models.PositiveIntegerField(
        default=0, help_text="Expected number of students/staff"
    )
    notes = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        related_name='meal_plans_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', 'meal__meal_type']
        unique_together = ('school', 'date', 'meal')

    def __str__(self):
        return f"{self.date} — {self.meal.name}"


class KitchenStock(models.Model):
    """Food items in the kitchen storeroom."""
    CATEGORY_CHOICES = [
        ('cereal', 'Cereals (Maize, Rice, Flour)'),
        ('legume', 'Legumes (Beans, Peas, Lentils)'),
        ('vegetable', 'Vegetables'),
        ('fruit', 'Fruits'),
        ('protein', 'Protein (Meat, Fish, Eggs)'),
        ('dairy', 'Dairy (Milk, Cheese)'),
        ('cooking_fat', 'Cooking Oil / Fat'),
        ('spice', 'Spices / Condiments'),
        ('beverage', 'Beverages'),
        ('other', 'Other'),
    ]

    UNIT_CHOICES = [
        ('kg', 'Kilograms'),
        ('g', 'Grams'),
        ('litre', 'Litres'),
        ('ml', 'Millilitres'),
        ('pieces', 'Pieces'),
        ('packets', 'Packets'),
        ('bags', 'Bags'),
    ]

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='kitchen_stock'
    )
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='kg')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reorder_level = models.DecimalField(max_digits=10, decimal_places=2, default=10)
    unit_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Cost per unit in KES"
    )
    supplier = models.CharField(max_length=150, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = ('school', 'name')

    def __str__(self):
        return f"{self.name} ({self.quantity} {self.get_unit_display()})"

    @property
    def is_low_stock(self):
        return self.quantity <= self.reorder_level

    @property
    def total_value(self):
        return self.quantity * self.unit_cost


class KitchenLog(models.Model):
    """Stock movements — purchase, usage, wastage."""
    ACTION_CHOICES = [
        ('in', 'Stock In (Purchase)'),
        ('used', 'Used in Cooking'),
        ('adjust', 'Adjustment'),
        ('wastage', 'Wastage / Spoiled'),
        ('donated', 'Donation Received'),
    ]

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='kitchen_logs'
    )
    stock_item = models.ForeignKey(
        KitchenStock, on_delete=models.CASCADE, related_name='logs'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reason = models.CharField(max_length=200, blank=True)
    related_meal_plan = models.ForeignKey(
        MealPlan, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='kitchen_logs'
    )
    recorded_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} {self.quantity} {self.stock_item.name}"


class MealServing(models.Model):
    """Record of a meal actually served — for headcount."""
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='meal_servings'
    )
    meal_plan = models.ForeignKey(
        MealPlan, on_delete=models.CASCADE, related_name='servings'
    )
    served_at = models.DateTimeField(auto_now_add=True)
    students_served = models.PositiveIntegerField(default=0)
    staff_served = models.PositiveIntegerField(default=0)
    guests_served = models.PositiveIntegerField(default=0)
    wastage_plates = models.PositiveIntegerField(default=0, help_text="Plates returned / wasted")
    notes = models.TextField(blank=True)
    served_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        related_name='meals_served'
    )

    class Meta:
        ordering = ['-served_at']

    def __str__(self):
        return f"Serving — {self.meal_plan}"

    @property
    def total_served(self):
        return self.students_served + self.staff_served + self.guests_served
    

# ============================================================
# LABORATORY / LAB TECHNICIAN MODULE
# ============================================================

class LabEquipment(models.Model):
    """Laboratory equipment inventory."""
    CATEGORY_CHOICES = [
        ('microscope', 'Microscopes'),
        ('glassware', 'Glassware (Beakers, Flasks)'),
        ('measuring', 'Measuring Instruments'),
        ('burner', 'Burners / Heating'),
        ('chemical', 'Chemicals / Reagents'),
        ('specimen', 'Specimens / Models'),
        ('safety', 'Safety Equipment'),
        ('apparatus', 'Apparatus / Kits'),
        ('other', 'Other'),
    ]

    CONDITION_CHOICES = [
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('needs_repair', 'Needs Repair'),
        ('broken', 'Broken'),
    ]

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='lab_equipment'
    )
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    quantity = models.PositiveIntegerField(default=1)
    working_quantity = models.PositiveIntegerField(default=1)
    condition = models.CharField(
        max_length=20, choices=CONDITION_CHOICES, default='good'
    )
    location = models.CharField(
        max_length=100, blank=True,
        help_text="e.g. Shelf A, Cabinet 2"
    )
    purchase_date = models.DateField(null=True, blank=True)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    supplier = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'name']
        unique_together = ('school', 'name')

    def __str__(self):
        return f"{self.name} ({self.working_quantity}/{self.quantity} working)"

    @property
    def is_functional(self):
        return self.working_quantity > 0

    @property
    def total_value(self):
        return self.quantity * self.unit_cost


class LabIncident(models.Model):
    """Lab incident / equipment breakage report."""
    INCIDENT_CHOICES = [
        ('breakage', 'Equipment Breakage'),
        ('chemical_spill', 'Chemical Spill'),
        ('injury', 'Student / Staff Injury'),
        ('malfunction', 'Equipment Malfunction'),
        ('theft', 'Missing Equipment'),
        ('other', 'Other'),
    ]

    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='lab_incidents'
    )
    incident_type = models.CharField(max_length=20, choices=INCIDENT_CHOICES)
    incident_date = models.DateField()
    incident_time = models.TimeField(null=True, blank=True)

    equipment = models.ForeignKey(
        LabEquipment, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='incidents'
    )
    involved_student = models.ForeignKey(
        'students.Student', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lab_incidents'
    )
    class_involved = models.CharField(max_length=50, blank=True)

    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='low')
    description = models.TextField()
    action_taken = models.TextField(blank=True)
    reported_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        related_name='lab_incidents_reported'
    )
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-incident_date', '-created_at']

    def __str__(self):
        return f"{self.get_incident_type_display()} — {self.incident_date}"


class PracticalSchedule(models.Model):
    """Scheduled practical session for a class."""
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='practical_schedules'
    )
    title = models.CharField(max_length=200)
    class_level = models.CharField(max_length=50)
    subject = models.CharField(max_length=100, blank=True)
    scheduled_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    equipment_needed = models.TextField(
        blank=True, help_text="List of equipment / chemicals required"
    )
    teacher = models.CharField(max_length=150, blank=True)
    is_completed = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        related_name='practicals_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scheduled_date', 'start_time']

    def __str__(self):
        return f"{self.title} — {self.class_level} ({self.scheduled_date})"