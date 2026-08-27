from django import forms
from django.contrib.auth.models import User
from pathlib import Path
from django.core.exceptions import ValidationError
from django.utils import timezone
from PIL import Image, UnidentifiedImageError
import secrets
from .models import Attendance, CompanySetting, Department, Designation, Employee, Job, LeaveRequest, Payroll, PerformanceReview, WorkSchedule

class StyledForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values(): field.widget.attrs["class"] = "input"

class EmployeeForm(StyledForm):
    first_name = forms.CharField(max_length=150); last_name = forms.CharField(max_length=150); email = forms.EmailField()
    class Meta:
        model = Employee
        exclude = ("user", "created_at", "updated_at")
        widgets = {"joining_date": forms.DateInput(attrs={"type":"date"}), "date_of_birth": forms.DateInput(attrs={"type":"date"}), "address": forms.Textarea(attrs={"rows":3})}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.user_id:
            user = self.instance.user
            self.fields["first_name"].initial = user.first_name; self.fields["last_name"].initial = user.last_name; self.fields["email"].initial = user.email
    def clean_email(self):
        email = self.cleaned_data["email"]
        current_user_id = self.instance.user_id if self.instance and self.instance.pk else None
        if User.objects.exclude(pk=current_user_id).filter(username=email).exists(): raise ValidationError("A user with this email already exists.")
        return email
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
        obj = super().save(commit=False); email = self.cleaned_data["email"]
        user = obj.user if obj.user_id else User(username=email)
        user.username=email; user.email=email; user.first_name=self.cleaned_data["first_name"]; user.last_name=self.cleaned_data["last_name"]
        if not user.pk:
            # A shared default password would let anyone who knows the demo
            # convention access every newly-created employee account.
            self.generated_password = secrets.token_urlsafe(16)
            user.set_password(self.generated_password)
        user.save(); obj.user=user
        if commit: obj.save(); self.save_m2m()
        return obj

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

    def clean(self):
        data = super().clean()
        employee_number = (data.get("employee_number") or "").strip().upper()
        employee = Employee.objects.filter(employee_id__iexact=employee_number).first()
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
class JobForm(StyledForm):
    class Meta: model=Job; fields=("title","department","openings","applicants","stage")
class PerformanceForm(StyledForm):
    class Meta: model=PerformanceReview; fields=("employee","review_date","score","notes"); widgets={"review_date":forms.DateInput(attrs={"type":"date"}),"notes":forms.Textarea(attrs={"rows":3})}
class SettingForm(StyledForm):
    class Meta: model=CompanySetting; fields=("name","timezone")

class WorkScheduleForm(StyledForm):
    class Meta:
        model = WorkSchedule
        fields = ("expected_daily_hours", "half_day_hours", "grace_minutes", "attendance_deduction_per_absent_day", "overtime_multiplier")
