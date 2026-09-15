from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q
from django.utils import timezone

from ..models import Attendance, CompanyHoliday, Employee, EmployeeSalary, LeaveRequest, Payroll, WorkSchedule

MONEY = Decimal("0.01")
HOURS = Decimal("3600")


def money(value):
    return Decimal(value or 0).quantize(MONEY, rounding=ROUND_HALF_UP)


def hours(seconds):
    return (Decimal(seconds or 0) / HOURS).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class PayrollCalculation:
    employee: Employee
    period_start: date
    period_end: date
    salary: dict
    summary: dict
    earnings: dict
    deductions: dict
    net_pay: Decimal
    breakdown: list


def _salary_for(employee, period_start):
    structure = EmployeeSalary.objects.filter(employee=employee, company=employee.company, effective_from__lte=period_start).order_by("-effective_from").first()
    if structure:
        return {
            "monthly_gross": money(structure.monthly_gross), "basic_salary": money(structure.basic_salary),
            "hra": money(structure.hra), "allowances": money(structure.allowances),
            "fixed_deductions": money(structure.fixed_deductions), "bonus": money(structure.bonus),
            "overtime_enabled": structure.overtime_enabled, "overtime_multiplier": Decimal(structure.overtime_multiplier),
        }
    legacy = Payroll.objects.filter(employee=employee, company=employee.company, pay_period__lte=period_start).order_by("-pay_period").first()
    if legacy:
        return {
            "monthly_gross": money(legacy.basic_salary + legacy.hra + legacy.allowances), "basic_salary": money(legacy.basic_salary),
            "hra": money(legacy.hra), "allowances": money(legacy.allowances), "fixed_deductions": money(legacy.deductions),
            "bonus": money(legacy.bonus), "overtime_enabled": False, "overtime_multiplier": Decimal("1.5"),
        }
    return {"monthly_gross": money(0), "basic_salary": money(0), "hra": money(0), "allowances": money(0), "fixed_deductions": money(0), "bonus": money(0), "overtime_enabled": False, "overtime_multiplier": Decimal("1.5")}


def calculate_payroll(employee, period_start, period_end):
    schedule = WorkSchedule.current(employee.company)
    salary = _salary_for(employee, period_start)
    required_daily = Decimal(schedule.expected_daily_hours or 0)
    half_day_hours = Decimal(schedule.half_day_hours or 0)
    weekly_offs = set(schedule.weekly_offs or [6])
    holidays = {holiday.date: holiday for holiday in CompanyHoliday.objects.filter(company=employee.company, date__range=(period_start, period_end))}
    leaves = LeaveRequest.objects.filter(company=employee.company, employee=employee, status=LeaveRequest.Status.APPROVED, start_date__lte=period_end, end_date__gte=period_start)
    leave_by_date = {}
    for leave in leaves:
        cursor = max(leave.start_date, period_start)
        end = min(leave.end_date, period_end)
        while cursor <= end:
            leave_by_date[cursor] = leave
            cursor += timedelta(days=1)
    attendance = {row.date: row for row in Attendance.objects.filter(company=employee.company, employee=employee, date__range=(period_start, period_end)).prefetch_related("sessions")}
    scheduled_dates = []
    cursor = period_start
    while cursor <= period_end:
        if cursor.weekday() not in weekly_offs and cursor not in holidays:
            scheduled_dates.append(cursor)
        cursor += timedelta(days=1)
    divisor = Decimal(len(scheduled_dates) or 1)
    if schedule.salary_calculation_method == "calendar_days":
        divisor = Decimal((period_end - period_start).days + 1)
    elif schedule.salary_calculation_method == "fixed_30":
        divisor = Decimal(30)
    daily_rate = money(salary["monthly_gross"] / divisor)
    hourly_rate = salary["monthly_gross"] / divisor / (required_daily or Decimal(1))
    breakdown = []
    present = Decimal(0); absent = Decimal(0); paid_leave = Decimal(0); unpaid_leave = Decimal(0); half_days = Decimal(0)
    worked_seconds = 0; overtime_seconds = 0; absent_deduction = money(0); leave_deduction = money(0); short_deduction = money(0)
    for day in (period_start + timedelta(days=index) for index in range((period_end - period_start).days + 1)):
        holiday = holidays.get(day)
        leave = leave_by_date.get(day)
        row = attendance.get(day)
        worked = row.sessions_total.total_seconds() if row else 0
        worked_seconds += int(max(0, worked))
        required = required_daily if day in scheduled_dates else Decimal(0)
        status = "weekly_off" if day.weekday() in weekly_offs else "holiday" if holiday else "paid_leave" if leave and leave.is_paid else "unpaid_leave" if leave else "absent"
        payable = money(0); deduction = money(0)
        if holiday or (day.weekday() in weekly_offs):
            payable = daily_rate if holiday and holiday.paid else money(0)
        elif leave:
            if leave.is_paid:
                paid_leave += 1; payable = daily_rate; status = "paid_leave"
            else:
                unpaid_leave += 1; leave_deduction += daily_rate; deduction = daily_rate; status = "unpaid_leave"
        elif worked > 0:
            worked_hours = Decimal(worked) / HOURS
            present += Decimal("0.5") if worked_hours < half_day_hours else Decimal(1)
            if worked_hours < half_day_hours: half_days += Decimal("1")
            payable = money(min(worked_hours, required_daily) * hourly_rate)
            if worked_hours < required_daily: short_deduction += money((required_daily - worked_hours) * hourly_rate); deduction = money((required_daily - worked_hours) * hourly_rate)
            if worked_hours > required_daily: overtime_seconds += int((worked_hours - required_daily) * HOURS)
            status = "half_day" if worked_hours < half_day_hours else "present"
        else:
            absent += 1; absent_deduction += daily_rate; deduction = daily_rate
        breakdown.append({"date": day.isoformat(), "status": status, "required_hours": str(required), "worked_hours": str(hours(worked)), "overtime_hours": str(hours(max(0, int((Decimal(worked) / HOURS - required_daily) * HOURS))) if required else Decimal(0)), "payable": str(payable), "deduction": str(deduction)})
    overtime_hours = hours(overtime_seconds)
    overtime_amount = money(overtime_hours * hourly_rate * (salary["overtime_multiplier"] if salary["overtime_enabled"] and schedule.overtime_enabled else Decimal(0)))
    gross = money(salary["monthly_gross"] + salary["bonus"] + overtime_amount)
    total_deductions = money(salary["fixed_deductions"] + absent_deduction + leave_deduction + short_deduction)
    return PayrollCalculation(employee, period_start, period_end, salary, {
        "working_days": len(scheduled_dates), "present_days": present, "absent_days": absent,
        "paid_leave_days": paid_leave, "unpaid_leave_days": unpaid_leave, "half_days": half_days,
        "required_hours": Decimal(len(scheduled_dates)) * required_daily, "worked_hours": hours(worked_seconds), "overtime_hours": overtime_hours,
    }, {"basic_salary": salary["basic_salary"], "hra": salary["hra"], "allowances": salary["allowances"], "bonus": salary["bonus"], "overtime": overtime_amount, "gross": gross}, {
        "attendance": absent_deduction, "leave": leave_deduction, "short_hours": short_deduction, "fixed": salary["fixed_deductions"], "total": total_deductions,
    }, money(gross - total_deductions), breakdown)


def month_period(year, month):
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])
