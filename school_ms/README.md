# ElimuCore — School Management System

A multi-tenant school management system built for Kenyan schools using the
CBC/CBE curriculum. Built with Django 6, PostgreSQL, Tailwind, M-Pesa Daraja,
and Africa's Talking.

## Modules

- **Admissions** — application pipeline → review → admit → auto-parent & bed assignment
- **Boarding** — dormitories, beds, assignment transfer/checkout, roster downloads (CSV + PDF)
- **Academics** — timetables, syllabus coverage, lesson plans, mark sheets, report cards
- **Attendance** — class teacher, teacher, and school-wide views with PDF exports
- **Finance** — fee structures, invoices, receipts, M-Pesa STK push + C2B, unallocated payment queue
- **Wallet** — student wallets with top-up, withdrawal, and pending-collection queue
- **Departments** — transport, library, kitchen, lab, health, security
- **Communications** — internal messaging, notices, SMS via Africa's Talking
- **Reporting** — 40+ PDF templates (fees, attendance, medical, timetables, rosters, leaving certificates)

## Roles

Principal · Deputy Principal (Admin) · Deputy Principal (Academics) · Director of Studies · Secretary · Boarding Master · Accountant · Teacher · Class Teacher · Nurse · Librarian · Lab Technician · Chief Chef · Security Officer · Store Keeper · Driver · Parent · Student

## Tech stack

- Python 3.12, Django 6.0
- PostgreSQL (production) / SQLite (development)
- Tailwind CSS via `django-tailwind`
- Celery + Redis (background tasks)
- WeasyPrint, xhtml2pdf, ReportLab (PDF generation)
- M-Pesa Daraja, Africa's Talking, Resend (integrations)

## Local setup

```bash
git clone https://github.com/SamuelEusabius/radicore.git
cd <repo-name>
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env      
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver