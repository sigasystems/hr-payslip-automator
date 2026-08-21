import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os
import resend
try:
    from services.ms_auth_service import MicrosoftAuthService
except ModuleNotFoundError:
    from app.services.ms_auth_service import MicrosoftAuthService

class EmailSender:
    def __init__(self, settings, db_service=None):
        """
        settings: (id, host, port, email, password, use_tls, provider, resend_key, resend_from)
        """
        self.db = db_service
        self.provider = settings[6] if len(settings) > 6 else 'smtp'
        
        # SMTP Settings
        self.host = settings[1]
        self.port = settings[2]
        self.sender_email = settings[3]
        self.password = settings[4]
        self.use_tls = bool(settings[5])
        
        # Resend Settings
        self.resend_api_key = settings[7] if len(settings) > 7 else None
        self.resend_from_email = settings[8] if len(settings) > 8 else None
        if self.resend_api_key:
            resend.api_key = self.resend_api_key

        # Microsoft Auth Service
        self.ms_auth = MicrosoftAuthService(db_service) if db_service else None

    def _format_content(self, template, employee_name, month, emp_id=""):
        if not template:
            return ""
        return template.replace("{employee_name}", employee_name or "")\
                       .replace("{name}", employee_name or "")\
                       .replace("{month_year}", month or "")\
                       .replace("{month}", month or "")\
                       .replace("{employee_id}", emp_id or "")\
                       .replace("{emp_id}", emp_id or "")

    def send_payslip(self, receiver_email, employee_name, month, pdf_path, custom_subject=None, custom_body=None, emp_id=""):
        if self.provider == 'resend':
            return self._send_via_resend(receiver_email, employee_name, month, pdf_path, custom_subject, custom_body, emp_id)
        elif self.provider == 'microsoft':
            return self._send_via_microsoft(receiver_email, employee_name, month, pdf_path, custom_subject, custom_body, emp_id)
        else:
            return self._send_via_smtp(receiver_email, employee_name, month, pdf_path, custom_subject, custom_body, emp_id)

    def _send_via_resend(self, receiver_email, employee_name, month, pdf_path, custom_subject=None, custom_body=None, emp_id=""):
        try:
            with open(pdf_path, "rb") as f:
                pdf_content = f.read()

            subject = self._format_content(custom_subject, employee_name, month, emp_id) if custom_subject else f"Salary Slip - {month}"
            
            if custom_body:
                formatted_body = self._format_content(custom_body, employee_name, month, emp_id)
                html_body = f"<p>{formatted_body.replace(chr(10), '<br>')}</p>"
            else:
                html_body = f"""<p>Hi {employee_name},</p>
<p>Please find attached your salary slip for {month}.</p>
<p>Regards,<br>HR Team</p>"""

            params = {
                "from": self.resend_from_email or "onboarding@resend.dev",
                "to": receiver_email,
                "subject": subject,
                "html": html_body,
                "attachments": [
                    {
                        "filename": os.path.basename(pdf_path),
                        "content": list(pdf_content),
                    }
                ],
            }

            resend.Emails.send(params)
            return True, "Email sent successfully via Resend"
        except Exception as e:
            return False, f"Resend Error: {str(e)}"

    def _send_via_microsoft(self, receiver_email, employee_name, month, pdf_path, custom_subject=None, custom_body=None, emp_id=""):
        if not self.ms_auth:
            return False, "Microsoft Auth Service is not initialized."

        token, sender_email, err = self.ms_auth.get_valid_access_token()
        if err:
            return False, f"Microsoft OAuth Error: {err}"

        try:
            subject = self._format_content(custom_subject, employee_name, month, emp_id) if custom_subject else f"Salary Slip - {month}"
            body = self._format_content(custom_body, employee_name, month, emp_id) if custom_body else f"""Hi {employee_name},

Please find attached your salary slip for {month}.

Regards,
HR Team"""

            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = receiver_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            # Attach PDF
            with open(pdf_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(pdf_path))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(pdf_path)}"'
            msg.attach(part)

            # Connect to Office365 SMTP
            server = smtplib.SMTP("smtp.office365.com", 587, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()

            # XOAUTH2 Authentication
            auth_str = MicrosoftAuthService.generate_xoauth2_string(sender_email, token)
            code, resp = server.docmd("AUTH", "XOAUTH2 " + auth_str)
            if code != 235:
                server.quit()
                return False, f"OAuth Authentication Failed ({code}): {resp.decode('utf-8', errors='ignore')}"

            server.send_message(msg)
            server.quit()
            return True, f"Email sent successfully via Microsoft 365 ({sender_email})"
        except Exception as e:
            return False, f"Microsoft 365 SMTP Error: {str(e)}"

    def _send_via_smtp(self, receiver_email, employee_name, month, pdf_path, custom_subject=None, custom_body=None, emp_id=""):
        try:
            subject = self._format_content(custom_subject, employee_name, month, emp_id) if custom_subject else f"Salary Slip - {month}"
            body = self._format_content(custom_body, employee_name, month, emp_id) if custom_body else f"""Hi {employee_name},

Please find attached your salary slip for {month}.

Regards,
HR Team"""

            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = receiver_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            # Attach PDF
            with open(pdf_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(pdf_path))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(pdf_path)}"'
            msg.attach(part)

            # Connect and send
            server = smtplib.SMTP(self.host, self.port, timeout=15)
            if self.use_tls:
                server.starttls()
            
            server.login(self.sender_email, self.password)
            server.send_message(msg)
            server.quit()
            return True, "Email sent successfully via SMTP"
        except Exception as e:
            return False, f"SMTP Error: {str(e)}"

    @staticmethod
    def test_connection(host, port, email, password, use_tls, provider='smtp', resend_key='', resend_from='', db_service=None):
        if provider == 'resend':
            try:
                resend.api_key = resend_key
                resend.Domains.list()
                return True, "Resend API key is valid"
            except Exception as e:
                return False, f"Resend Error: {str(e)}"
        elif provider == 'microsoft':
            if not db_service:
                return False, "Database service unavailable for Microsoft OAuth check."
            ms_auth = MicrosoftAuthService(db_service)
            token, sender_email, err = ms_auth.get_valid_access_token()
            if err:
                return False, f"Microsoft OAuth verification failed: {err}"
            try:
                server = smtplib.SMTP("smtp.office365.com", 587, timeout=10)
                server.ehlo()
                server.starttls()
                server.ehlo()
                auth_str = MicrosoftAuthService.generate_xoauth2_string(sender_email, token)
                code, resp = server.docmd("AUTH", "XOAUTH2 " + auth_str)
                server.quit()
                if code == 235:
                    return True, f"Microsoft 365 OAuth connection successful ({sender_email})"
                else:
                    return False, f"Microsoft SMTP Authentication Failed ({code}): {resp.decode('utf-8', errors='ignore')}"
            except Exception as e:
                return False, f"Microsoft 365 Connection Error: {str(e)}"
        else:
            try:
                server = smtplib.SMTP(host, port, timeout=10)
                if use_tls:
                    server.starttls()
                server.login(email, password)
                server.quit()
                return True, "SMTP Connection successful"
            except Exception as e:
                return False, f"SMTP Error: {str(e)}"
