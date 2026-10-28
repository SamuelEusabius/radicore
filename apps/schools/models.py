from django.db import models
from django.utils.text import slugify
from apps.schools.managers import TenantManager



# ==========================================================
# SUBSCRIPTION PLAN
# ==========================================================

class SubscriptionPlan(models.Model):
    """A subscription tier based on school size."""
    name = models.CharField(max_length=50, unique=True)
    code = models.SlugField(max_length=30, unique=True, blank=True, null=True)

    # Student range this plan is for
    min_students = models.PositiveIntegerField(default=0)
    max_students = models.PositiveIntegerField(default=500)

    # Teacher limits
    max_teachers = models.PositiveIntegerField(default=30)

    # Pricing (KES) — all four cycles
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    term_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    contract_1y_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    contract_2y_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    features = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order")

    class Meta:
        ordering = ['order', 'min_students']

    def __str__(self):
        return f"{self.name} ({self.min_students}-{self.max_students} students)"

    def matches_student_count(self, count):
        return self.min_students <= count <= self.max_students
    @property
    def feature_list(self):
        """Return features as a clean list, handling str / list / JSON."""
        f = self.features
        if isinstance(f, list):
            return [str(x).strip() for x in f if str(x).strip()]
        if not f:
            return []
        s = str(f).strip()
        if s.startswith('[') and s.endswith(']'):
            try:
                import ast
                parsed = ast.literal_eval(s)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except (ValueError, SyntaxError):
                pass
        if '\n' in s:
            return [line.strip() for line in s.split('\n') if line.strip()]
        if ',' in s:
            return [part.strip() for part in s.split(',') if part.strip()]
        return [s]

    def price_for_cycle(self, cycle):
        return {
            'monthly': self.monthly_price,
            'term': self.term_price,
            'contract_1y': self.contract_1y_price,
            'contract_2y': self.contract_2y_price,
        }.get(cycle, self.monthly_price)
    

# ==========================================================
# SCHOOL
# ==========================================================

