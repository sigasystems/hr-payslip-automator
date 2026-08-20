import sqlite3
import os
from datetime import datetime

class DatabaseService:
    def __init__(self, db_path=None):
        if db_path is None:
            # When packaged or running in Program Files, write database to %APPDATA%/HRPayslipAutomator/
            app_data = os.environ.get("APPDATA") or os.path.expanduser("~")
            db_dir = os.path.join(app_data, "HRPayslipAutomator")
            os.makedirs(db_dir, exist_ok=True)
            self.db_path = os.path.join(db_dir, "app.db")
            
            # Migration check: if old relative db exists, copy over
            old_db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "app.db")
            if os.path.exists(old_db) and not os.path.exists(self.db_path):
                try:
                    import shutil
                    shutil.copy2(old_db, self.db_path)
                except Exception:
                    pass
        else:
            self.db_path = db_path
            
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Employees table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS employees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id TEXT UNIQUE NOT NULL,
                    employee_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    department TEXT,
                    pan_number TEXT,
                    uan_number TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Email logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS email_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id TEXT,
                    extracted_name TEXT,
                    extracted_pan TEXT,
                    extracted_uan TEXT,
                    status TEXT, -- SENT, FAILED, CONFLICT, UNMATCHED
                    error_message TEXT,
                    pdf_path TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Settings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    smtp_host TEXT,
                    smtp_port INTEGER,
                    sender_email TEXT,
                    sender_password TEXT,
                    use_tls BOOLEAN DEFAULT 1,
                    email_provider TEXT DEFAULT 'smtp', -- 'smtp' or 'resend'
                    resend_api_key TEXT,
                    resend_from_email TEXT
                )
            ''')
            
            # Check for new columns if table existed (simple migration)
            try:
                cursor.execute("ALTER TABLE settings ADD COLUMN email_provider TEXT DEFAULT 'smtp'")
            except sqlite3.OperationalError: pass # Already exists
            try:
                cursor.execute("ALTER TABLE settings ADD COLUMN resend_api_key TEXT")
            except sqlite3.OperationalError: pass # Already exists
            try:
                cursor.execute("ALTER TABLE settings ADD COLUMN resend_from_email TEXT")
            except sqlite3.OperationalError: pass # Already exists
            try:
                cursor.execute("ALTER TABLE settings ADD COLUMN ms_client_id TEXT")
            except sqlite3.OperationalError: pass # Already exists
            try:
                cursor.execute("ALTER TABLE settings ADD COLUMN ms_tenant_id TEXT")
            except sqlite3.OperationalError: pass # Already exists

            # OAuth tokens table for Microsoft / other OAuth providers
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS oauth_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT UNIQUE NOT NULL,
                    email TEXT,
                    access_token TEXT,
                    refresh_token TEXT,
                    token_cache TEXT,
                    expires_at TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Insert default settings if not exists
            cursor.execute("SELECT COUNT(*) FROM settings")
            if cursor.fetchone()[0] == 0:
                cursor.execute('''
                    INSERT INTO settings (smtp_host, smtp_port, sender_email, sender_password, use_tls, email_provider)
                    VALUES ('smtp.gmail.com', 587, '', '', 1, 'smtp')
                ''')
            
            conn.commit()

    # Employee CRUD
    def add_employee(self, emp_id, name, email, dept="", pan="", uan=""):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO employees (employee_id, employee_name, email, department, pan_number, uan_number)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (emp_id, name, email, dept, pan, uan))
            conn.commit()

    def get_all_employees(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM employees")
            return cursor.fetchall()

    def update_employee(self, id, emp_id, name, email, dept, pan, uan):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE employees 
                SET employee_id=?, employee_name=?, email=?, department=?, pan_number=?, uan_number=?
                WHERE id=?
            ''', (emp_id, name, email, dept, pan, uan, id))
            conn.commit()

    def delete_employee(self, id):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM employees WHERE id=?", (id,))
            conn.commit()

    def delete_employees(self, ids):
        if not ids:
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join(['?'] * len(ids))
            cursor.execute(f"DELETE FROM employees WHERE id IN ({placeholders})", ids)
            conn.commit()

    # Logs
    def add_log(self, emp_id, ext_name, ext_pan, ext_uan, status, error="", pdf_path=""):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO email_logs (employee_id, extracted_name, extracted_pan, extracted_uan, status, error_message, pdf_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (emp_id, ext_name, ext_pan, ext_uan, status, error, pdf_path))
            conn.commit()

    def get_logs(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM email_logs ORDER BY sent_at DESC")
            return cursor.fetchall()

    # Settings
    def get_settings(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM settings LIMIT 1")
            return cursor.fetchone()

    def update_settings(self, host, port, email, password, tls, provider='smtp', resend_key='', resend_from='', ms_client_id='', ms_tenant_id=''):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE settings 
                SET smtp_host=?, smtp_port=?, sender_email=?, sender_password=?, use_tls=?, 
                    email_provider=?, resend_api_key=?, resend_from_email=?,
                    ms_client_id=?, ms_tenant_id=?
                WHERE id=1
            ''', (host, port, email, password, tls, provider, resend_key, resend_from, ms_client_id, ms_tenant_id))
            conn.commit()

    # OAuth Token Management
    def save_oauth_tokens(self, provider, email, access_token, refresh_token, token_cache="", expires_at=""):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO oauth_tokens (provider, email, access_token, refresh_token, token_cache, expires_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(provider) DO UPDATE SET
                    email=excluded.email,
                    access_token=excluded.access_token,
                    refresh_token=excluded.refresh_token,
                    token_cache=excluded.token_cache,
                    expires_at=excluded.expires_at,
                    updated_at=CURRENT_TIMESTAMP
            ''', (provider, email, access_token, refresh_token, token_cache, str(expires_at)))
            conn.commit()

    def get_oauth_tokens(self, provider):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, provider, email, access_token, refresh_token, token_cache, expires_at, updated_at FROM oauth_tokens WHERE provider=?", (provider,))
            return cursor.fetchone()

    def delete_oauth_tokens(self, provider):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM oauth_tokens WHERE provider=?", (provider,))
            conn.commit()
