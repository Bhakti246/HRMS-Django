from datetime import date, time
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from ems.models import Attendance, Department, Designation, Employee, Job, LeaveRequest, Payroll, PerformanceReview

class Command(BaseCommand):
    help="Create realistic local HRMS demo data."
    def handle(self, *args, **kwargs):
        admin, _ = User.objects.get_or_create(username="admin@acme.test", defaults={"email":"admin@acme.test","first_name":"System","last_name":"Admin","is_staff":True,"is_superuser":True})
        admin.set_password("Admin@123"); admin.is_staff=True; admin.is_superuser=True; admin.save()
        departments={n:Department.objects.get_or_create(name=n)[0] for n in ["HR","Engineering","Analytics","Product"]}
        designations={n:Designation.objects.get_or_create(name=n)[0] for n in ["HR Manager","Software Engineer","Data Analyst","Product Manager"]}
        data=[("EMP-001","Ananya","Sharma","HR Manager","HR","ananya@acme.test"),("EMP-002","Rohit","Verma","Software Engineer","Engineering","rohit@acme.test"),("EMP-003","Neha","Gupta","Data Analyst","Analytics","neha@acme.test"),("EMP-004","Arjun","Mehta","Product Manager","Product","arjun@acme.test")]
        people=[]
        for i,(eid,first,last,role,dept,email) in enumerate(data):
            user,_=User.objects.get_or_create(username=email,defaults={"email":email,"first_name":first,"last_name":last}); user.set_password("Employee@123"); user.save()
            emp,_=Employee.objects.get_or_create(employee_id=eid,defaults={"user":user,"department":departments[dept],"designation":designations[role],"phone":f"+91 98765 4321{i}","joining_date":date(2022+i%2,5,10),"status":"active"})
            people.append(emp); Attendance.objects.get_or_create(employee=emp,date=date.today(),defaults={"status":"present","check_in":time(9,30)})
        LeaveRequest.objects.get_or_create(employee=people[1],start_date=date.today(),end_date=date.today(),defaults={"leave_type":"casual","reason":"Personal work"})
        for emp in people: Payroll.objects.get_or_create(employee=emp,pay_period=date.today().replace(day=1),defaults={"basic_salary":50000,"hra":20000,"allowances":5000,"deductions":6000})
        Job.objects.get_or_create(title="Frontend Engineer",department=departments["Engineering"],defaults={"openings":2,"applicants":34,"stage":"screening"})
        PerformanceReview.objects.get_or_create(employee=people[0],review_date=date.today(),defaults={"score":8.5,"notes":"Strong people leadership and onboarding delivery."})
        self.stdout.write(self.style.SUCCESS("Demo data created. Admin: admin@acme.test / Admin@123; employees: email / Employee@123"))
