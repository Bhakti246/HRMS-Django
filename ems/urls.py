from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

app_name="ems"
urlpatterns=[
 path("",views.dashboard,name="dashboard"),path("login/",auth_views.LoginView.as_view(template_name="registration/login.html"),name="login"),path("logout/",views.logout_view,name="logout"),path("profile/",views.profile,name="profile"),path("profile/attendance/",views.attendance_action,name="attendance_action"),path("profile/attendance/state/",views.attendance_state,name="attendance_state"),
 path("employees/",views.employees,name="employees"),path("employees/add/",views.employee_form,name="employee_add"),path("employees/<int:pk>/edit/",views.employee_form,name="employee_edit"),path("employees/<int:pk>/delete/",views.employee_delete,name="employee_delete"),path("employees/export/",views.export_employees,name="employees_export"),
 path("departments/",views.departments,name="departments"),path("departments/add/",views.department_form,name="department_add"),path("departments/<int:pk>/edit/",views.department_form,name="department_edit"),path("designations/",views.designations,name="designations"),path("designations/add/",views.designation_form,name="designation_add"),path("designations/<int:pk>/edit/",views.designation_form,name="designation_edit"),
 path("attendance/",views.attendance,name="attendance"),path("attendance/add/",views.attendance_form,name="attendance_add"),path("leave/",views.leaves,name="leaves"),path("leave/apply/",views.leave_apply,name="leave_apply"),path("leave/<int:pk>/<str:status>/",views.leave_decision,name="leave_decision"),
 path("payroll/",views.payroll,name="payroll"),path("payroll/add/",views.payroll_form,name="payroll_add"),path("payroll/<int:pk>/edit/",views.payroll_form,name="payroll_edit"),path("recruitment/",views.recruitment,name="recruitment"),path("recruitment/add/",views.job_form,name="job_add"),path("performance/",views.performance,name="performance"),path("performance/add/",views.performance_form,name="performance_add"),path("reports/",views.reports,name="reports"),path("settings/",views.settings_page,name="settings"),path("settings/work-schedule/",views.work_schedule,name="work_schedule"),
]
