import csv
from datetime import date
from functools import wraps
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .forms import AttendanceForm, DepartmentForm, DesignationForm, EmployeeForm, JobForm, LeaveForm, PayrollForm, PerformanceForm, SettingForm, WorkScheduleForm
from .models import Attendance, AttendanceSession, CompanySetting, Department, Designation, Employee, Job, LeaveRequest, Payroll, PerformanceReview, WorkSchedule

def is_admin(user): return user.is_authenticated and user.is_staff

def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not is_admin(request.user):
            return render(request, "403.html", status=403)
        return view_func(request, *args, **kwargs)
    return wrapped
def employee_for(user):
    """Return the sole canonical profile, with a useful response for bad data."""
    matches = Employee.objects.filter(user=user).select_related("user", "department", "designation")
    if matches.count() != 1:
        raise EmployeeProfileUnavailable
    return matches.get()


class EmployeeProfileUnavailable(Exception):
    pass


def employee_or_error(request):
    try:
        return employee_for(request.user)
    except EmployeeProfileUnavailable:
        return render(request, "ems/no_employee_profile.html", status=403)

def wants_json(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("accept", "")

def json_result(success, message, status=200, data=None):
    return JsonResponse({"success": success, "message": message, "data": data or {}}, status=status)

def format_duration(value):
    seconds = max(0, int(value.total_seconds()))
    return f"{seconds // 3600:02}:{(seconds % 3600) // 60:02}:{seconds % 60:02}"

def paginate(request, records, per_page=12):
    return Paginator(records, per_page).get_page(request.GET.get("page"))

def attendance_payload(employee):
    today = timezone.localdate()
    attendance = Attendance.objects.filter(employee=employee, date=today).prefetch_related("sessions").first()
    active_session = AttendanceSession.objects.filter(attendance__employee=employee, attendance__date=today, punch_out__isnull=True).select_related("attendance").first()
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
        "active_started_at": active_session.punch_in.isoformat() if active_session else "",
        "server_now": timezone.now().isoformat(),
        "working_time": format_duration(attendance.sessions_total) if attendance else "00:00:00",
        "break_time": format_duration(attendance.break_total) if attendance else "00:00:00",
        "sessions": sessions,
    }

def verify_employee_identity(request, employee):
    """Never trust a submitted employee id: it must match the logged-in user's profile."""
    supplied_id = request.POST.get("employee_id", "").strip()
    supplied_dob = request.POST.get("date_of_birth", "")
    if employee.status != Employee.Status.ACTIVE:
        return "Your employee account is inactive."
    if not employee.date_of_birth:
        return "Your date of birth has not been recorded. Ask an administrator to update your profile."
    if supplied_id != employee.employee_id or supplied_dob != employee.date_of_birth.isoformat():
        return "Employee number or date of birth could not be verified."
    return None

@login_required
def dashboard(request):
    today = timezone.localdate()
    if not is_admin(request.user):
        employee = employee_or_error(request)
        if not isinstance(employee, Employee): return employee
        context = {
            "employee": employee,
            "today_attendance": Attendance.objects.filter(employee=employee, date=today).prefetch_related("sessions").first(),
            "active_session": AttendanceSession.objects.filter(attendance__employee=employee, attendance__date=today, punch_out__isnull=True).first(),
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
        "total_employees": Employee.objects.count(),
        "active_employees": Employee.objects.filter(status="active").count(),
        "departments": Department.objects.filter(active=True).count(),
        "present_today": Attendance.objects.filter(date=today, status__in=["present", "late"]).count(),
        "absent_today": Attendance.objects.filter(date=today, status="absent").count(),
        "currently_working": AttendanceSession.objects.filter(punch_out__isnull=True).count(),
        "pending_leaves": LeaveRequest.objects.filter(status="pending").count(),
        "payroll_total": sum((p.net_salary for p in Payroll.objects.filter(pay_period__year=today.year, pay_period__month=today.month)), start=0),
        "recent_leaves": LeaveRequest.objects.select_related("employee__user")[:5],
        "department_counts": Department.objects.annotate(count=Count("employees")),
    }
    return render(request, "ems/dashboard.html", context)

