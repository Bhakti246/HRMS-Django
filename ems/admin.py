from django.contrib import admin
from .models import Attendance, AttendanceSession, CompanySetting, Department, Designation, Employee, Job, LeaveRequest, Payroll, PerformanceReview, WorkSchedule

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "full_name", "department", "designation", "status", "joining_date")
    list_filter = ("status", "department")
    search_fields = ("employee_id", "user__first_name", "user__last_name", "user__email")

class AttendanceSessionInline(admin.TabularInline):
    model = AttendanceSession
    extra = 0
    readonly_fields = ("duration", "created_at", "updated_at")

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("employee", "date", "check_in", "check_out", "status")
    list_filter = ("status", "date")
    search_fields = ("employee__employee_id", "employee__user__first_name", "employee__user__last_name")
    inlines = [AttendanceSessionInline]

@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ("attendance", "punch_in", "punch_out", "duration")
    list_filter = ("attendance__date",)
    search_fields = ("attendance__employee__employee_id", "attendance__employee__user__first_name")
    readonly_fields = ("duration", "created_at", "updated_at")

@admin.register(LeaveRequest)
class LeaveAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "start_date", "end_date", "status")
    list_filter = ("status", "leave_type")

@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ("employee", "pay_period", "net_salary", "status")
    list_filter = ("status",)

admin.site.register([Department, Designation, Job, PerformanceReview, CompanySetting, WorkSchedule])
