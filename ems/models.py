from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True


class Department(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    def __str__(self): return self.name


class Designation(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
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
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="employee")
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees")
    designation = models.ForeignKey(Designation, on_delete=models.PROTECT, related_name="employees")
    phone = models.CharField(max_length=25)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    address = models.TextField(blank=True)
    joining_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    profile_photo = models.ImageField(upload_to="profiles/", blank=True)
    emergency_contact = models.CharField(max_length=25, blank=True)
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
    date = models.DateField()
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PRESENT)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["employee", "date"], name="unique_employee_attendance")]
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
    punch_in = models.DateTimeField()
    punch_out = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["punch_in"]
        constraints = [models.UniqueConstraint(fields=["attendance"], name="one_session_per_attendance")]

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
    expected_daily_hours = models.DecimalField(max_digits=4, decimal_places=2, default=8)
    half_day_hours = models.DecimalField(max_digits=4, decimal_places=2, default=4)
    grace_minutes = models.PositiveIntegerField(default=0)
    attendance_deduction_per_absent_day = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overtime_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=0)

    @classmethod
    def current(cls):
        return cls.objects.first() or cls.objects.create()


class LeaveRequest(TimeStampedModel):
    class LeaveType(models.TextChoices):
        CASUAL="casual", "Casual"; SICK="sick", "Sick"; PRIVILEGE="privilege", "Privilege"
    class Status(models.TextChoices):
        PENDING="pending", "Pending"; APPROVED="approved", "Approved"; REJECTED="rejected", "Rejected"; CANCELLED="cancelled", "Cancelled"
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.CharField(max_length=20, choices=LeaveType.choices)
    start_date = models.DateField(); end_date = models.DateField(); reason = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_leaves")
    approved_at = models.DateTimeField(null=True, blank=True)
    @property
    def days(self): return (self.end_date - self.start_date).days + 1


class Payroll(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT="draft", "Draft"; PAID="paid", "Paid"
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="payrolls")
    pay_period = models.DateField(help_text="First day of the payroll month")
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    hra = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonus = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    payment_date = models.DateField(null=True, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["employee", "pay_period"], name="unique_employee_payroll")]
        ordering = ["-pay_period"]
    @property
    def attendance_deduction(self):
        from calendar import monthrange
        start = self.pay_period.replace(day=1)
        end = start.replace(day=monthrange(start.year, start.month)[1])
        absent_days = Attendance.objects.filter(employee=self.employee, date__range=(start, end), status=Attendance.Status.ABSENT).count()
        return absent_days * WorkSchedule.current().attendance_deduction_per_absent_day

    @property
    def net_salary(self): return self.basic_salary + self.hra + self.allowances + self.bonus - self.deductions - self.attendance_deduction


class Job(TimeStampedModel):
    class Stage(models.TextChoices):
        SCREENING="screening", "Screening"; OFFER="offer", "Offer"; CLOSED="closed", "Closed"
    title = models.CharField(max_length=150)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="jobs")
    openings = models.PositiveIntegerField(default=1)
    applicants = models.PositiveIntegerField(default=0)
    stage = models.CharField(max_length=15, choices=Stage.choices, default=Stage.SCREENING)


class PerformanceReview(TimeStampedModel):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="reviews")
    review_date = models.DateField()
    score = models.DecimalField(max_digits=3, decimal_places=1, validators=[MinValueValidator(0)])
    notes = models.TextField(blank=True)
    class Meta: ordering = ["-review_date"]


class CompanySetting(TimeStampedModel):
    name = models.CharField(max_length=150, default="Acme Pvt Ltd")
    timezone = models.CharField(max_length=100, default="IST (UTC+5:30)")
