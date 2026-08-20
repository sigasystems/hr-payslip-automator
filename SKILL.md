Build a modern Python desktop application for automated employee payslip distribution and management.

# Tech Stack

Use:

- Python 3.12+
- CustomTkinter for desktop UI
- SQLite for local database
- PyMuPDF (fitz) for PDF processing
- pandas for Excel import/export
- smtplib + email.mime for email sending
- threading/background workers for long tasks
- PyInstaller compatible

# Application Goal

Create a fully offline HR desktop application that automates payslip processing and email delivery.

HR uploads one combined salary PDF where:

- 1 page = 1 employee payslip

The application must:

1. Split combined PDF into individual PDFs
2. Extract employee details from each page
3. Match employee from local database
4. Send payslip emails automatically
5. Store logs in SQLite
6. Provide modern HR dashboard UI
7. Handle failures/conflicts gracefully

Do NOT use:

- Cloud APIs
- Paid PDF services
- External PDF splitting APIs

Everything must run locally except SMTP email sending.

# Project Structure

app/
├── main.py
├── ui/
│ ├── dashboard.py
│ ├── upload_screen.py
│ ├── employees_screen.py
│ ├── logs_screen.py
│ ├── settings_screen.py
│ └── components/
├── services/
│ ├── pdf_splitter.py
│ ├── extractor.py
│ ├── matcher.py
│ ├── email_sender.py
│ ├── database.py
│ ├── logger.py
│ └── utils.py
├── database/
│ └── app.db
├── uploads/
├── output/
├── logs/
├── temp/
├── assets/
└── requirements.txt

# Core Workflow

HR uploads combined PDF
↓
Split PDF page-wise
↓
Extract employee details
↓
Match employee from database
↓
Generate individual PDF
↓
Send email with attachment
↓
Store processing logs
↓
Show success/failure summary

# Application Screens

1. Dashboard

---

Create modern dashboard cards showing:

- Total employees
- Emails sent
- Failed emails
- Conflict cases
- Unmatched payslips
- Last processing date
- Recent activity

Add:

- Charts
- Progress indicators
- Status summaries

2. Upload Payslip Screen

---

Allow HR to:

- Select combined PDF
- Start processing
- View real-time progress
- Cancel processing
- View live logs

Processing steps:

1. Split PDF page-wise
2. Extract text
3. Match employee
4. Generate PDF
5. Send email
6. Save logs

Show:

- Current employee being processed
- Success count
- Failure count
- Progress bar

3. Employee Management Screen

---

Provide full CRUD operations.

Fields:

- Employee ID
- Employee Name
- Email
- Department
- PAN Number
- UAN Number

Features:

- Add employee
- Edit employee
- Delete employee
- Search employees
- Import employees from Excel
- Export employees

4. Logs Screen

---

Display all processing logs.

Statuses:

- SENT
- FAILED
- CONFLICT
- UNMATCHED

Allow:

- Retry failed emails
- Manual employee assignment
- View extracted text
- Filter logs
- Export logs

5. Settings Screen

---

Allow configuring SMTP settings.

Fields:

- SMTP Host
- SMTP Port
- Sender Email
- App Password
- TLS/SSL option

Add:

- Test Email button
- Save settings button

# PDF Processing

Use PyMuPDF.

Since:

- 1 page = 1 employee

Split each page into:
output/EMP001.pdf

# Text Extraction Logic

Extract employee details using:

1. Employee Name
2. PAN Number
3. UAN Number

Possible formats:

Employee Name:

- Employee Name: Rahul Sharma
- Name: Rahul Sharma

PAN:

- PAN: ABCDE1234F

UAN:

- UAN: 123456789012

Use regex-based extraction.

# Regex Rules

PAN Regex:
[A-Z]{5}[0-9]{4}[A-Z]{1}

UAN Regex:
\d{12}

# Extraction Requirements

The extraction service must:

- Read text from each PDF page
- Normalize text
- Remove extra spaces
- Use case-insensitive matching
- Clean special characters

Examples:

- Rahul Sharma
- RAHUL SHARMA
- rahul sharma

should all be treated as same employee.

# Employee Matching Logic

Match employees using priority order:

1. PAN Number
2. UAN Number
3. Employee Name

Rules:

- First try PAN match
- If PAN missing → try UAN
- If UAN missing → try name
- If multiple matches found → mark CONFLICT
- If no match found → mark UNMATCHED

# Conflict Handling

If multiple employees match:

- Do NOT send email automatically
- Mark status:
  CONFLICT
- Show in review queue

If no match found:

- Mark status:
  UNMATCHED

# Manual Review Features

Allow HR to:

- Manually assign employee
- Edit extracted details
- Retry email sending
- Approve conflicted records

# Email Sending

Use SMTP email sending.

Support:

- Gmail
- Outlook
- Office365
- Zoho

# Email Template

Subject:
Salary Slip - {month}

Body:

Hi {employee_name},

Please find attached your salary slip for {month}.

Regards,
HR Team

Attach generated PDF.

# Database Schema

Use SQLite.

Create tables:

## employees

id
employee_id
employee_name
email
department
pan_number
uan_number
created_at

## email_logs

id
employee_id
extracted_name
extracted_pan
extracted_uan
status
error_message
pdf_path
sent_at

## settings

id
smtp_host
smtp_port
sender_email
sender_password
use_tls

# Security Requirements

- Do NOT hardcode credentials
- Store SMTP settings securely
- Mask PAN/UAN in logs

Examples:
ABCDE1234F → ABCDE\***\*F
123456789012 → \*\*\*\***789012

# UI Requirements

Use modern dark theme.

Design:

- Sidebar navigation
- Rounded cards
- Data tables
- Toast notifications
- Progress bars
- Confirmation dialogs
- Search inputs
- Status badges

Create polished HR software style interface.

# Architecture Requirements

Use clean modular architecture.

Requirements:

- Service-based structure
- Reusable components
- Proper error handling
- Logging system
- Type hints
- Background task handling
- Loading states
- Thread-safe UI updates

# Background Processing

Long-running tasks must:

- Run in background threads
- Not freeze UI
- Provide real-time updates

# Error Handling

Handle:

- Invalid PDF
- Missing employee
- SMTP failure
- Corrupted file
- Duplicate processing
- Network issues

Show user-friendly error messages.

# Logs & Audit

Track:

- Success
- Failure
- Conflict
- Unmatched
- Retry attempts
- Timestamp
- Error details

Add export logs feature.

# Future Ready Features

Structure code to support:

- Password-protected PDFs
- OCR support
- Multi-company payroll formats
- Scheduled sending
- WhatsApp integration
- Role-based access
- Payroll archives

# Packaging

Application must support:

- Windows .exe generation
- PyInstaller packaging
- Running without Python installed

# Generate

Generate complete implementation including:

- Full project architecture
- Database schema
- All UI screens
- PDF splitting service
- Text extraction service
- Employee matching logic
- Email sending service
- SQLite integration
- Threading/background workers
- Error handling
- Logging system
- requirements.txt
- Packaging instructions
- Clean production-ready code

# Important

The application should feel like professional HR software and be optimized for:

- Speed
- Reliability
- Offline usage
- Easy HR operations
- Large PDF processing
- Minimal manual intervention
