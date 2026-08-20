# HR Payslip Automator

A modern Python desktop application for automated employee payslip distribution and management.

## Features

- **Dashboard**: Overview of processing stats and real-time activity charts.
- **Automated Processing**: Upload a combined PDF, split it, extract details via OCR / text parsing, match employees, and dispatch payslips.
- **Employee Management**: Add, edit, single delete, bulk multi-select delete, and Excel bulk import.
- **Multi-Provider Email Dispatch**:
  - **SMTP**: Standard SMTP with TLS/SSL encryption.
  - **Microsoft 365 OAuth 2.0**: Secure Entra ID device flow authentication with Windows DPAPI encryption.
  - **Resend API**: Cloud transactional email service integration.
- **Detailed Logs**: Track every email sent, failure, or conflict with searchable filters.
- **CI/CD Automated Releases**: Automated PyInstaller bundling and Inno Setup Windows installer creation via GitHub Actions.
- **Modern UI**: Polished, responsive dark theme using CustomTkinter.

## Tech Stack

- Python 3.11+
- CustomTkinter (Modern Desktop UI)
- PyMuPDF (PDF Processing & Splitting)
- RapidOCR & ONNXRuntime (Fallback OCR extraction)
- MSAL & Cryptography (Microsoft 365 OAuth & Windows DPAPI token security)
- Resend Python SDK
- SQLite (Local Database)
- pandas & openpyxl (Excel Import)

## Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python app/main.py
   ```

## Packaging & Windows Installer

To build the standalone application and Inno Setup installer locally:

```powershell
.\build.ps1
```

- Standalone executable output: `dist\HRPayslipAutomator\HRPayslipAutomator.exe`
- Windows setup installer: `dist_installer\HRPayslipAutomator_Setup_v1.0.0.exe`

## PDF Format Requirements

- 1 page = 1 employee payslip.
- Should contain at least one of: Employee Name, PAN Number, or UAN Number.
- PAN Regex: `[A-Z]{5}[0-9]{4}[A-Z]{1}`
- UAN Regex: `\d{12}`
