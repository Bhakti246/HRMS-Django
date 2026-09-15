from datetime import date, timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.management import call_command
from io import StringIO
from .models import Attendance, AttendanceSession, Company, CompanyMembership, Department, Designation, Employee, LeaveRequest, UserAccountProfile
from .forms import EmployeeForm


class AttendanceWorkflowTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Test Company", slug="test-company")
        department = Department.objects.create(company=self.company, name="Test Engineering")
        designation = Designation.objects.create(company=self.company, name="Test Engineer")
        self.user = User.objects.create_user("staff@example.test", password="Password@123", first_name="Test", last_name="Employee")
        self.employee = Employee.objects.create(company=self.company, user=self.user, employee_id="TEST-001", department=department, designation=designation, phone="9000000000", joining_date=date.today(), date_of_birth=date(1990, 1, 2))
        CompanyMembership.objects.create(user=self.user, company=self.company)
        self.client.login(username="staff@example.test", password="Password@123")

    def post_action(self, action, employee_id="TEST-001", password="Password@123"):
        return self.client.post(reverse("ems:attendance_action"), {"action": action, "employee_id": employee_id, "password": password})

    def test_profile_and_punch_lifecycle(self):
        self.assertEqual(self.client.get(reverse("ems:profile")).status_code, 200)
        self.post_action("punch_in")
        self.assertEqual(AttendanceSession.objects.filter(attendance__employee=self.employee, punch_out__isnull=True).count(), 1)
        self.post_action("punch_in")
        self.assertEqual(AttendanceSession.objects.filter(attendance__employee=self.employee).count(), 1)
        self.post_action("punch_out")
        self.assertEqual(AttendanceSession.objects.filter(attendance__employee=self.employee, punch_out__isnull=True).count(), 0)
        self.post_action("punch_in")
        self.assertEqual(AttendanceSession.objects.filter(attendance__employee=self.employee).count(), 1)

    def test_identity_and_ownership_are_enforced(self):
        self.post_action("punch_in", employee_id="OTHER-001")
        self.assertFalse(AttendanceSession.objects.exists())
        self.post_action("punch_in", password="WrongPassword@123")
        self.assertFalse(AttendanceSession.objects.exists())

    def test_ajax_attendance_response(self):
        response = self.client.post(
            reverse("ems:attendance_action"),
            {"action": "punch_in", "employee_id": "TEST-001", "password": "Password@123"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertTrue(response.json()["data"]["is_working"])

    def test_logged_in_employee_can_punch_without_extra_verification(self):
        response = self.client.post(
            reverse("ems:attendance_action"),
            {"action": "punch_in"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

    def test_ajax_verification_returns_identity_result(self):
        response = self.client.post(
            reverse("ems:attendance_action"),
            {"action": "verify", "employee_id": "TEST-001", "password": "Password@123"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["message"], "Identity verified.")

    def test_ajax_invalid_identity_has_contextual_error(self):
        response = self.client.post(
            reverse("ems:attendance_action"),
            {"action": "verify", "employee_id": "001", "password": "Password@123"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()["success"])
        self.assertEqual(response.json()["error_code"], "INVALID_IDENTITY")

    def test_ajax_duplicate_punch_has_conflict_error(self):
        self.post_action("punch_in")
        response = self.client.post(
            reverse("ems:attendance_action"),
            {"action": "punch_in", "employee_id": "TEST-001", "password": "Password@123"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error_code"], "ALREADY_CHECKED_IN")

    def test_break_resume_and_punch_out_use_multiple_server_sessions(self):
        self.post_action("punch_in")
        self.post_action("start_break")
        self.assertEqual(AttendanceSession.objects.filter(attendance__employee=self.employee, punch_out__isnull=True).count(), 0)
        response = self.post_action("end_break")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AttendanceSession.objects.filter(attendance__employee=self.employee).count(), 2)
        self.post_action("punch_out")
        self.assertEqual(Attendance.objects.get(employee=self.employee, date=date.today()).check_out is not None, True)

    def test_employee_account_requires_first_password_change(self):
        form = EmployeeForm(company=self.company, data={
            "first_name": "First", "last_name": "Login", "email": "first@example.test",
            "username": "first-login", "temporary_password": "Temporary@123", "confirm_password": "Temporary@123",
            "employee_id": "TEST-003", "department": self.employee.department.pk,
            "designation": self.employee.designation.pk, "phone": "9222222222",
            "date_of_birth": "1993-02-03", "joining_date": str(date.today()),
            "gender": "other", "address": "", "status": "active",
            "emergency_contact": "", "employment_type": "full_time", "role": "employee",
        })
        self.assertTrue(form.is_valid(), form.errors)
        employee = form.save(commit=False)
        employee.company = self.company
        employee.save()
        self.assertTrue(UserAccountProfile.objects.get(user=employee.user).must_change_password)
        CompanyMembership.objects.create(user=employee.user, company=self.company, role=CompanyMembership.Role.EMPLOYEE)
        self.client.logout()
        response = self.client.post(reverse("ems:login"), {"username": "first-login", "password": "Temporary@123"})
        self.assertRedirects(response, reverse("ems:password_change"))
        response = self.client.post(reverse("ems:password_change"), {"new_password": "NewPassword@123", "confirm_password": "NewPassword@123"})
        self.assertRedirects(response, reverse("ems:dashboard"))
        self.assertFalse(UserAccountProfile.objects.get(user=employee.user).must_change_password)

    def test_admin_without_employee_profile_redirects(self):
        admin = User.objects.create_superuser("admin@example.test", "admin@example.test", "Password@123")
        CompanyMembership.objects.create(user=admin, company=self.company, role=CompanyMembership.Role.OWNER)
        self.client.force_login(admin)
        response = self.client.get(reverse("ems:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Administrator account")

    def test_logout_requires_post(self):
        self.assertEqual(self.client.get(reverse("ems:logout")).status_code, 403)
        response = self.client.post(reverse("ems:logout"))
        self.assertRedirects(response, reverse("ems:login"))

    def test_future_date_and_wrong_identity_are_rejected(self):
        response = self.post_action("punch_in", password="WrongPassword@123")
        self.assertFalse(AttendanceSession.objects.exists())
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Attendance.objects.filter(date__gt=timezone.localdate()).exists())

    def test_second_punch_in_after_punch_out_is_rejected(self):
        self.post_action("punch_in")
        self.post_action("punch_out")
        response = self.post_action("punch_in")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AttendanceSession.objects.filter(attendance__employee=self.employee).count(), 1)

    def test_next_attendance_day_requires_twelve_hour_rest_period(self):
        attendance = Attendance.objects.create(company=self.company, employee=self.employee, date=date.today() - timedelta(days=1), check_in="09:00:00", check_out="18:00:00")
        AttendanceSession.objects.create(
            attendance=attendance,
            employee=self.employee,
            punch_in=timezone.now() - timedelta(hours=6),
            punch_out=timezone.now() - timedelta(hours=5),
        )
        response = self.client.post(
            reverse("ems:attendance_action"),
            {"action": "punch_in"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error_code"], "REST_PERIOD_ACTIVE")

    def test_next_attendance_day_allows_punch_after_twelve_hours(self):
        attendance = Attendance.objects.create(company=self.company, employee=self.employee, date=date.today() - timedelta(days=1), check_in="09:00:00", check_out="18:00:00")
        AttendanceSession.objects.create(
            attendance=attendance,
            employee=self.employee,
            punch_in=timezone.now() - timedelta(hours=13),
            punch_out=timezone.now() - timedelta(hours=12, minutes=30),
        )
        response = self.client.post(
            reverse("ems:attendance_action"),
            {"action": "punch_in"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

    def test_employee_form_creates_the_canonical_user_link(self):
        form = EmployeeForm(company=self.company, data={
            "first_name": "New", "last_name": "Hire", "email": "new@example.test",
            "username": "new-hire", "temporary_password": "Temporary@123", "confirm_password": "Temporary@123",
            "employee_id": "TEST-002", "department": self.employee.department.pk,
            "designation": self.employee.designation.pk, "phone": "9111111111",
            "date_of_birth": "1992-02-03", "joining_date": str(date.today()),
            "gender": "other", "address": "", "status": "active",
            "emergency_contact": "", "employment_type": "full_time",
        })
        self.assertTrue(form.is_valid(), form.errors)
        employee = form.save(commit=False); employee.company = self.company; employee.save()
        self.assertIsNotNone(employee.user_id)
        self.assertEqual(Employee.objects.filter(user=employee.user).count(), 1)
        self.assertTrue(employee.user.check_password("Temporary@123"))

    def test_attendance_form_reports_missing_dob(self):
        self.employee.date_of_birth = None
        self.employee.save(update_fields=["date_of_birth"])
        from .forms import AttendanceForm
        form = AttendanceForm(data={"employee_number": "TEST-001", "date_of_birth": "1990-01-02", "date": str(date.today()), "status": "present"})
        self.assertFalse(form.is_valid())
        self.assertIn("does not have a date of birth recorded", str(form.errors))

    def test_admin_bootstrap_can_reset_existing_password(self):
        import os
        admin = User.objects.create_user("render-admin", password="old-password")
        os.environ.update({"DJANGO_SUPERUSER_USERNAME": "render-admin", "DJANGO_SUPERUSER_EMAIL": "admin@example.test", "DJANGO_SUPERUSER_PASSWORD": "new-password", "DJANGO_SUPERUSER_RESET_PASSWORD": "true"})
        try:
            call_command("bootstrap_admin", stdout=StringIO())
        finally:
            for key in ("DJANGO_SUPERUSER_USERNAME", "DJANGO_SUPERUSER_EMAIL", "DJANGO_SUPERUSER_PASSWORD", "DJANGO_SUPERUSER_RESET_PASSWORD"):
                os.environ.pop(key, None)
        admin.refresh_from_db()
        self.assertTrue(admin.check_password("new-password"))
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_login_accepts_email(self):
        self.client.logout()
        response = self.client.post(reverse("ems:login"), {"username": "staff@example.test", "password": "Password@123"})
        self.assertRedirects(response, reverse("ems:dashboard"))

    def test_leave_decision_rejects_get_and_invalid_status(self):
        admin = User.objects.create_superuser("admin2@example.test", "admin2@example.test", "Password@123")
        CompanyMembership.objects.create(user=admin, company=self.company, role=CompanyMembership.Role.OWNER)
        leave = LeaveRequest.objects.create(company=self.company, employee=self.employee, leave_type="casual", start_date=date.today(), end_date=date.today(), reason="Rest")
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("ems:leave_decision", args=[leave.pk, "approved"])).status_code, 403)
        self.client.post(reverse("ems:leave_decision", args=[leave.pk, "not-a-status"]))
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.PENDING)


class CompanyOnboardingTests(TestCase):
    def setup_data(self):
        return {
            "company_name": "Northwind People",
            "company_email": "hello@northwind.test",
            "phone": "9000000000",
            "address": "1 Main Street",
            "city": "Mumbai", "state": "Maharashtra", "country": "India", "pincode": "400001",
            "website": "https://northwind.test",
            "industry": "Technology",
            "timezone": "UTC",
            "owner_name": "Alex Owner",
            "admin_email": "alex@northwind.test",
            "admin_username": "alex-owner",
            "password": "StrongPassword@123",
            "confirm_password": "StrongPassword@123",
        }

    def test_empty_root_redirects_to_setup(self):
        Company.objects.all().delete()
        response = self.client.get(reverse("ems:entrypoint"))
        self.assertRedirects(response, reverse("ems:setup"))

    def test_setup_creates_owner_workspace_and_logs_in(self):
        response = self.client.post(reverse("ems:setup"), self.setup_data())
        self.assertRedirects(response, reverse("ems:dashboard"))
        company = Company.objects.get(slug="northwind-people")
        owner = User.objects.get(username="alex-owner")
        membership = CompanyMembership.objects.get(user=owner, company=company)
        self.assertEqual(membership.role, CompanyMembership.Role.OWNER)
        self.assertTrue(self.client.session.get("_auth_user_id"))
        self.assertTrue(Employee.objects.filter(user=owner, company=company, employee_id="OWNER-001").exists())
        self.assertTrue(Department.objects.filter(company=company, name="Administration").exists())
        self.assertTrue(Designation.objects.filter(company=company, name="Company Owner").exists())

    def test_existing_root_redirects_to_login(self):
        Company.objects.create(name="Existing", slug="existing")
        response = self.client.get(reverse("ems:entrypoint"))
        self.assertRedirects(response, reverse("ems:login"))

    def test_owner_role_controls_management_dashboard_without_staff_flag(self):
        company = Company.objects.create(name="Role Company", slug="role-company")
        owner = User.objects.create_user("role-owner", password="Password@123", is_staff=False)
        CompanyMembership.objects.create(user=owner, company=company, role=CompanyMembership.Role.OWNER)
        self.client.force_login(owner)
        response = self.client.get(reverse("ems:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Company owner dashboard")
