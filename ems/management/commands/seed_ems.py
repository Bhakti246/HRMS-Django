from datetime import date, time
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from ems.models import Attendance, Company, CompanyMembership, Department, Designation, Employee, Job, LeaveRequest, Payroll, PerformanceReview

class Command(BaseCommand):
    help="Create realistic local HRMS demo data."
    def handle(self, *args, **kwargs):
        company, _ = Company.objects.get_or_create(slug="acme-demo", defaults={"name": "Acme Demo", "legal_name": "Acme Demo"})
        admin, _ = User.objects.get_or_create(username="admin@acme.test", defaults={"email":"admin@acme.test","first_name":"System","last_name":"Admin","is_staff":True,"is_superuser":True})
        admin.set_unusable_password(); admin.is_staff=True; admin.is_superuser=True; admin.save()
        CompanyMembership.objects.get_or_create(user=admin, company=company, defaults={"role": CompanyMembership.Role.OWNER})
        departments={n:Department.objects.get_or_create(company=company, name=n)[0] for n in ["HR","Engineering","Analytics","Product"]}
        designations={n:Designation.objects.get_or_create(company=company, name=n)[0] for n in ["HR Manager","Software Engineer","Data Analyst","Product Manager"]}
        data=[("EMP-001","Ananya","Sharma","HR Manager","HR","ananya@acme.test",date(1990,2,14)),("EMP-002","Rohit","Verma","Software Engineer","Engineering","rohit@acme.test",date(1992,7,21)),("EMP-003","Neha","Gupta","Data Analyst","Analytics","neha@acme.test",date(1994,11,5)),("EMP-004","Arjun","Mehta","Product Manager","Product","arjun@acme.test",date(1989,5,10))]
        people=[]
        for i,(eid,first,last,role,dept,email,dob) in enumerate(data):
            user,_=User.objects.get_or_create(username=email,defaults={"email":email,"first_name":first,"last_name":last}); user.set_unusable_password(); user.save()
            emp,_=Employee.objects.get_or_create(company=company, employee_id=eid,defaults={"user":user,"department":departments[dept],"designation":designations[role],"phone":f"+91 98765 4321{i}","date_of_birth":dob,"joining_date":date(2022+i%2,5,10),"status":"active"})
            CompanyMembership.objects.get_or_create(user=user, company=company)
            people.append(emp); Attendance.objects.get_or_create(company=company, employee=emp,date=date.today(),defaults={"status":"present","check_in":time(9,30)})
        LeaveRequest.objects.get_or_create(company=company, employee=people[1],start_date=date.today(),end_date=date.today(),defaults={"leave_type":"casual","reason":"Personal work"})
        for emp in people: Payroll.objects.get_or_create(company=company, employee=emp,pay_period=date.today().replace(day=1),defaults={"basic_salary":50000,"hra":20000,"allowances":5000,"deductions":6000})
        Job.objects.get_or_create(company=company, title="Frontend Engineer",department=departments["Engineering"],defaults={"openings":2,"applicants":34,"stage":"screening"})
        PerformanceReview.objects.get_or_create(company=company, employee=people[0],review_date=date.today(),defaults={"score":8.5,"notes":"Strong people leadership and onboarding delivery."})
        self.stdout.write(self.style.SUCCESS("Demo data created with unusable passwords. Use Django's password-reset flow to activate accounts."))
