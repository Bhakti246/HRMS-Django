from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


def assign_default_company(apps, schema_editor):
    Company = apps.get_model("ems", "Company")
    company, _ = Company.objects.get_or_create(
        slug="default", defaults={"name": "Default Company", "legal_name": "Default Company"}
    )
    for name in ("Department", "Designation", "Employee", "Attendance", "LeaveRequest", "Payroll", "Job", "PerformanceReview", "CompanySetting", "WorkSchedule"):
        model = apps.get_model("ems", name)
        model.objects.filter(company__isnull=True).update(company=company)
    AttendanceSession = apps.get_model("ems", "AttendanceSession")
    for session in AttendanceSession.objects.filter(employee__isnull=True).select_related("attendance"):
        session.employee_id = session.attendance.employee_id
        session.save(update_fields=["employee"])
    User = apps.get_model("auth", "User")
    Membership = apps.get_model("ems", "CompanyMembership")
    employee_user_ids = apps.get_model("ems", "Employee").objects.filter(company=company).values_list("user_id", flat=True)
    for user_id in employee_user_ids:
        Membership.objects.get_or_create(user_id=user_id, company=company, defaults={"role": "employee"})
    for user in User.objects.filter(is_superuser=True):
        Membership.objects.get_or_create(user_id=user.pk, company=company, defaults={"role": "owner"})


class Migration(migrations.Migration):
    dependencies = [("ems", "0003_remove_attendancesession_one_open_session_per_attendance_and_more"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(name="Company", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("name", models.CharField(max_length=150)), ("legal_name", models.CharField(blank=True, max_length=200)),
            ("slug", models.SlugField(max_length=80, unique=True)), ("email", models.EmailField(blank=True, max_length=254)),
            ("phone", models.CharField(blank=True, max_length=25)), ("address", models.TextField(blank=True)),
            ("logo", models.ImageField(blank=True, upload_to="company_logos/")), ("timezone", models.CharField(default="Asia/Kolkata", max_length=64)),
            ("currency", models.CharField(default="INR", max_length=3)), ("date_format", models.CharField(default="d M Y", max_length=32)),
            ("active", models.BooleanField(default=True)), ("employee_limit", models.PositiveIntegerField(default=10)),
            ("inactive_employees_consume_seats", models.BooleanField(default=False)),
        ], options={"ordering": ["name"]}),
        migrations.CreateModel(name="CompanyMembership", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("role", models.CharField(choices=[("owner", "Company owner"), ("hr_admin", "HR admin"), ("hr_manager", "HR manager"), ("manager", "Manager"), ("employee", "Employee")], default="employee", max_length=20)),
            ("active", models.BooleanField(default=True)),
            ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="ems.company")),
            ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="company_memberships", to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="AuditLog", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("action", models.CharField(max_length=80)),
            ("object_type", models.CharField(max_length=100)), ("object_id", models.CharField(blank=True, max_length=64)),
            ("ip_address", models.GenericIPAddressField(blank=True, null=True)), ("metadata", models.JSONField(blank=True, default=dict)), ("timestamp", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_events", to=settings.AUTH_USER_MODEL)),
            ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="audit_logs", to="ems.company")),
        ], options={"ordering": ["-timestamp"]}),
        *[migrations.AddField(model_name=name.lower(), name="company", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="+", to="ems.company")) for name in ("Department", "Designation", "Employee", "Attendance", "LeaveRequest", "Payroll", "Job", "PerformanceReview", "CompanySetting", "WorkSchedule")],
        migrations.AddField(model_name="attendancesession", name="employee", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="+", to="ems.employee")),
        migrations.AddField(model_name="employee", name="reporting_manager", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="direct_reports", to="ems.employee")),
        migrations.AddField(model_name="employee", name="employment_type", field=models.CharField(default="full_time", max_length=30)),
        migrations.AddField(model_name="leaverequest", name="rejected_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="rejected_leaves", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="leaverequest", name="rejected_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="leaverequest", name="remarks", field=models.TextField(blank=True)),
        migrations.RunPython(assign_default_company, migrations.RunPython.noop),
        *[migrations.AlterField(model_name=name.lower(), name="company", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name=related, to="ems.company")) for name, related in (("Department", "departments"), ("Designation", "designations"), ("Attendance", "attendance"), ("LeaveRequest", "leave_requests"), ("Payroll", "payrolls"), ("Job", "jobs"), ("PerformanceReview", "performance_reviews"))],
        migrations.AlterField(model_name="employee", name="company", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="employees", to="ems.company")),
        migrations.AlterField(model_name="companysetting", name="company", field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="settings", to="ems.company")),
        migrations.AlterField(model_name="workschedule", name="company", field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="work_schedule", to="ems.company")),
        migrations.AlterField(model_name="attendancesession", name="employee", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attendance_sessions", to="ems.employee")),
        migrations.AlterField(model_name="department", name="name", field=models.CharField(max_length=100)),
        migrations.AlterField(model_name="designation", name="name", field=models.CharField(max_length=100)),
        migrations.AlterField(model_name="employee", name="employee_id", field=models.CharField(max_length=20)),
        migrations.RemoveConstraint(model_name="attendancesession", name="one_session_per_attendance"),
        migrations.AddConstraint(model_name="companymembership", constraint=models.UniqueConstraint(fields=("user", "company"), name="unique_company_membership")),
        migrations.AddConstraint(model_name="department", constraint=models.UniqueConstraint(fields=("company", "name"), name="unique_company_department")),
        migrations.AddConstraint(model_name="designation", constraint=models.UniqueConstraint(fields=("company", "name"), name="unique_company_designation")),
        migrations.AddConstraint(model_name="employee", constraint=models.UniqueConstraint(fields=("company", "employee_id"), name="unique_company_employee_id")),
        migrations.AddConstraint(model_name="attendancesession", constraint=models.UniqueConstraint(condition=Q(("punch_out__isnull", True)), fields=("employee",), name="one_open_session_per_employee")),
        migrations.AddIndex(model_name="companymembership", index=models.Index(fields=["company", "role", "active"], name="ems_compmem_comp_role_idx")),
        migrations.AddIndex(model_name="attendance", index=models.Index(fields=["company", "date"], name="ems_attenda_company_48fdf5_idx")),
        migrations.AddIndex(model_name="attendance", index=models.Index(fields=["company", "employee", "date"], name="ems_attenda_company_e62470_idx")),
        migrations.AddIndex(model_name="attendancesession", index=models.Index(fields=["attendance", "punch_out"], name="ems_attenda_attenda_68c761_idx")),
        migrations.AddIndex(model_name="leaverequest", index=models.Index(fields=["company", "employee", "status"], name="ems_leavere_company_0d4f90_idx")),
        migrations.AddIndex(model_name="leaverequest", index=models.Index(fields=["company", "start_date", "end_date"], name="ems_leavere_company_1cb1ae_idx")),
        migrations.AddIndex(model_name="employee", index=models.Index(fields=["company", "status"], name="ems_employe_company_13b5e9_idx")),
        migrations.AddIndex(model_name="auditlog", index=models.Index(fields=["company", "timestamp"], name="ems_auditlo_company_b1eeae_idx")),
        migrations.AddIndex(model_name="auditlog", index=models.Index(fields=["object_type", "object_id"], name="ems_auditlo_object__d9a224_idx")),
    ]