class School(models.Model):
    class SchoolType(models.TextChoices):
        PUBLIC  = 'public',  'Public'
        PRIVATE = 'private', 'Private'

    class Gender(models.TextChoices):
        BOYS   = 'boys',   'Boys Only'
        GIRLS  = 'girls',  'Girls Only'
        MIXED  = 'mixed',  'Mixed'

    class Level(models.TextChoices):
        PRIMARY      = 'primary',       'Primary (CBC 1-6)'
        JSS          = 'jss',           'Junior Secondary (7-9)'
        SENIOR       = 'senior',        'Senior School (10-12)'
        PRIMARY_JSS  = 'primary_jss',   'Primary + Junior Secondary'
        ALL          = 'all',           'Full School (1-12)'

    # ============ BASIC INFO ============
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True, null=True)
    code = models.CharField(
        max_length=20, unique=True, blank=True, null=True,
        help_text="Auto-generated school code (e.g. SCH0001)"
    )
    logo = models.ImageField(upload_to='school_logos/', blank=True, null=True)
    motto = models.CharField(max_length=200, blank=True, default='')

    # ============ CLASSIFICATION ============
    school_type = models.CharField(
        max_length=10, choices=SchoolType.choices, default=SchoolType.PRIVATE
    )
    gender = models.CharField(
        max_length=10, choices=Gender.choices, default=Gender.MIXED
    )
    level = models.CharField(
        max_length=20, choices=Level.choices, default=Level.ALL
    )

    # ============ KENYA-SPECIFIC ============
    nemis_code = models.CharField(
        max_length=30, blank=True, default='', help_text="NEMIS School Code"
    )
    county = models.CharField(max_length=50, blank=True, default='')
    sub_county = models.CharField(max_length=50, blank=True, default='')
    ward = models.CharField(max_length=50, blank=True, default='')
    physical_address = models.CharField(max_length=200, blank=True, default='')

    # ============ CONTACT ============
    email = models.EmailField(blank=True, default='')
    phone = models.CharField(max_length=20, blank=True, default='')
    postal_address = models.CharField(max_length=100, blank=True, default='')

    # ============ LEADERSHIP ============
    principal_name = models.CharField(max_length=100, blank=True, default='')
    principal_id = models.CharField(max_length=20, blank=True, default='', help_text="National ID")
    principal_phone = models.CharField(max_length=20, blank=True, default='')
    principal_email = models.EmailField(blank=True, default='')
    principal_photo = models.ImageField(upload_to='school_leadership/', blank=True, null=True)

    deputy_name = models.CharField(max_length=100, blank=True, default='')
    deputy_id = models.CharField(max_length=20, blank=True, default='')
    deputy_phone = models.CharField(max_length=20, blank=True, default='')
    deputy_email = models.EmailField(blank=True, default='')
    deputy_photo = models.ImageField(upload_to='school_leadership/', blank=True, null=True)

    senior_teacher_name = models.CharField(max_length=100, blank=True, default='')
    senior_teacher_id = models.CharField(max_length=20, blank=True, default='')
    senior_teacher_phone = models.CharField(max_length=20, blank=True, default='')
    senior_teacher_email = models.EmailField(blank=True, default='')
    senior_teacher_photo = models.ImageField(upload_to='school_leadership/', blank=True, null=True)

    accountant_name = models.CharField(max_length=100, blank=True, default='')
    accountant_id = models.CharField(max_length=20, blank=True, default='')
    accountant_phone = models.CharField(max_length=20, blank=True, default='')
    accountant_email = models.EmailField(blank=True, default='')
    accountant_photo = models.ImageField(upload_to='school_leadership/', blank=True, null=True)

    # ============ SUBSCRIPTION ============
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT, null=True, blank=True
    )
    is_active = models.BooleanField(
        default=True, help_text="Deactivated schools cannot be accessed"
    )
    subscription_paid_until = models.DateField(
    null=True, blank=True,
    help_text="DEPRECATED — use SchoolSubscription.paid_until instead"
)

    blocked_message = models.TextField(
        blank=True,
        default='Your school subscription has expired. Please contact the school administration or renew your subscription to continue using the system.',
        help_text="Shown to school users when account is deactivated"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.code:
            # Count how many schools exist and generate the next code
            last_school = School.objects.all().order_by('id').last()
            if not last_school:
                self.code = 'SCH001'
            else:
                # Extract the number from the last code (e.g., SCH001 -> 1)
                import re
                match = re.search(r'\d+', last_school.code)
                if match:
                    next_num = int(match.group()) + 1
                    self.code = f"SCH{next_num:03d}"
                else:
                    self.code = f"SCH{School.objects.count() + 1:03d}"
        super().save(*args, **kwargs)

    # ============ HELPER PROPERTIES ============
    @property
    def is_public(self):
        return self.school_type == self.SchoolType.PUBLIC

    @property
    def is_boys_only(self):
        return self.gender == self.Gender.BOYS

    @property
    def is_girls_only(self):
        return self.gender == self.Gender.GIRLS

    @property
    def is_mixed(self):
        return self.gender == self.Gender.MIXED

    @property
    def status_label(self):
        return 'Active' if self.is_active else 'Inactive'

    @property
    def initials(self):
        parts = (self.name or 'SM').split()
        return ''.join(p[0] for p in parts[:2]).upper() or 'SM'

    @property
    def is_subscription_active(self):
        """
        Source of truth for 'can this school use the system'.
        Reads SchoolSubscription, never School.subscription_paid_until.
        """
        sub = getattr(self, 'subscription', None)
        return bool(sub and sub.is_valid)

    @property
    def subscription_status_label(self):
        sub = getattr(self, 'subscription', None)
        return sub.get_status_display() if sub else 'No subscription'
# ==========================================================
# BOARD MEMBER
# ==========================================================

class BoardMember(models.Model):
    class Role(models.TextChoices):
        CHAIRPERSON = 'chairperson', 'Chairperson'
        SECRETARY   = 'secretary',   'Secretary'
        TREASURER   = 'treasurer',   'Treasurer'
        MEMBER      = 'member',      'Member'
        PARENT_REP  = 'parent_rep',  'Parents Representative'

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name='board_members'
    )
    full_name = models.CharField(max_length=100)
    id_number = models.CharField(max_length=20, help_text="National ID")
    occupation = models.CharField(max_length=100, blank=True, default='')
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.MEMBER
    )
    phone = models.CharField(max_length=20, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    photo = models.ImageField(upload_to='board_members/', blank=True, null=True)
    appointed_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['role', 'full_name']

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()}) — {self.school.name}"


