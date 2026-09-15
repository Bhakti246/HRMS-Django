import csv
from datetime import date, timedelta
from functools import wraps
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.contrib.auth.models import User
from .forms import AttendanceForm, CompanySetupForm, DepartmentForm, DesignationForm, EmployeeForm, JobForm, LeaveForm, PasswordChangeForm, PayrollForm, PerformanceForm, SettingForm, WorkScheduleForm
from .models import Attendance, AttendanceSession, AuditLog, Company, CompanyMembership, CompanySetting, Department, Designation, Employee, Job, LeaveRequest, Payroll, PerformanceReview, UserAccountProfile, WorkSchedule

MANAGEMENT_ROLES = {CompanyMembership.Role.OWNER, CompanyMembership.Role.HR_ADMIN, CompanyMembership.Role.HR_MANAGER}

def current_company(request):
    memberships = CompanyMembership.objects.filter(user=request.user, active=True, company__active=True).select_related("company")
    selected = request.session.get("active_company_id")
    membership = memberships.filter(company_id=selected).first() if selected else memberships.first()
    if membership and not selected:
        request.session["active_company_id"] = membership.company_id
    request.membership = membership
    return membership.company if membership else None

def is_admin(user, company=None):
    memberships = CompanyMembership.objects.filter(user=user, active=True)
    if company:
        memberships = memberships.filter(company=company)
    return user.is_authenticated and memberships.filter(role__in=MANAGEMENT_ROLES).exists()

def company_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapped(request, *args, **kwargs):
        request.company = current_company(request)
        if not request.company:
            return render(request, "403.html", status=403)
        account_profile = UserAccountProfile.objects.filter(user=request.user).first()
        if account_profile and account_profile.must_change_password and request.resolver_match.url_name != "password_change":
            return redirect("ems:password_change")
        request.is_management = request.membership.role in MANAGEMENT_ROLES
        request.role_display = request.membership.get_role_display()
        return view_func(request, *args, **kwargs)
    return wrapped

def log_event(request, action, obj, **metadata):
    AuditLog.objects.create(company=request.company, actor=request.user, action=action, object_type=obj._meta.label, object_id=str(obj.pk), ip_address=request.META.get("REMOTE_ADDR") or None, metadata=metadata)

def admin_required(view_func):
    @wraps(view_func)
    @company_required
    def wrapped(request, *args, **kwargs):
        if not is_admin(request.user, request.company):
            return render(request, "403.html", status=403)
        return view_func(request, *args, **kwargs)
    return wrapped
def employee_for(user, company=None):
    """Return the sole canonical profile, with a useful response for bad data."""
    matches = Employee.objects.filter(user=user, **({"company": company} if company else {})).select_related("user", "department", "designation")
    if matches.count() != 1:
        raise EmployeeProfileUnavailable
    return matches.get()


class EmployeeProfileUnavailable(Exception):
    pass


def employee_or_error(request):
    try:
        return employee_for(request.user, getattr(request, "company", None))
    except EmployeeProfileUnavailable:
        return render(request, "ems/no_employee_profile.html", status=403)