@login_required
def profile(request):
    # Administrators can legitimately exist without an Employee row. Give
    # them a usable account profile instead of redirecting back to dashboard.
    if is_admin(request.user) and not hasattr(request.user, "employee"):
        return render(request, "ems/admin_profile.html", {"account": request.user})
    employee = employee_or_error(request)
    if not isinstance(employee, Employee):
        return employee
    today = timezone.localdate()
    today_attendance = Attendance.objects.filter(employee=employee, date=today).prefetch_related("sessions").first()
    active_session = AttendanceSession.objects.filter(attendance__employee=employee, punch_out__isnull=True).select_related("attendance").first()
    return render(request, "ems/profile.html", {
        "employee": employee, "payroll": employee.payrolls.first(), "reviews": employee.reviews.all()[:5],
        "attendance": employee.attendance.prefetch_related("sessions")[:5], "today_attendance": today_attendance,
        "active_session": active_session, "working_time": format_duration(today_attendance.sessions_total) if today_attendance else "00:00:00",
        "break_time": format_duration(today_attendance.break_total) if today_attendance else "00:00:00",
        "server_now": timezone.localtime().isoformat(),
    })

@login_required
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
    error = verify_employee_identity(request, employee)
    if error:
        if wants_json(request):
            return json_result(False, error, 400)
        messages.error(request, error); return redirect("ems:profile")
    action = request.POST.get("action")
    now = timezone.now()
    if action == "verify":
        if wants_json(request):
            return json_result(True, "Identity verified.", data=attendance_payload(employee))
        messages.success(request, "Identity verified. You can punch in.")
        return redirect("ems:profile")
    success = False
    message = "Unknown attendance action."
    status = 400
    with transaction.atomic():
        attendance = Attendance.objects.select_for_update().filter(employee=employee, date=timezone.localdate()).first()
        employee = Employee.objects.select_for_update().get(pk=employee.pk)
        attendance = Attendance.objects.select_for_update().filter(employee=employee, date=timezone.localdate()).first()
        active = AttendanceSession.objects.select_for_update().filter(attendance=attendance, punch_out__isnull=True).first() if attendance else None
        if action == "punch_in":
            if active:
                message = "You are already working. Punch out before starting another session."
            elif attendance and attendance.sessions.exists():
                message = "Attendance has already been recorded for today. Multiple punch-ins are not allowed."
            elif LeaveRequest.objects.filter(employee=employee, status=LeaveRequest.Status.APPROVED, start_date__lte=timezone.localdate(), end_date__gte=timezone.localdate()).exists():
                message = "You have approved leave for today and cannot punch in."
            else:
                attendance, _ = Attendance.objects.get_or_create(employee=employee, date=timezone.localdate(), defaults={"status": Attendance.Status.PRESENT, "check_in": timezone.localtime(now).time()})
                if not attendance.check_in:
                    attendance.check_in = timezone.localtime(now).time(); attendance.status = Attendance.Status.PRESENT; attendance.save(update_fields=["check_in", "status", "updated_at"])
                AttendanceSession.objects.create(attendance=attendance, punch_in=now)
                success = True; message = "Punch in recorded. You are now working."; status = 200
        elif action == "punch_out":
            if not active:
                message = "There is no active work session to punch out."
            else:
                active.punch_out = now; active.save(update_fields=["punch_out", "updated_at"])
                attendance = active.attendance; attendance.check_out = timezone.localtime(now).time(); attendance.save(update_fields=["check_out", "updated_at"])
                success = True; message = "Punch out recorded. You can resume later with a new session."; status = 200
    if wants_json(request):
        return json_result(success, message, status, attendance_payload(employee))
    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect("ems:profile")

@login_required
def attendance_state(request):
    if not wants_json(request):
        return redirect("ems:profile")
    employee = employee_or_error(request)
    if not isinstance(employee, Employee): return json_result(False, "Employee profile unavailable.", 403)
    return json_result(True, "Attendance state loaded.", data=attendance_payload(employee))