# ==========================================================
# SCHOOL SUBSCRIPTION
# ==========================================================

class SchoolSubscription(models.Model):
    """Tracks the subscription of a school with billing cycle support."""

    class Status(models.TextChoices):
        TRIAL            = 'trial',            'Free Trial'
        PENDING_PAYMENT  = 'pending_payment',  'Pending Payment'
        ACTIVE           = 'active',           'Active'
        EXPIRED          = 'expired',          'Expired'
        CANCELLED        = 'cancelled',        'Cancelled'

    class PaymentMethod(models.TextChoices):
        MPESA = 'mpesa', 'M-Pesa'
        BANK  = 'bank',  'Bank Transfer'
        CASH  = 'cash',  'Cash'

    class BillingCycle(models.TextChoices):
        MONTHLY  = 'monthly',  'Monthly'
        TERM     = 'term',     'Per Term (3 Months)'
        CONTRACT = 'contract', 'Contract'

    school = models.OneToOneField(
        School, on_delete=models.CASCADE, related_name='subscription'
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.TRIAL
    )

    # ---------- Billing ----------
    billing_cycle = models.CharField(
        max_length=20, choices=BillingCycle.choices, default=BillingCycle.TERM
    )
    contract_years = models.PositiveIntegerField(
        default=0, help_text="Only for CONTRACT billing"
    )
    total_paid_kes = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )

    # ---------- Trial ----------
    trial_started_at = models.DateTimeField(auto_now_add=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)

    # ---------- Paid ----------
    paid_until = models.DateTimeField(null=True, blank=True)
    last_payment_date = models.DateTimeField(null=True, blank=True)
    last_payment_method = models.CharField(
        max_length=10, choices=PaymentMethod.choices, blank=True, default=''
    )
    last_payment_reference = models.CharField(max_length=100, blank=True, default='')

    # ---------- Payment Confirmation ----------
    payment_confirmed_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='confirmed_payments'
    )
    payment_confirmed_at = models.DateTimeField(null=True, blank=True)
    payment_notes = models.TextField(blank=True, default='')

    # ---------- Limits ----------
    max_students = models.PositiveIntegerField(default=450)
    max_teachers = models.PositiveIntegerField(default=50)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.school.name} — {self.get_status_display()}"

    # ==========================================================
    # HELPERS
    # ==========================================================

    @property
    def is_valid(self):
        from django.utils import timezone
        now = timezone.now()
        if self.status == self.Status.TRIAL and self.trial_ends_at:
            return now < self.trial_ends_at
        if self.status == self.Status.ACTIVE and self.paid_until:
            return now < self.paid_until
        return False

    @property
    def days_remaining(self):
        from django.utils import timezone
        now = timezone.now()
        target = (
            self.trial_ends_at
            if self.status == self.Status.TRIAL
            else self.paid_until
        )
        if not target:
            return 0
        return max(0, (target - now).days)

    @property
    def billing_cycle_display(self):
        if self.billing_cycle == self.BillingCycle.CONTRACT and self.contract_years:
            years = self.contract_years
            suffix = 's' if years > 1 else ''
            return f"Contract ({years} year{suffix})"
        return self.get_billing_cycle_display()

    @property
    def status_badge_class(self):
        return {
            'trial':           'pro-badge-info',
            'pending_payment': 'pro-badge-warning',
            'active':          'pro-badge-success',
            'expired':         'pro-badge-danger',
            'cancelled':       'pro-badge-gray',
        }.get(self.status, 'pro-badge-gray')

    # ==========================================================
    # PRICE CALCULATION
    # ==========================================================

    @staticmethod
    def calculate_price(plan, billing_cycle, contract_years=1):
        """
        Calculate total price + duration days for a billing cycle.
        Delegates to SubscriptionPlan.price_for_cycle().

        Returns: (total_price, duration_days)
        """
        if not plan:
            return 0, 0
        if billing_cycle == 'contract':
            years = max(int(contract_years or 1), 1)
            unit = plan.contract_2y_price if years >= 2 else plan.contract_1y_price
            return float(unit) * years, 365 * years
        if billing_cycle == 'monthly':
            return float(plan.monthly_price), 30
        return float(plan.term_price), 90

    # ==========================================================
    # HELPERS
    # ==========================================================

    @property
    def is_valid(self):
        from django.utils import timezone
        now = timezone.now()
        if self.status == self.Status.TRIAL and self.trial_ends_at:
            return now < self.trial_ends_at
        if self.status == self.Status.ACTIVE and self.paid_until:
            return now < self.paid_until
        return False

    @property
    def days_remaining(self):
        from django.utils import timezone
        now = timezone.now()
        target = (
            self.trial_ends_at
            if self.status == self.Status.TRIAL
            else self.paid_until
        )
        if not target:
            return 0
        return max(0, (target - now).days)

    @property
    def billing_cycle_display(self):
        if self.billing_cycle == self.BillingCycle.CONTRACT and self.contract_years:
            years = self.contract_years
            suffix = 's' if years > 1 else ''
            return f"Contract ({years} year{suffix})"
        return self.get_billing_cycle_display()

    @property
    def status_badge_class(self):
        return {
            'trial':           'pro-badge-info',
            'pending_payment': 'pro-badge-warning',
            'active':          'pro-badge-success',
            'expired':         'pro-badge-danger',
            'cancelled':       'pro-badge-gray',
        }.get(self.status, 'pro-badge-gray')

    # ==========================================================
    # PRICE CALCULATION
    # ==========================================================

    @staticmethod
    def calculate_price(plan, billing_cycle, contract_years=1):
        """
        Calculate total price + duration days for a billing cycle.
        Delegates to SubscriptionPlan.price_for_cycle().

        Returns: (total_price, duration_days)
        """
        if not plan:
            return 0, 0
        if billing_cycle == 'contract':
            years = max(int(contract_years or 1), 1)
            unit = plan.contract_2y_price if years >= 2 else plan.contract_1y_price
            return float(unit) * years, 365 * years
        if billing_cycle == 'monthly':
            return float(plan.monthly_price), 30
        return float(plan.term_price), 90


