# HR Payslip Automator

A modern Python desktop application for automated employee payslip distribution and management.

## Features

- **Dashboard**: Overview of processing stats and recent activity.
- **Automated Processing**: Upload a combined PDF, split it, extract details, match employees, and send emails automatically.
- **Employee Management**: CRUD operations and Excel import.
- **Detailed Logs**: Track every email sent, failure, or conflict.
- **Secure Settings**: Configure SMTP with support for TLS/SSL.
- **Modern UI**: Polished dark theme using CustomTkinter.

## Tech Stack

- Python 3.12+
- CustomTkinter (UI)
- PyMuPDF (PDF Processing)
- SQLite (Local Database)
- pandas (Excel Import)

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
   .\venv\Scripts\python app/main.py
   ```

## Packaging (Windows .exe)

To generate a standalone executable, use PyInstaller:

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --add-data "app/database;app/database" --add-data "app/assets;app/assets" app/main.py
```

## PDF Format Requirements

- 1 page = 1 employee payslip.
- Should contain at least one of: Employee Name, PAN Number, or UAN Number.
- PAN Regex: `[A-Z]{5}[0-9]{4}[A-Z]{1}`
- UAN Regex: `\d{12}`