@admin_required
def employees(request):
    records = Employee.objects.select_related("user", "department", "designation").order_by("employee_id")
    q=request.GET.get("q", ""); department=request.GET.get("department", ""); status=request.GET.get("status", "")
    if q: records=records.filter(Q(employee_id__icontains=q)|Q(user__first_name__icontains=q)|Q(user__last_name__icontains=q)|Q(user__email__icontains=q))
    if department: records=records.filter(department_id=department)
    if status: records=records.filter(status=status)
    return render(request,"ems/employees.html",{"employees":paginate(request,records),"departments":Department.objects.filter(active=True),"q":q,"selected_department":department,"selected_status":status})

@admin_required
def employee_form(request, pk=None):
    employee = get_object_or_404(Employee, pk=pk) if pk else None
    form=EmployeeForm(request.POST or None, request.FILES or None, instance=employee)
    if request.method=="POST" and form.is_valid():
        form.save()
        if getattr(form, "generated_password", None):
            messages.success(request, f"Employee saved. Share this one-time password securely: {form.generated_password}")
        else:
            messages.success(request,"Employee saved.")
        return redirect("ems:employees")
    return render(request,"ems/form.html",{"form":form,"title":"Edit Employee" if employee else "Add Employee","cancel_url":"ems:employees"})

@admin_required
def employee_delete(request, pk):
    employee=get_object_or_404(Employee,pk=pk)
    if request.method=="POST": employee.status="inactive"; employee.save(); messages.success(request,"Employee deactivated."); return redirect("ems:employees")
    return render(request,"ems/confirm_delete.html",{"object":employee,"cancel_url":"ems:employees","message":"Deactivate this employee? Their records will be preserved."})

@admin_required
def export_employees(request):
    response=HttpResponse(content_type="text/csv"); response["Content-Disposition"]='attachment; filename="employees.csv"'; writer=csv.writer(response); writer.writerow(["ID","Name","Department","Designation","Email","Status","Joining date"])
    for e in Employee.objects.select_related("user","department","designation"): writer.writerow([e.employee_id,e.full_name,e.department,e.designation,e.user.email,e.get_status_display(),e.joining_date])
    return response

def crud_list(request, model, form_class, template, title):
    records=model.objects.all(); return render(request,template,{"records":records,"title":title})
def crud_form(request, model, form_class, pk, title, cancel):
    instance=get_object_or_404(model,pk=pk) if pk else None; form=form_class(request.POST or None,instance=instance)
    if request.method=="POST" and form.is_valid(): form.save(); messages.success(request,"Saved successfully."); return redirect(cancel)
    return render(request,"ems/form.html",{"form":form,"title":title,"cancel_url":cancel})

@admin_required
def departments(request): return crud_list(request,Department,DepartmentForm,"ems/simple_list.html","Departments")
@admin_required
def department_form(request,pk=None): return crud_form(request,Department,DepartmentForm,pk,"Edit Department" if pk else "Add Department","ems:departments")
@admin_required
def designations(request): return crud_list(request,Designation,DesignationForm,"ems/simple_list.html","Designations")
@admin_required
def designation_form(request,pk=None): return crud_form(request,Designation,DesignationForm,pk,"Edit Designation" if pk else "Add Designation","ems:designations")

@login_required
def attendance(request):
    records=Attendance.objects.select_related("employee__user").prefetch_related("sessions"); target=None
    if is_admin(request.user):
        if request.GET.get("employee"): records=records.filter(employee_id=request.GET["employee"])
    else:
        target=employee_or_error(request)
        if not isinstance(target, Employee): return target
        records=records.filter(employee=target)
    if request.GET.get("date"): records=records.filter(date=request.GET["date"])
    if request.GET.get("status"): records=records.filter(status=request.GET["status"])
    if request.GET.get("q") and is_admin(request.user): records=records.filter(Q(employee__employee_id__icontains=request.GET["q"])|Q(employee__user__first_name__icontains=request.GET["q"])|Q(employee__user__last_name__icontains=request.GET["q"]))
    page = paginate(request, records)
    for record in page:
        record.working_time = format_duration(record.sessions_total)
        record.break_time = format_duration(record.break_total)
    return render(request,"ems/attendance.html",{"records":page,"employees":Employee.objects.filter(status="active"),"is_admin":is_admin(request.user),"today":timezone.localdate(),"status_choices":Attendance.Status.choices})