def wants_json(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("accept", "")

def json_result(success, message, status=200, data=None, error_code=None):
    payload = {"success": success, "message": message, "data": data or {}}
    if error_code:
        payload["error_code"] = error_code
    return JsonResponse(payload, status=status)

def format_duration(value):
    seconds = max(0, int(value.total_seconds()))
    return f"{seconds // 3600:02}:{(seconds % 3600) // 60:02}:{seconds % 60:02}"

def paginate(request, records, per_page=12):
    return Paginator(records, per_page).get_page(request.GET.get("page"))

def attendance_payload(employee):
    today = timezone.localdate()
    attendance = Attendance.objects.filter(company=employee.company, employee=employee, date=today).prefetch_related("sessions").first()
    active_session = AttendanceSession.objects.filter(attendance__employee=employee, attendance__date=today, punch_out__isnull=True).select_related("attendance").first()
    is_on_break = bool(attendance and attendance.check_in and not attendance.check_out and not active_session and attendance.sessions.exists())
    sessions = []
    if attendance:
        for session in attendance.sessions.all():
            sessions.append({
                "punch_in": timezone.localtime(session.punch_in).strftime("%H:%M"),
                "punch_out": timezone.localtime(session.punch_out).strftime("%H:%M") if session.punch_out else "Working",
                "duration": format_duration(session.duration),
            })
    return {
        "is_working": bool(active_session),
        "is_on_break": is_on_break,
        "is_complete": bool(attendance and attendance.check_out),
        "active_started_at": active_session.punch_in.isoformat() if active_session else "",
        "server_now": timezone.now().isoformat(),
        "working_time": format_duration(attendance.sessions_total) if attendance else "00:00:00",
        "break_time": format_duration(attendance.break_total) if attendance else "00:00:00",
        "sessions": sessions,
    }

def verify_employee_identity(request, employee):
    """Verify the submitted employee number and password against the logged-in account."""
    supplied_id = request.POST.get("employee_id", "").strip()
    supplied_password = request.POST.get("password", "")
    if employee.status != Employee.Status.ACTIVE:
        return "Your employee account is inactive."
    if supplied_id != employee.employee_id or not employee.user.check_password(supplied_password):
        return "Employee number or account password could not be verified."
    return None

@company_required
def dashboard(request):
    today = timezone.localdate()
    if not request.is_management:
        employee = employee_or_error(request)
        if not isinstance(employee, Employee): return employee
        context = {
            "employee": employee,
            "dashboard_role_display": request.role_display,
            "today_attendance": Attendance.objects.filter(company=request.company, employee=employee, date=today).prefetch_related("sessions").first(),
            "active_session": AttendanceSession.objects.filter(employee=employee, punch_out__isnull=True).first(),
            "recent_attendance": employee.attendance.prefetch_related("sessions")[:5],
            "recent_leaves": employee.leave_requests.all()[:5],
            "payroll": employee.payrolls.first(),
            "server_now": timezone.now().isoformat(),
        }
        if context["today_attendance"]:
            context["working_time"] = format_duration(context["today_attendance"].sessions_total)
            context["break_time"] = format_duration(context["today_attendance"].break_total)
        else:
            context["working_time"] = "00:00:00"
            context["break_time"] = "00:00:00"
        return render(request, "ems/dashboard.html", context)
    context = {
        "dashboard_role": request.membership.role,
        "dashboard_role_display": request.role_display,
        "total_employees": Employee.objects.filter(company=request.company).count(),
        "active_employees": Employee.objects.filter(company=request.company, status="active").count(),
        "departments": Department.objects.filter(company=request.company, active=True).count(),
        "present_today": Attendance.objects.filter(company=request.company, date=today, status__in=["present", "late"]).count(),
        "absent_today": Attendance.objects.filter(company=request.company, date=today, status="absent").count(),
        "currently_working": AttendanceSession.objects.filter(employee__company=request.company, punch_out__isnull=True).count(),
        "pending_leaves": LeaveRequest.objects.filter(company=request.company, status="pending").count(),
        "payroll_total": sum((p.net_salary for p in Payroll.objects.filter(company=request.company, pay_period__year=today.year, pay_period__month=today.month)), start=0),
        "recent_leaves": LeaveRequest.objects.filter(company=request.company).select_related("employee__user")[:5],
        "department_counts": Department.objects.filter(company=request.company).annotate(count=Count("employees")),
    }
    return render(request, "ems/dashboard.html", context)


def entrypoint(request):
    if request.user.is_authenticated:
        return redirect("ems:dashboard")
    if not Company.objects.filter(active=True).exists():
        return redirect("ems:setup")
    return redirect("ems:login")


def setup(request):
    if request.user.is_authenticated:
        return redirect("ems:dashboard")
    form = CompanySetupForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        username = (data.get("admin_username") or data["admin_email"]).strip()
        company_slug = slugify(data["company_name"])
        base_slug = company_slug or "company"
        suffix = 1
        while Company.objects.filter(slug=company_slug).exists():
            suffix += 1
            company_slug = f"{base_slug}-{suffix}"
        owner_name = data["owner_name"].strip().split(None, 1)
        first_name = owner_name[0]
        last_name = owner_name[1] if len(owner_name) > 1 else ""
        with transaction.atomic():
            company = Company.objects.create(
                name=data["company_name"], slug=company_slug, logo=data.get("logo"),
                email=data["company_email"], phone=data["phone"], address=data["address"],
                city=data["city"], state=data["state"], country=data["country"], pincode=data["pincode"],
                website=data.get("website", ""), industry=data["industry"], timezone=data["timezone"],
            )
            user = User.objects.create_user(
                username=username, email=data["admin_email"], password=data["password"],
                first_name=first_name, last_name=last_name,
            )
            department = Department.objects.create(company=company, name="Administration")
            designation = Designation.objects.create(company=company, name="Company Owner")
            Employee.objects.create(
                user=user, company=company, employee_id="OWNER-001", department=department,
                designation=designation, phone=data["phone"], joining_date=timezone.localdate(),
            )
            CompanyMembership.objects.create(user=user, company=company, role=CompanyMembership.Role.OWNER)
            UserAccountProfile.objects.create(user=user, must_change_password=False)
            CompanySetting.objects.create(company=company, name=company.name, timezone=company.timezone)
            WorkSchedule.objects.create(company=company)
        request.session["active_company_id"] = company.pk
        login(request, user, backend=settings.AUTHENTICATION_BACKENDS[0])
        messages.success(request, f"Welcome to {company.name}. Your company workspace is ready.")
        return redirect("ems:dashboard")
    return render(request, "ems/setup.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("ems:dashboard")
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        account_profile = UserAccountProfile.objects.filter(user=user).first()
        if account_profile and account_profile.must_change_password:
            return redirect("ems:password_change")
        return redirect(request.POST.get("next") or "ems:dashboard")
    return render(request, "registration/login.html", {"form": form, "next": request.GET.get("next", "")})


@login_required
def password_change(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        request.user.set_password(form.cleaned_data["new_password"])
        request.user.save(update_fields=["password"])
        UserAccountProfile.objects.update_or_create(user=request.user, defaults={"must_change_password": False})
        login(request, request.user)
        messages.success(request, "Your password has been updated.")
        return redirect("ems:dashboard")
    return render(request, "registration/password_change.html", {"form": form})

@company_required
def profile(request):
    # Administrators can legitimately exist without an Employee row. Give
    # them a usable account profile instead of redirecting back to dashboard.
    if is_admin(request.user, request.company) and not Employee.objects.filter(user=request.user, company=request.company).exists():
        return render(request, "ems/admin_profile.html", {"account": request.user})
    employee = employee_or_error(request)
    if not isinstance(employee, Employee):
        return employee
    today = timezone.localdate()
    today_attendance = Attendance.objects.filter(company=request.company, employee=employee, date=today).prefetch_related("sessions").first()
    active_session = AttendanceSession.objects.filter(employee=employee, punch_out__isnull=True).select_related("attendance").first()
    return render(request, "ems/profile.html", {
        "employee": employee, "payroll": employee.payrolls.first(), "reviews": employee.reviews.all()[:5],
        "attendance": employee.attendance.prefetch_related("sessions")[:5], "today_attendance": today_attendance,
        "active_session": active_session, "working_time": format_duration(today_attendance.sessions_total) if today_attendance else "00:00:00",
        "break_time": format_duration(today_attendance.break_total) if today_attendance else "00:00:00",
        "server_now": timezone.localtime().isoformat(),
    })

@company_required
def attendance_action(request):
    if request.method != "POST":
        if wants_json(request):
            return json_result(False, "POST required.", 405)
        return HttpResponseForbidden("POST required")
    employee = employee_or_error(request)
    if not isinstance(employee, Employee):
        if wants_json(request):
            return json_result(False, "Your account is not linked to exactly one employee profile.", 403)
        return employee
    action = request.POST.get("action")
    if action == "verify":
        error = verify_employee_identity(request, employee)
        if error:
            if wants_json(request):
                return json_result(False, error, 403, error_code="INVALID_IDENTITY")
            messages.error(request, error); return redirect("ems:profile")
        if wants_json(request):
            return json_result(True, "Identity verified.", data=attendance_payload(employee))
        messages.success(request, "Identity verified. You can use attendance.")
        return redirect("ems:profile")
    now = timezone.now()
    success = False
    message = "Unknown attendance action."
    status = 400
    error_code = "INVALID_ACTION"
    with transaction.atomic():
        attendance = Attendance.objects.select_for_update().filter(employee=employee, date=timezone.localdate()).first()
        employee = Employee.objects.select_for_update().get(pk=employee.pk)
        attendance = Attendance.objects.select_for_update().filter(employee=employee, date=timezone.localdate()).first()
        active = AttendanceSession.objects.select_for_update().filter(attendance=attendance, punch_out__isnull=True).first() if attendance else None
        last_punch_out = AttendanceSession.objects.filter(
            employee=employee, punch_out__isnull=False
        ).order_by("-punch_out").values_list("punch_out", flat=True).first()
        if action in {"punch_in", "end_break"}:
            if active:
                message = "You are already working. Punch out before starting another session."
                status = 409; error_code = "ALREADY_CHECKED_IN"
            elif action == "end_break" and not attendance:
                message = "There is no active break to end."
                status = 409; error_code = "NO_ACTIVE_BREAK"
            elif attendance and attendance.check_out:
                message = "This attendance day is already complete."
                status = 409; error_code = "ATTENDANCE_COMPLETED"
            elif action == "punch_in" and last_punch_out and now < last_punch_out + timedelta(hours=12):
                eligible_at = timezone.localtime(last_punch_out + timedelta(hours=12))
                message = "Your next attendance day opens at {} after the required 12-hour rest period.".format(eligible_at.strftime("%I:%M %p").lstrip("0"))
                status = 409; error_code = "REST_PERIOD_ACTIVE"
            elif LeaveRequest.objects.filter(company=request.company, employee=employee, status=LeaveRequest.Status.APPROVED, start_date__lte=timezone.localdate(), end_date__gte=timezone.localdate()).exists():
                message = "You have approved leave for today and cannot punch in."
            else:
                attendance, _ = Attendance.objects.get_or_create(company=request.company, employee=employee, date=timezone.localdate(), defaults={"status": Attendance.Status.PRESENT, "check_in": timezone.localtime(now).time()})
                if not attendance.check_in:
                    attendance.check_in = timezone.localtime(now).time(); attendance.status = Attendance.Status.PRESENT; attendance.save(update_fields=["check_in", "status", "updated_at"])
                try:
                    with transaction.atomic():
                        AttendanceSession.objects.create(attendance=attendance, employee=employee, punch_in=now)
                except IntegrityError:
                    message = "Your attendance state changed in another request. Refresh and try again."
                    status = 409; error_code = "ATTENDANCE_STATE_CONFLICT"
                else:
                    log_event(request, "attendance.break_ended" if action == "end_break" else "attendance.punch_in", attendance)
                    success = True; message = "Break ended. You are now working." if action == "end_break" else "Punch in recorded. You are now working."; status = 200
        elif action == "start_break":
            if not active:
                message = "You are not currently working."
                status = 409; error_code = "NOT_WORKING"
            else:
                active.punch_out = now
                active.save(update_fields=["punch_out", "updated_at"])
                log_event(request, "attendance.break_started", active.attendance)
                success = True; message = "Break started."; status = 200
        elif action == "punch_out":
            if not active:
                message = "There is no active work session to punch out."
                status = 409; error_code = "NO_OPEN_SESSION"
            else:
                active.punch_out = now; active.save(update_fields=["punch_out", "updated_at"])
                attendance = active.attendance; attendance.check_out = timezone.localtime(now).time(); attendance.save(update_fields=["check_out", "updated_at"])
                log_event(request, "attendance.punch_out", attendance)
                success = True; message = "Punch out recorded. You can resume later with a new session."; status = 200
    if wants_json(request):
        return json_result(success, message, status, attendance_payload(employee), None if success else error_code)
    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect("ems:profile")

@company_required
def attendance_state(request):
    if not wants_json(request):
        return redirect("ems:profile")
    employee = employee_or_error(request)
    if not isinstance(employee, Employee): return json_result(False, "Employee profile unavailable.", 403)
    return json_result(True, "Attendance state loaded.", data=attendance_payload(employee))

@admin_required
def employees(request):
    records = Employee.objects.filter(company=request.company).select_related("user", "department", "designation").order_by("employee_id")
    q=request.GET.get("q", ""); department=request.GET.get("department", ""); status=request.GET.get("status", "")
    if q: records=records.filter(Q(employee_id__icontains=q)|Q(user__first_name__icontains=q)|Q(user__last_name__icontains=q)|Q(user__email__icontains=q))
    if department: records=records.filter(department_id=department)
    if status: records=records.filter(status=status)
    return render(request,"ems/employees.html",{"employees":paginate(request,records),"departments":Department.objects.filter(company=request.company, active=True),"q":q,"selected_department":department,"selected_status":status})

@admin_required
def employee_form(request, pk=None):
    employee = get_object_or_404(Employee, pk=pk, company=request.company) if pk else None
    form=EmployeeForm(request.POST or None, request.FILES or None, instance=employee, company=request.company)
    if request.method=="POST" and form.is_valid():
        active_count = Employee.objects.filter(company=request.company, status=Employee.Status.ACTIVE).count()
        if not pk and active_count >= request.company.employee_limit:
            form.add_error(None, "Employee limit reached. Upgrade your plan to add more employees.")
            return render(request, "ems/form.html", {"form": form, "title": "Add Employee", "cancel_url": "ems:employees"})
        with transaction.atomic():
            employee = form.save(commit=False)
            employee.company = request.company
            employee.save()
            membership, _ = CompanyMembership.objects.get_or_create(user=employee.user, company=request.company)
            membership.role = form.cleaned_data["role"] or CompanyMembership.Role.EMPLOYEE
            membership.active = employee.status == Employee.Status.ACTIVE
            membership.save(update_fields=["role", "active", "updated_at"])
            log_event(request, "employee.created" if not pk else "employee.updated", employee)
        messages.success(request, "Employee account created." if not pk else "Employee saved.")
        return redirect("ems:employees")
    return render(request,"ems/form.html",{"form":form,"title":"Edit Employee" if employee else "Add Employee","cancel_url":"ems:employees"})

@admin_required
def employee_delete(request, pk):
    employee=get_object_or_404(Employee,pk=pk,company=request.company)
    if request.method=="POST":
        employee.status="inactive"
        employee.user.is_active=False
        employee.user.save(update_fields=["is_active"])
        CompanyMembership.objects.filter(user=employee.user, company=request.company).update(active=False, updated_at=timezone.now())
        employee.save()
        log_event(request, "employee.deactivated", employee)
        messages.success(request,"Employee deactivated.")
        return redirect("ems:employees")
    return render(request,"ems/confirm_delete.html",{"object":employee,"cancel_url":"ems:employees","message":"Deactivate this employee? Their records will be preserved."})

@admin_required
def export_employees(request):
    response=HttpResponse(content_type="text/csv"); response["Content-Disposition"]='attachment; filename="employees.csv"'; writer=csv.writer(response); writer.writerow(["ID","Name","Department","Designation","Email","Status","Joining date"])
    for e in Employee.objects.filter(company=request.company).select_related("user","department","designation"): writer.writerow([e.employee_id,e.full_name,e.department,e.designation,e.user.email,e.get_status_display(),e.joining_date])
    return response

def crud_list(request, model, form_class, template, title):
    records=model.objects.filter(company=request.company); return render(request,template,{"records":records,"title":title})
def crud_form(request, model, form_class, pk, title, cancel):
    instance=get_object_or_404(model,pk=pk, company=request.company) if pk else None; form=form_class(request.POST or None,instance=instance, company=request.company)
    if request.method=="POST" and form.is_valid(): obj=form.save(commit=False); obj.company=request.company; obj.save(); log_event(request, "record.saved", obj); messages.success(request,"Saved successfully."); return redirect(cancel)
    return render(request,"ems/form.html",{"form":form,"title":title,"cancel_url":cancel})

@admin_required
def departments(request): return crud_list(request,Department,DepartmentForm,"ems/simple_list.html","Departments")
@admin_required
def department_form(request,pk=None): return crud_form(request,Department,DepartmentForm,pk,"Edit Department" if pk else "Add Department","ems:departments")
@admin_required
def designations(request): return crud_list(request,Designation,DesignationForm,"ems/simple_list.html","Designations")
@admin_required
def designation_form(request,pk=None): return crud_form(request,Designation,DesignationForm,pk,"Edit Designation" if pk else "Add Designation","ems:designations")

@company_required
def attendance(request):
    records=Attendance.objects.filter(company=request.company).select_related("employee__user").prefetch_related("sessions"); target=None
    if is_admin(request.user, request.company):
        if request.GET.get("employee"): records=records.filter(employee_id=request.GET["employee"])
    else:
        target=employee_or_error(request)
        if not isinstance(target, Employee): return target
        records=records.filter(employee=target)
    if request.GET.get("date"): records=records.filter(date=request.GET["date"])
    if request.GET.get("status"): records=records.filter(status=request.GET["status"])
    if request.GET.get("q") and is_admin(request.user, request.company): records=records.filter(Q(employee__employee_id__icontains=request.GET["q"])|Q(employee__user__first_name__icontains=request.GET["q"])|Q(employee__user__last_name__icontains=request.GET["q"]))
    page = paginate(request, records)
    for record in page:
        record.working_time = format_duration(record.sessions_total)
        record.break_time = format_duration(record.break_total)
    return render(request,"ems/attendance.html",{"records":page,"employees":Employee.objects.filter(company=request.company,status="active"),"is_admin":is_admin(request.user, request.company),"today":timezone.localdate(),"status_choices":Attendance.Status.choices})
@admin_required
def attendance_form(request):
    form=AttendanceForm(request.POST or None, company=request.company)
    if request.method=="POST" and form.is_valid(): obj=form.save(commit=False); obj.company=request.company; obj.save(); log_event(request, "attendance.marked", obj); messages.success(request,"Attendance saved."); return redirect("ems:attendance")
    return render(request,"ems/form.html",{"form":form,"title":"Mark Attendance","cancel_url":"ems:attendance"})

@company_required
def leaves(request):
    records=LeaveRequest.objects.filter(company=request.company).select_related("employee__user","approved_by")
    if not is_admin(request.user, request.company):
        employee = employee_or_error(request)
        if not isinstance(employee, Employee): return employee
        records=records.filter(employee=employee)
    if request.GET.get("status"): records=records.filter(status=request.GET["status"])
    return render(request,"ems/leaves.html",{"records":records,"is_admin":is_admin(request.user, request.company)})
@company_required
def leave_apply(request):
    employee=employee_or_error(request)
    if not isinstance(employee, Employee): return employee
    form=LeaveForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        overlaps = LeaveRequest.objects.filter(company=request.company, employee=employee, status__in=[LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED], start_date__lte=form.cleaned_data["end_date"], end_date__gte=form.cleaned_data["start_date"])
        if overlaps.exists(): form.add_error(None, "This leave overlaps an existing request.")
        else: obj=form.save(commit=False); obj.employee=employee; obj.company=request.company; obj.save(); log_event(request, "leave.requested", obj); messages.success(request,"Leave request submitted."); return redirect("ems:leaves")
    return render(request,"ems/form.html",{"form":form,"title":"Request Leave","cancel_url":"ems:leaves"})
@admin_required
def leave_decision(request,pk,status):
    leave=get_object_or_404(LeaveRequest,pk=pk,company=request.company)
    allowed = {LeaveRequest.Status.APPROVED, LeaveRequest.Status.REJECTED}
    if request.method == "POST" and status in allowed and leave.status == LeaveRequest.Status.PENDING:
        leave.status=status
        if status == LeaveRequest.Status.APPROVED: leave.approved_by=request.user; leave.approved_at=timezone.now(); fields=["status", "approved_by", "approved_at", "updated_at"]
        else: leave.rejected_by=request.user; leave.rejected_at=timezone.now(); fields=["status", "rejected_by", "rejected_at", "updated_at"]
        leave.save(update_fields=fields); log_event(request, f"leave.{status}", leave); messages.success(request,f"Leave {status}.")
    elif request.method != "POST":
        return HttpResponseForbidden("POST required")
    return redirect("ems:leaves")

@company_required
def payroll(request):
    records=Payroll.objects.filter(company=request.company).select_related("employee__user")
    if not is_admin(request.user, request.company):
        employee = employee_or_error(request)
        if not isinstance(employee, Employee): return employee
        records=records.filter(employee=employee)
    return render(request,"ems/payroll.html",{"records":records,"is_admin":is_admin(request.user, request.company)})
@admin_required
def payroll_form(request,pk=None): return crud_form(request,Payroll,PayrollForm,pk,"Edit Payroll" if pk else "Run Payroll","ems:payroll")

@admin_required
def recruitment(request): return render(request,"ems/recruitment.html",{"jobs":Job.objects.filter(company=request.company).select_related("department")})
@admin_required
def job_form(request,pk=None): return crud_form(request,Job,JobForm,pk,"Edit Job" if pk else "New Job","ems:recruitment")
@admin_required
def performance(request): return render(request,"ems/performance.html",{"reviews":PerformanceReview.objects.filter(company=request.company).select_related("employee__user")})
@admin_required
def performance_form(request): return crud_form(request,PerformanceReview,PerformanceForm,None,"Add Review","ems:performance")
@admin_required
def reports(request): return render(request,"ems/reports.html",{"by_department":Department.objects.filter(company=request.company).annotate(total=Count("employees")),"attendance_count":Attendance.objects.filter(company=request.company,status="present").count(),"payroll_total":sum((p.net_salary for p in Payroll.objects.filter(company=request.company)), start=0)})
@admin_required
def settings_page(request):
    instance=CompanySetting.objects.filter(company=request.company).first() or CompanySetting(company=request.company); form=SettingForm(request.POST or None,instance=instance)
    if request.method=="POST" and form.is_valid(): obj=form.save(commit=False); obj.company=request.company; obj.save(); log_event(request, "company.settings_updated", obj); messages.success(request,"Settings saved."); return redirect("ems:settings")
    return render(request,"ems/form.html",{"form":form,"title":"Company Settings","cancel_url":"ems:dashboard"})

@admin_required
def work_schedule(request):
    instance = WorkSchedule.current(request.company); form = WorkScheduleForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save(); messages.success(request, "Attendance and payroll policy saved."); return redirect("ems:settings")
    return render(request, "ems/form.html", {"form": form, "title": "Working Hours & Attendance Policy", "cancel_url": "ems:settings"})

def logout_view(request):
    if request.method != "POST":
        return HttpResponseForbidden("POST required")
    logout(request)
    return redirect("ems:login")
def error_403(request, exception=None): return render(request,"403.html",status=403)
def error_400(request, exception=None): return render(request,"400.html",status=400)
def error_404(request, exception=None): return render(request,"404.html",status=404)
def error_500(request): return render(request,"500.html",status=500)
