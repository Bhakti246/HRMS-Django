from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True


class Company(TimeStampedModel):
    """A tenant. Business data is always owned by one company."""
    name = models.CharField(max_length=150)
    legal_name = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(max_length=80, unique=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=25, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    industry = models.CharField(max_length=100, blank=True)
    logo = models.ImageField(upload_to="company_logos/", blank=True)
    timezone = models.CharField(max_length=64, default="Asia/Kolkata")
    currency = models.CharField(max_length=3, default="INR")
    date_format = models.CharField(max_length=32, default="d M Y")
    active = models.BooleanField(default=True)
    employee_limit = models.PositiveIntegerField(default=10)
    inactive_employees_consume_seats = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CompanyMembership(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Company owner"
        HR_ADMIN = "hr_admin", "HR admin"
        HR_MANAGER = "hr_manager", "HR manager"
        MANAGER = "manager", "Manager"
        EMPLOYEE = "employee", "Employee"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="company_memberships")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLOYEE)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "company"], name="unique_company_membership")]
        indexes = [models.Index(fields=["company", "role", "active"], name="ems_compmem_comp_role_idx")]

    def __str__(self):
        return f"{self.user} @ {self.company} ({self.get_role_display()})"


class UserAccountProfile(TimeStampedModel):
    """Application-specific account state kept separate from Django auth flags."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="account_profile")
    must_change_password = models.BooleanField(default=False)

    def __str__(self):
        return self.user.get_username()


class Department(TimeStampedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["company", "name"], name="unique_company_department")]
    def __str__(self): return self.name


class Designation(TimeStampedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="designations")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["company", "name"], name="unique_company_designation")]
    def __str__(self): return self.name


class Employee(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
    class Gender(models.TextChoices):
        FEMALE = "female", "Female"
        MALE = "male", "Male"
        OTHER = "other", "Other"
    # An employee account is never valid without its one, canonical login.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="employees")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="employees")
    employee_id = models.CharField(max_length=20)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees")
    designation = models.ForeignKey(Designation, on_delete=models.PROTECT, related_name="employees")
    phone = models.CharField(max_length=25)
    personal_email = models.EmailField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    address = models.TextField(blank=True)
    joining_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    profile_photo = models.ImageField(upload_to="profiles/", blank=True)
    emergency_contact = models.CharField(max_length=25, blank=True)
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=25, blank=True)
    reporting_manager = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="direct_reports")
    employment_type = models.CharField(max_length=30, default="full_time")
    class Meta:
        constraints = [models.UniqueConstraint(fields=["company", "employee_id"], name="unique_company_employee_id")]
        indexes = [models.Index(fields=["company", "status"], name="ems_employe_company_13b5e9_idx")]
    def clean(self):
        super().clean()
        # New records are linked by EmployeeForm before save; the database
        # non-null constraint protects direct model saves. Existing records
        # are explicitly rejected if their link is ever missing.
        if self.pk and not self.user_id:
            raise ValidationError({"user": "Every employee must be linked to exactly one user account."})
    def __str__(self): return f"{self.employee_id} - {self.full_name}"
    @property
    def full_name(self): return self.user.get_full_name() if self.user else self.employee_id


class Attendance(TimeStampedModel):
    class Status(models.TextChoices):
        PRESENT="present", "Present"; ABSENT="absent", "Absent"; HALF_DAY="half", "Half day"; LATE="late", "Late"
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendance")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="attendance")
    date = models.DateField()
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PRESENT)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["employee", "date"], name="unique_employee_attendance")]
        indexes = [models.Index(fields=["company", "date"], name="ems_attenda_company_48fdf5_idx"), models.Index(fields=["company", "employee", "date"], name="ems_attenda_company_e62470_idx")]
        ordering = ["-date"]

    def clean(self):
        super().clean()
        today = timezone.localdate()
        if self.date and self.date > today:
            raise ValidationError({"date": "Attendance cannot be recorded for a future date."})
        if self.check_out and not self.check_in:
            raise ValidationError({"check_out": "Punch in is required before punch out."})
        if self.check_in and self.check_out and self.check_out < self.check_in:
            raise ValidationError({"check_out": "Punch out cannot be earlier than punch in."})

    @property
    def sessions_total(self):
        return sum((session.duration for session in self.sessions.all()), timedelta())

    @property
    def completed_sessions_total(self):
        return sum((session.duration for session in self.sessions.filter(punch_out__isnull=False)), timedelta())

    @property
    def break_total(self):
        sessions = list(self.sessions.order_by("punch_in"))
        return sum((max(timedelta(), later.punch_in - earlier.punch_out) for earlier, later in zip(sessions, sessions[1:]) if earlier.punch_out), timedelta())

    @property
    def first_punch_in(self):
        session = self.sessions.order_by("punch_in").first()
        return session.punch_in if session else None

    @property
    def last_punch_out(self):
        session = self.sessions.filter(punch_out__isnull=False).order_by("-punch_out").first()
        return session.punch_out if session else None


class AttendanceSession(TimeStampedModel):
    """A server-timestamped work interval. One open interval per employee."""
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name="sessions")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendance_sessions")
    punch_in = models.DateTimeField()
    punch_out = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["punch_in"]
        constraints = [models.UniqueConstraint(fields=["employee"], condition=Q(punch_out__isnull=True), name="one_open_session_per_employee")]
        indexes = [models.Index(fields=["attendance", "punch_out"], name="ems_attenda_attenda_68c761_idx")]

    def clean(self):
        super().clean()
        if self.punch_out and self.punch_out < self.punch_in:
            raise ValidationError({"punch_out": "Punch out cannot be earlier than punch in."})

    @property
    def duration(self):
        from django.utils import timezone
        return (self.punch_out or timezone.now()) - self.punch_in


class WorkSchedule(TimeStampedModel):
    """Single configurable attendance/payroll policy, not hard-coded business rules."""
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name="work_schedule")
    expected_daily_hours = models.DecimalField(max_digits=4, decimal_places=2, default=8)
    half_day_hours = models.DecimalField(max_digits=4, decimal_places=2, default=4)
    grace_minutes = models.PositiveIntegerField(default=0)
    attendance_deduction_per_absent_day = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overtime_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    weekly_offs = models.JSONField(default=list)
    salary_calculation_method = models.CharField(max_length=20, default="working_days", choices=[("working_days", "Working days"), ("calendar_days", "Calendar days"), ("fixed_30", "Fixed 30 days")])
    overtime_enabled = models.BooleanField(default=False)

    @classmethod
    def current(cls, company):
        return cls.objects.get_or_create(company=company)[0]


class LeaveRequest(TimeStampedModel):
    class LeaveType(models.TextChoices):
        CASUAL="casual", "Casual"; SICK="sick", "Sick"; PRIVILEGE="privilege", "Privilege"
    class Status(models.TextChoices):
        PENDING="pending", "Pending"; APPROVED="approved", "Approved"; REJECTED="rejected", "Rejected"; CANCELLED="cancelled", "Cancelled"
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_requests")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.CharField(max_length=20, choices=LeaveType.choices)
    start_date = models.DateField(); end_date = models.DateField(); reason = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_leaves")
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="rejected_leaves")
    rejected_at = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    is_paid = models.BooleanField(default=True)
    class Meta:
        indexes = [models.Index(fields=["company", "employee", "status"], name="ems_leavere_company_0d4f90_idx"), models.Index(fields=["company", "start_date", "end_date"], name="ems_leavere_company_1cb1ae_idx")]
    @property
    def days(self): return (self.end_date - self.start_date).days + 1


class Payroll(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT="draft", "Draft"; CALCULATED="calculated", "Calculated"; APPROVED="approved", "Approved"; PAID="paid", "Paid"; CANCELLED="cancelled", "Cancelled"
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="payrolls")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="payrolls")
    pay_period = models.DateField(help_text="First day of the payroll month")
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    hra = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonus = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    payment_date = models.DateField(null=True, blank=True)
    working_days = models.PositiveIntegerField(default=0)
    present_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    absent_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    paid_leave_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    unpaid_leave_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    half_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    required_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    worked_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    overtime_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    overtime_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    attendance_deduction_snapshot = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    leave_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gross_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    salary_snapshot = models.JSONField(default=dict, blank=True)
    calculation_snapshot = models.JSONField(default=dict, blank=True)
    calculated_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["employee", "pay_period"], name="unique_employee_payroll")]
        ordering = ["-pay_period"]
    @property
    def attendance_deduction(self):
        from calendar import monthrange
        start = self.pay_period.replace(day=1)
        end = start.replace(day=monthrange(start.year, start.month)[1])
        absent_days = Attendance.objects.filter(company=self.company, employee=self.employee, date__range=(start, end), status=Attendance.Status.ABSENT).count()
        return self.attendance_deduction_snapshot or absent_days * WorkSchedule.current(self.company).attendance_deduction_per_absent_day

    @property
    def net_salary(self): return self.net_pay or self.basic_salary + self.hra + self.allowances + self.bonus - self.deductions - self.attendance_deduction


class EmployeeSalary(TimeStampedModel):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name="salary_structure")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="salary_structures")
    monthly_gross = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    hra = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    fixed_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    bonus = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    overtime_enabled = models.BooleanField(default=False)
    overtime_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1.5, validators=[MinValueValidator(0)])
    effective_from = models.DateField(default=timezone.localdate)


class CompanyHoliday(TimeStampedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="holidays")
    date = models.DateField()
    name = models.CharField(max_length=150)
    paid = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["company", "date"], name="unique_company_holiday")]


class Job(TimeStampedModel):
    class Stage(models.TextChoices):
        SCREENING="screening", "Screening"; OFFER="offer", "Offer"; CLOSED="closed", "Closed"
    title = models.CharField(max_length=150)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="jobs")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="jobs")
    openings = models.PositiveIntegerField(default=1)
    applicants = models.PositiveIntegerField(default=0)
    stage = models.CharField(max_length=15, choices=Stage.choices, default=Stage.SCREENING)


class PerformanceReview(TimeStampedModel):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="reviews")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="performance_reviews")
    review_date = models.DateField()
    score = models.DecimalField(max_digits=3, decimal_places=1, validators=[MinValueValidator(0)])
    notes = models.TextField(blank=True)
    class Meta: ordering = ["-review_date"]


class CompanySetting(TimeStampedModel):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name="settings")
    name = models.CharField(max_length=150, default="Acme Pvt Ltd")
    timezone = models.CharField(max_length=100, default="IST (UTC+5:30)")


class AuditLog(models.Model):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="audit_logs")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_events")
    action = models.CharField(max_length=80)
    object_type = models.CharField(max_length=100)
    object_id = models.CharField(max_length=64, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["company", "timestamp"], name="ems_auditlo_company_b1eeae_idx"), models.Index(fields=["object_type", "object_id"], name="ems_auditlo_object__d9a224_idx")]
