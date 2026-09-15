from django import forms
from django.contrib.auth.models import User
from pathlib import Path
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.text import slugify
from django.contrib.auth.password_validation import validate_password
from PIL import Image, UnidentifiedImageError
from .models import Attendance, CompanyMembership, CompanySetting, Department, Designation, Employee, EmployeeSalary, Job, LeaveRequest, Payroll, PerformanceReview, UserAccountProfile, WorkSchedule


class CompanySetupForm(forms.Form):
    company_name = forms.CharField(max_length=150, label="Company name")
    logo = forms.ImageField(required=False, label="Company logo")
    company_email = forms.EmailField(label="Company email")
    phone = forms.CharField(max_length=25)
    address = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    city = forms.CharField(max_length=100)
    state = forms.CharField(max_length=100)
    country = forms.CharField(max_length=100)
    pincode = forms.CharField(max_length=20)
    website = forms.URLField(required=False)
    industry = forms.CharField(max_length=100)
    timezone = forms.ChoiceField(choices=[("Asia/Kolkata", "India Standard Time (Asia/Kolkata)"), ("UTC", "UTC"), ("Asia/Dubai", "Gulf Standard Time"), ("Europe/London", "United Kingdom"), ("America/New_York", "US Eastern")])
    owner_name = forms.CharField(max_length=150, label="Owner / admin name")
    admin_email = forms.EmailField(label="Owner email")
    admin_username = forms.CharField(max_length=150, label="Owner username")
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirm password")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"

    def clean_admin_email(self):
        email = self.cleaned_data["admin_email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists. Please sign in instead.")
        return email

    def clean(self):
        data = super().clean()
        if data.get("password") != data.get("confirm_password"):
            self.add_error("confirm_password", "Passwords do not match.")
        if data.get("password"):
            validate_password(data["password"])
        username = (data.get("admin_username") or "").strip()
        if username and User.objects.filter(username__iexact=username).exists():
            self.add_error("admin_username", "This username is already in use.")
        return data

class StyledForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        kwargs.pop("company", None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values(): field.widget.attrs["class"] = "input"

class EmployeeForm(StyledForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(label="Login email")
    username = forms.CharField(max_length=150, required=False)
    temporary_password = forms.CharField(widget=forms.PasswordInput, required=False)
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=False)
    role = forms.ChoiceField(choices=[
        (CompanyMembership.Role.EMPLOYEE, "Employee"),
        (CompanyMembership.Role.MANAGER, "Manager"),
        (CompanyMembership.Role.HR_MANAGER, "HR manager"),
        (CompanyMembership.Role.HR_ADMIN, "HR admin"),
    ], required=False, initial=CompanyMembership.Role.EMPLOYEE)
    class Meta:
        model = Employee
        exclude = ("user", "company", "created_at", "updated_at")
        widgets = {"joining_date": forms.DateInput(attrs={"type":"date"}), "date_of_birth": forms.DateInput(attrs={"type":"date"}), "address": forms.Textarea(attrs={"rows":3})}
    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop("company", None)
        super().__init__(*args, **kwargs)
        if self.company:
            self.fields["department"].queryset = Department.objects.filter(company=self.company, active=True)
            self.fields["designation"].queryset = Designation.objects.filter(company=self.company, active=True)
            self.fields["reporting_manager"].queryset = Employee.objects.filter(company=self.company, status=Employee.Status.ACTIVE)
        if self.instance and self.instance.pk and self.instance.user_id:
            user = self.instance.user
            self.fields["first_name"].initial = user.first_name; self.fields["last_name"].initial = user.last_name; self.fields["email"].initial = user.email; self.fields["username"].initial = user.username
            membership = CompanyMembership.objects.filter(user=user, company=self.company).first()
            if membership:
                self.fields["role"].initial = membership.role
            self.fields["username"].required = True
            self.fields["temporary_password"].label = "New password (optional)"
            self.fields["confirm_password"].label = "Confirm new password"
        else:
            self.fields["username"].required = True
            self.fields["temporary_password"].required = True
            self.fields["confirm_password"].required = True
    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        current_user_id = self.instance.user_id if self.instance and self.instance.pk else None
        if User.objects.exclude(pk=current_user_id).filter(email__iexact=email).exists():
            raise ValidationError("This login email is already in use.")
        return email
    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        current_user_id = self.instance.user_id if self.instance and self.instance.pk else None
        if User.objects.exclude(pk=current_user_id).filter(username__iexact=username).exists():
            raise ValidationError("This username is already in use.")
        return username
    def clean(self):
        data = super().clean()
        password = data.get("temporary_password")
        confirmation = data.get("confirm_password")
        if not self.instance.pk and password != confirmation:
            self.add_error("confirm_password", "Passwords do not match.")
        if self.instance.pk and password and password != confirmation:
            self.add_error("confirm_password", "Passwords do not match.")
        if password:
            from django.contrib.auth.password_validation import validate_password
            validate_password(password, self.instance.user if self.instance and self.instance.user_id else None)
        return data
    def clean_profile_photo(self):
        photo = self.cleaned_data.get("profile_photo")
        if not photo:
            return photo
        max_size = 2 * 1024 * 1024
        if photo.size > max_size:
            raise ValidationError("Profile photo must be 2MB or smaller.")
        extension = Path(photo.name).suffix.lower()
        if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise ValidationError("Profile photo must be a JPG, PNG, or WebP image.")
        content_type = getattr(photo, "content_type", "")
        if content_type and content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValidationError("Uploaded file is not a supported image type.")
        try:
            photo.seek(0)
            with Image.open(photo) as image:
                image.verify()
            photo.seek(0)
        except (UnidentifiedImageError, OSError):
            raise ValidationError("The uploaded file is not a valid image.")
        return photo
    def save(self, commit=True):
        obj = super().save(commit=False)
        password = self.cleaned_data.get("temporary_password")
        if obj.user_id:
            user = obj.user
            user.username = self.cleaned_data["username"]
            user.email = self.cleaned_data["email"]
            user.first_name = self.cleaned_data["first_name"]
            user.last_name = self.cleaned_data.get("last_name", "")
            if password:
                user.set_password(password)
                UserAccountProfile.objects.update_or_create(user=user, defaults={"must_change_password": True})
            user.save()
        else:
            user = User.objects.create_user(
                username=self.cleaned_data["username"], email=self.cleaned_data["email"],
                password=password, first_name=self.cleaned_data["first_name"],
                last_name=self.cleaned_data.get("last_name", ""),
            )
            UserAccountProfile.objects.create(user=user, must_change_password=True)
        obj.user = user
        if commit: obj.save(); self.save_m2m()
        return obj


class PasswordChangeForm(forms.Form):
    new_password = forms.CharField(widget=forms.PasswordInput, label="New password")
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirm new password")

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"

    def clean(self):
        data = super().clean()
        if data.get("new_password") != data.get("confirm_password"):
            self.add_error("confirm_password", "Passwords do not match.")
        if data.get("new_password"):
            from django.contrib.auth.password_validation import validate_password
            validate_password(data["new_password"], self.user)
        return data

class DepartmentForm(StyledForm):
    class Meta: model=Department; fields=("name","description","active"); widgets={"description":forms.Textarea(attrs={"rows":3})}
class DesignationForm(StyledForm):
    class Meta: model=Designation; fields=("name","description","active"); widgets={"description":forms.Textarea(attrs={"rows":3})}
class AttendanceForm(StyledForm):
    employee_number = forms.CharField(max_length=20, label="Employee number")
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), label="Date of birth")
    class Meta:
        model = Attendance
        fields = ("employee_number", "date_of_birth", "date", "check_in", "check_out", "status")
        widgets = {"date": forms.DateInput(attrs={"type":"date"}), "check_in": forms.TimeInput(attrs={"type":"time"}), "check_out": forms.TimeInput(attrs={"type":"time"})}

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop("company", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        employee_number = (data.get("employee_number") or "").strip().upper()
        employee = Employee.objects.filter(employee_id__iexact=employee_number, **({"company": self.company} if self.company else {})).first()
        if employee and not employee.date_of_birth:
            raise ValidationError(
                "Employee {} does not have a date of birth recorded. Update that employee profile before marking attendance.".format(employee.employee_id)
            )
        if employee and employee.date_of_birth != data.get("date_of_birth"):
            employee = None
        if not employee:
            raise ValidationError("Employee number and date of birth do not match an employee record.")
        if employee.status != Employee.Status.ACTIVE:
            raise ValidationError("Inactive employees cannot receive attendance.")
        if data.get("date") and data["date"] > timezone.localdate():
            self.add_error("date", "Attendance cannot be recorded for a future date.")
        if employee and data.get("date") and Attendance.objects.filter(employee=employee, date=data["date"]).exclude(pk=self.instance.pk).exists():
            self.add_error("date", "Attendance already exists for this employee and date.")
        self.employee = employee
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.employee = self.employee
        for field in ("date", "check_in", "check_out", "status"):
            setattr(obj, field, self.cleaned_data.get(field))
        if commit:
            obj.full_clean()
            obj.save()
        return obj
class LeaveForm(StyledForm):
    class Meta: model=LeaveRequest; fields=("leave_type","start_date","end_date","reason"); widgets={"start_date":forms.DateInput(attrs={"type":"date"}),"end_date":forms.DateInput(attrs={"type":"date"}),"reason":forms.Textarea(attrs={"rows":3})}
    def clean(self):
        data=super().clean()
        if data.get("start_date") and data.get("end_date") and data["end_date"] < data["start_date"]: self.add_error("end_date", "End date cannot be before start date.")
        return data
class PayrollForm(StyledForm):
    class Meta: model=Payroll; fields=("employee","pay_period","basic_salary","hra","allowances","deductions","bonus","status","payment_date"); widgets={"pay_period":forms.DateInput(attrs={"type":"date"}),"payment_date":forms.DateInput(attrs={"type":"date"})}
    def __init__(self, *args, **kwargs):
        company = kwargs.pop("company", None)
        super().__init__(*args, **kwargs)
        if company: self.fields["employee"].queryset = Employee.objects.filter(company=company, status=Employee.Status.ACTIVE)


class PayrollPreviewForm(forms.Form):
    employee = forms.ModelChoiceField(queryset=Employee.objects.none(), label="Employee")
    pay_period = forms.DateField(input_formats=["%Y-%m", "%Y-%m-%d"], widget=forms.DateInput(attrs={"type": "month"}), label="Payroll month")

    def __init__(self, *args, **kwargs):
        company = kwargs.pop("company", None)
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = Employee.objects.filter(company=company, status=Employee.Status.ACTIVE) if company else Employee.objects.none()

    def clean_pay_period(self):
        value = self.cleaned_data["pay_period"]
        return value.replace(day=1)
class JobForm(StyledForm):
    class Meta: model=Job; fields=("title","department","openings","applicants","stage")
    def __init__(self, *args, **kwargs):
        company = kwargs.pop("company", None)
        super().__init__(*args, **kwargs)
        if company: self.fields["department"].queryset = Department.objects.filter(company=company, active=True)
class PerformanceForm(StyledForm):
    class Meta: model=PerformanceReview; fields=("employee","review_date","score","notes"); widgets={"review_date":forms.DateInput(attrs={"type":"date"}),"notes":forms.Textarea(attrs={"rows":3})}
    def __init__(self, *args, **kwargs):
        company = kwargs.pop("company", None)
        super().__init__(*args, **kwargs)
        if company: self.fields["employee"].queryset = Employee.objects.filter(company=company, status=Employee.Status.ACTIVE)
class SettingForm(StyledForm):
    class Meta: model=CompanySetting; fields=("name","timezone")

class WorkScheduleForm(StyledForm):
    class Meta:
        model = WorkSchedule
        fields = ("expected_daily_hours", "half_day_hours", "grace_minutes", "attendance_deduction_per_absent_day", "overtime_multiplier", "weekly_offs", "salary_calculation_method", "overtime_enabled")


class EmployeeSalaryForm(StyledForm):
    class Meta:
        model = EmployeeSalary
        fields = ("monthly_gross", "basic_salary", "hra", "allowances", "fixed_deductions", "bonus", "overtime_enabled", "overtime_multiplier", "effective_from")
        widgets = {"effective_from": forms.DateInput(attrs={"type": "date"})}