# ==========================================================
# MODULAR FEATURE TOGGLES
# ==========================================================

class SchoolModule(models.Model):
    """
    Tracks which modules are enabled for each school.
    One row per (school, module) pair.

    Modules are toggled by Super Admins. Plan-based defaults are
    applied at school creation; Super Admin can override per school.
    """

    class Module(models.TextChoices):
        LIBRARY        = 'library',        'Library Management'
        TRANSPORT      = 'transport',      'Transport & Routes'
        HOSTEL         = 'hostel',         'Hostel / Dormitory'
        WALLET         = 'wallet',         'Student Wallet'
        CAFETERIA      = 'cafeteria',      'Cafeteria'
        SMS            = 'sms',            'SMS Notifications'
        MPESA          = 'mpesa',          'M-Pesa Payments'
        ANALYTICS      = 'analytics',      'Advanced Analytics'
        PARENT_PORTAL  = 'parent_portal',  'Parent Portal'
        REPORTS        = 'reports',        'Custom Reports'

    # Modules enabled by default for NEW schools
    DEFAULT_ENABLED = {
        Module.SMS,
        Module.MPESA,
        Module.PARENT_PORTAL,
    }

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name='modules'
    )
    module = models.CharField(max_length=30, choices=Module.choices)

    is_enabled = models.BooleanField(default=False)

    # ----- Audit trail -----
    enabled_at = models.DateTimeField(null=True, blank=True)
    enabled_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='modules_enabled',
    )
    disabled_at = models.DateTimeField(null=True, blank=True)
    disabled_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='modules_disabled',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = TenantManager()

    class Meta:
        unique_together = ('school', 'module')
        ordering = ['school', 'module']
        indexes = [
            models.Index(fields=['school', 'module', 'is_enabled']),
        ]

    def __str__(self):
        status = 'ON' if self.is_enabled else 'OFF'
        return f"{self.school.name} · {self.get_module_display()} [{status}]"


# ==========================================================
# HELPER FUNCTION
# ==========================================================

def school_has_module(school, module_code):
    """
    Check if a school has a module enabled.

    Usage:
        from apps.schools.models import school_has_module
        if school_has_module(school, 'library'):
            ...

    Returns False if school is None or module doesn't exist.
    """
    if not school:
        return False
    return SchoolModule.objects.filter(
        school=school,
        module=module_code,
        is_enabled=True,
    ).exists()
