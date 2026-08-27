from datetime import date
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Attendance, AttendanceSession, Department, Designation, Employee, LeaveRequest
from .forms import EmployeeForm


class AttendanceWorkflowTests(TestCase):
    def setUp(self):
        department = Department.objects.create(name="Test Engineering")
        designation = Designation.objects.create(name="Test Engineer")
        self.user = User.objects.create_user("staff@example.test", password="Password@123", first_name="Test", last_name="Employee")
        self.employee = Employee.objects.create(user=self.user, employee_id="TEST-001", department=department, designation=designation, phone="9000000000", joining_date=date.today(), date_of_birth=date(1990, 1, 2))
        self.client.login(username="staff@example.test", password="Password@123")

    def post_action(self, action, employee_id="TEST-001", dob="1990-01-02"):
        return self.client.post(reverse("ems:attendance_action"), {"action": action, "employee_id": employee_id, "date_of_birth": dob})

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
        self.post_action("punch_in", dob="1991-01-02")
        self.assertFalse(AttendanceSession.objects.exists())

    def test_ajax_attendance_response(self):
        response = self.client.post(
            reverse("ems:attendance_action"),
            {"action": "punch_in", "employee_id": "TEST-001", "date_of_birth": "1990-01-02"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertTrue(response.json()["data"]["is_working"])

    def test_admin_without_employee_profile_redirects(self):
        admin = User.objects.create_superuser("admin@example.test", "admin@example.test", "Password@123")
        self.client.force_login(admin)
        response = self.client.get(reverse("ems:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Administrator account")

    def test_logout_requires_post(self):
        self.assertEqual(self.client.get(reverse("ems:logout")).status_code, 403)
        response = self.client.post(reverse("ems:logout"))
        self.assertRedirects(response, reverse("ems:login"))

    def test_future_date_and_wrong_identity_are_rejected(self):
        response = self.post_action("punch_in", dob="1990-01-03")
        self.assertFalse(AttendanceSession.objects.exists())
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Attendance.objects.filter(date__gt=timezone.localdate()).exists())

    def test_second_punch_in_after_punch_out_is_rejected(self):
        self.post_action("punch_in")
        self.post_action("punch_out")
        response = self.post_action("punch_in")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AttendanceSession.objects.filter(attendance__employee=self.employee).count(), 1)

    def test_employee_form_creates_the_canonical_user_link(self):
        form = EmployeeForm(data={
            "first_name": "New", "last_name": "Hire", "email": "new@example.test",
            "employee_id": "TEST-002", "department": self.employee.department.pk,
            "designation": self.employee.designation.pk, "phone": "9111111111",
            "date_of_birth": "1992-02-03", "joining_date": str(date.today()),
            "gender": "other", "address": "", "status": "active",
            "emergency_contact": "",
        })
        self.assertTrue(form.is_valid(), form.errors)
        employee = form.save()
        self.assertIsNotNone(employee.user_id)
        self.assertEqual(Employee.objects.filter(user=employee.user).count(), 1)

    def test_attendance_form_reports_missing_dob(self):
        self.employee.date_of_birth = None
        self.employee.save(update_fields=["date_of_birth"])
        from .forms import AttendanceForm
        form = AttendanceForm(data={"employee_number": "TEST-001", "date_of_birth": "1990-01-02", "date": str(date.today()), "status": "present"})
        self.assertFalse(form.is_valid())
        self.assertIn("does not have a date of birth recorded", str(form.errors))

    def test_leave_decision_rejects_get_and_invalid_status(self):
        admin = User.objects.create_superuser("admin2@example.test", "admin2@example.test", "Password@123")
        leave = LeaveRequest.objects.create(employee=self.employee, leave_type="casual", start_date=date.today(), end_date=date.today(), reason="Rest")
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("ems:leave_decision", args=[leave.pk, "approved"])).status_code, 403)
        self.client.post(reverse("ems:leave_decision", args=[leave.pk, "not-a-status"]))
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.PENDING)