@admin_required
def attendance_form(request):
    form=AttendanceForm(request.POST or None)
    if request.method=="POST" and form.is_valid(): form.save(); messages.success(request,"Attendance saved."); return redirect("ems:attendance")
    return render(request,"ems/form.html",{"form":form,"title":"Mark Attendance","cancel_url":"ems:attendance"})

@login_required
def leaves(request):
    records=LeaveRequest.objects.select_related("employee__user","approved_by")
    if not is_admin(request.user):
        employee = employee_or_error(request)
        if not isinstance(employee, Employee): return employee
        records=records.filter(employee=employee)
    if request.GET.get("status"): records=records.filter(status=request.GET["status"])
    return render(request,"ems/leaves.html",{"records":records,"is_admin":is_admin(request.user)})
@login_required
def leave_apply(request):
    employee=employee_or_error(request)
    if not isinstance(employee, Employee): return employee
    form=LeaveForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        obj=form.save(commit=False); obj.employee=employee; obj.save(); messages.success(request,"Leave request submitted."); return redirect("ems:leaves")
    return render(request,"ems/form.html",{"form":form,"title":"Request Leave","cancel_url":"ems:leaves"})
@admin_required
def leave_decision(request,pk,status):
    leave=get_object_or_404(LeaveRequest,pk=pk)
    allowed = {LeaveRequest.Status.APPROVED, LeaveRequest.Status.REJECTED}
    if request.method == "POST" and status in allowed and leave.status == LeaveRequest.Status.PENDING:
        leave.status=status; leave.approved_by=request.user; leave.approved_at=timezone.now(); leave.save(update_fields=["status", "approved_by", "approved_at", "updated_at"]); messages.success(request,f"Leave {status}.")
    elif request.method != "POST":
        return HttpResponseForbidden("POST required")
    return redirect("ems:leaves")

@login_required
def payroll(request):
    records=Payroll.objects.select_related("employee__user")
    if not is_admin(request.user):
        employee = employee_or_error(request)
        if not isinstance(employee, Employee): return employee
        records=records.filter(employee=employee)
    return render(request,"ems/payroll.html",{"records":records,"is_admin":is_admin(request.user)})
@admin_required
def payroll_form(request,pk=None): return crud_form(request,Payroll,PayrollForm,pk,"Edit Payroll" if pk else "Run Payroll","ems:payroll")

@admin_required
def recruitment(request): return render(request,"ems/recruitment.html",{"jobs":Job.objects.select_related("department")})
@admin_required
def job_form(request,pk=None): return crud_form(request,Job,JobForm,pk,"Edit Job" if pk else "New Job","ems:recruitment")
@admin_required
def performance(request): return render(request,"ems/performance.html",{"reviews":PerformanceReview.objects.select_related("employee__user")})
@admin_required
def performance_form(request): return crud_form(request,PerformanceReview,PerformanceForm,None,"Add Review","ems:performance")
@admin_required
def reports(request): return render(request,"ems/reports.html",{"by_department":Department.objects.annotate(total=Count("employees")),"attendance_count":Attendance.objects.filter(status="present").count(),"payroll_total":sum((p.net_salary for p in Payroll.objects.all()), start=0)})
@admin_required
def settings_page(request):
    instance=CompanySetting.objects.first() or CompanySetting(); form=SettingForm(request.POST or None,instance=instance)
    if request.method=="POST" and form.is_valid(): form.save(); messages.success(request,"Settings saved."); return redirect("ems:settings")
    return render(request,"ems/form.html",{"form":form,"title":"Company Settings","cancel_url":"ems:dashboard"})

@admin_required
def work_schedule(request):
    instance = WorkSchedule.current(); form = WorkScheduleForm(request.POST or None, instance=instance)
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
