import customtkinter as ctk
from tkinter import messagebox, filedialog
import threading
from services.email_sender import EmailSender
from services.ms_auth_service import MicrosoftAuthService

class SettingsScreen(ctk.CTkFrame):
    def __init__(self, parent, db_service):
        super().__init__(parent, fg_color="transparent")
        self.db = db_service
        self.ms_auth = MicrosoftAuthService(db_service)
        self.is_authenticating = False
        self._setup_ui()

    def _setup_ui(self):
        # Header
        header = ctk.CTkLabel(self, text="Email Settings", font=ctk.CTkFont(size=24, weight="bold"))
        header.pack(pady=(0, 20), anchor="w")

        # Load current settings
        # (id, host, port, email, password, tls, provider, resend_key, resend_from)
        settings = self.db.get_settings()
        initial_provider = settings[6] if len(settings) > 6 else 'smtp'
        self.provider_var = ctk.StringVar(value=initial_provider)

        # Provider Selection
        provider_frame = ctk.CTkFrame(self)
        provider_frame.pack(fill="x", pady=10)
        ctk.CTkLabel(provider_frame, text="Email Provider:", width=150, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=20)
        self.provider_switch = ctk.CTkSegmentedButton(
            provider_frame, 
            values=["smtp", "microsoft", "resend"],
            variable=self.provider_var,
            command=self._on_provider_change
        )
        self.provider_switch.pack(side="left", padx=10, pady=10)

        # -----------------------------
        # 1. SMTP Settings Frame
        # -----------------------------
        self.smtp_frame = ctk.CTkFrame(self)
        fields = [
            ("SMTP Host", "host", settings[1]),
            ("SMTP Port", "port", settings[2]),
            ("Sender Email", "email", settings[3]),
            ("App Password", "password", settings[4]),
        ]
        
        self.entries = {}
        for i, (label, key, val) in enumerate(fields):
            row = ctk.CTkFrame(self.smtp_frame, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=5)
            
            ctk.CTkLabel(row, text=label, width=150, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, width=300)
            if key == "password":
                entry.configure(show="*")
            entry.insert(0, str(val) if val else "")
            entry.pack(side="left", padx=10)
            self.entries[key] = entry

        # TLS Toggle
        tls_row = ctk.CTkFrame(self.smtp_frame, fg_color="transparent")
        tls_row.pack(fill="x", padx=20, pady=10)
        self.tls_var = ctk.BooleanVar(value=bool(settings[5]))
        ctk.CTkSwitch(tls_row, text="Use TLS/SSL", variable=self.tls_var).pack(side="left", padx=150)

        # -----------------------------
        # 2. Microsoft 365 OAuth Frame
        # -----------------------------
        self.ms_frame = ctk.CTkFrame(self)

        # Account Info row
        ms_account_row = ctk.CTkFrame(self.ms_frame, fg_color="transparent")
        ms_account_row.pack(fill="x", padx=20, pady=(15, 5))
        ctk.CTkLabel(ms_account_row, text="Account:", width=150, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.ms_account_label = ctk.CTkLabel(ms_account_row, text="Not Connected", font=ctk.CTkFont(size=14))
        self.ms_account_label.pack(side="left", padx=10)

        # Status row
        ms_status_row = ctk.CTkFrame(self.ms_frame, fg_color="transparent")
        ms_status_row.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(ms_status_row, text="Status:", width=150, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.ms_status_badge = ctk.CTkLabel(ms_status_row, text="✗ Not Connected", text_color="gray", font=ctk.CTkFont(size=14, weight="bold"))
        self.ms_status_badge.pack(side="left", padx=10)

        # Action Buttons row
        self.ms_btn_row = ctk.CTkFrame(self.ms_frame, fg_color="transparent")
        self.ms_btn_row.pack(fill="x", padx=20, pady=(15, 20))
        
        self.ms_connect_btn = ctk.CTkButton(
            self.ms_btn_row, 
            text="Connect Microsoft Account", 
            fg_color="#0078D4", 
            hover_color="#106EBE",
            command=self._on_ms_connect
        )
        self.ms_connect_btn.pack(side="left", padx=(0, 10))

        self.ms_reconnect_btn = ctk.CTkButton(
            self.ms_btn_row, 
            text="Reconnect Account", 
            fg_color="#2b5797", 
            hover_color="#1e3e6b",
            command=self._on_ms_reconnect
        )

        self.ms_disconnect_btn = ctk.CTkButton(
            self.ms_btn_row, 
            text="Disconnect Account", 
            fg_color="#A80000", 
            hover_color="#7A0000",
            command=self._on_ms_disconnect
        )

        # Optional Entra Config row
        ms_config_frame = ctk.CTkFrame(self.ms_frame, fg_color="transparent")
        ms_config_frame.pack(fill="x", padx=20, pady=(5, 5))
        
        # Client ID input
        cid_row = ctk.CTkFrame(ms_config_frame, fg_color="transparent")
        cid_row.pack(fill="x", pady=3)
        ctk.CTkLabel(cid_row, text="App (Client) ID:", width=150, anchor="w").pack(side="left")
        self.ms_client_id_entry = ctk.CTkEntry(cid_row, width=320, placeholder_text="Enter Azure App Client ID")
        current_cid = settings[9] if len(settings) > 9 and settings[9] else ""
        self.ms_client_id_entry.insert(0, current_cid)
        self.ms_client_id_entry.pack(side="left", padx=10)
        self.entries["ms_client_id"] = self.ms_client_id_entry

        # Tenant ID input
        tid_row = ctk.CTkFrame(ms_config_frame, fg_color="transparent")
        tid_row.pack(fill="x", pady=3)
        ctk.CTkLabel(tid_row, text="Tenant ID (optional):", width=150, anchor="w").pack(side="left")
        self.ms_tenant_id_entry = ctk.CTkEntry(tid_row, width=320, placeholder_text="common (or your tenant ID)")
        current_tid = settings[10] if len(settings) > 10 and settings[10] else ""
        self.ms_tenant_id_entry.insert(0, current_tid)
        self.ms_tenant_id_entry.pack(side="left", padx=10)
        self.entries["ms_tenant_id"] = self.ms_tenant_id_entry

        # Explanatory note
        ms_note = ctk.CTkLabel(
            self.ms_frame, 
            text="Enter your Azure App Registration Client ID, save, then click Connect Account.",
            text_color="gray",
            font=ctk.CTkFont(size=12)
        )
        ms_note.pack(padx=20, pady=(5, 15), anchor="w")

        # -----------------------------
        # 3. Resend Settings Frame
        # -----------------------------
        self.resend_frame = ctk.CTkFrame(self)
        resend_fields = [
            ("Resend API Key", "resend_key", settings[7] if len(settings) > 7 else ""),
            ("From Email", "resend_from", settings[8] if len(settings) > 8 else ""),
        ]
        
        for i, (label, key, val) in enumerate(resend_fields):
            row = ctk.CTkFrame(self.resend_frame, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=5)
            
            ctk.CTkLabel(row, text=label, width=150, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, width=300)
            if key == "resend_key":
                entry.configure(show="*")
            entry.insert(0, str(val) if val else "")
            entry.pack(side="left", padx=10)
            self.entries[key] = entry

        # -----------------------------
        # 4. Custom Storage / Output Folder Frame
        # -----------------------------
        storage_frame = ctk.CTkFrame(self)
        storage_frame.pack(fill="x", pady=10)
        
        storage_row = ctk.CTkFrame(storage_frame, fg_color="transparent")
        storage_row.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(storage_row, text="Output Directory:", width=150, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
        
        saved_folder = settings[11] if len(settings) > 11 and settings[11] else ""
        self.output_folder_var = ctk.StringVar(value=saved_folder)
        
        self.output_folder_entry = ctk.CTkEntry(storage_row, textvariable=self.output_folder_var, width=340, placeholder_text="Default: Documents/Payslips or OneDrive/Documents/Payslips")
        self.output_folder_entry.pack(side="left", padx=10)
        
        ctk.CTkButton(storage_row, text="Browse Folder", width=110, command=self._browse_output_folder).pack(side="left", padx=5)

        # Show/Hide frames initially
        self._on_provider_change(self.provider_var.get())

        # Action Buttons (Save / Test)
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", pady=20)
        
        self.save_btn = ctk.CTkButton(btn_frame, text="Save Settings", command=self._save_settings)
        self.save_btn.pack(side="left", padx=10)
        
        self.test_btn = ctk.CTkButton(btn_frame, text="Test Connection", fg_color="gray", command=self._test_connection)
        self.test_btn.pack(side="left", padx=10)

    def _refresh_ms_ui(self):
        """Updates Microsoft 365 Account, Status, and Button display based on current connection."""
        status_info = self.ms_auth.get_connection_status()
        connected = status_info.get("connected", False)
        email = status_info.get("email", "")
        status_text = status_info.get("status_text", "Not Connected")
        is_expired = status_info.get("is_expired", False)

        if connected and not is_expired:
            self.ms_account_label.configure(text=email)
            self.ms_status_badge.configure(text="✓ Connected", text_color="#107C41")
            self.ms_connect_btn.pack_forget()
            self.ms_reconnect_btn.pack(side="left", padx=(0, 10))
            self.ms_disconnect_btn.pack(side="left", padx=(0, 10))
        elif connected and is_expired:
            self.ms_account_label.configure(text=email)
            self.ms_status_badge.configure(text="⚠ Connection Expired", text_color="#D83B01")
            self.ms_connect_btn.pack_forget()
            self.ms_reconnect_btn.pack(side="left", padx=(0, 10))
            self.ms_disconnect_btn.pack(side="left", padx=(0, 10))
        else:
            self.ms_account_label.configure(text="Not Connected")
            self.ms_status_badge.configure(text="✗ Not Connected", text_color="gray")
            self.ms_reconnect_btn.pack_forget()
            self.ms_disconnect_btn.pack_forget()
            self.ms_connect_btn.pack(side="left", padx=(0, 10))

    def _on_provider_change(self, value):
        self.smtp_frame.pack_forget()
        self.ms_frame.pack_forget()
        self.resend_frame.pack_forget()

        if value == "resend":
            self.resend_frame.pack(fill="x", pady=10)
        elif value == "microsoft":
            self._refresh_ms_ui()
            self.ms_frame.pack(fill="x", pady=10)
        else:
            self.smtp_frame.pack(fill="x", pady=10)

    def _on_ms_connect(self):
        if self.is_authenticating:
            return
        
        # Save any entered Client ID / Tenant ID from entries
        self._save_settings(silent=True)
        self.ms_auth = MicrosoftAuthService(self.db)

        self.is_authenticating = True
        self.ms_connect_btn.configure(state="disabled", text="Signing in via browser...")
        self.ms_status_badge.configure(text="⏳ Waiting for browser login...", text_color="#0078D4")

        def run_login():
            success, msg = self.ms_auth.connect_account()
            self.is_authenticating = False
            self.after(0, lambda: self._handle_ms_auth_result(success, msg))

        threading.Thread(target=run_login, daemon=True).start()

    def _on_ms_reconnect(self):
        if self.is_authenticating:
            return

        # Save any entered Client ID / Tenant ID from entries
        self._save_settings(silent=True)
        self.ms_auth = MicrosoftAuthService(self.db)

        self.is_authenticating = True
        self.ms_reconnect_btn.configure(state="disabled", text="Reconnecting...")
        self.ms_status_badge.configure(text="⏳ Waiting for browser login...", text_color="#0078D4")

        def run_reconnect():
            success, msg = self.ms_auth.reconnect_account()
            self.is_authenticating = False
            self.after(0, lambda: self._handle_ms_auth_result(success, msg))

        threading.Thread(target=run_reconnect, daemon=True).start()

    def _handle_ms_auth_result(self, success, msg):
        self.ms_connect_btn.configure(state="normal", text="Connect Microsoft Account")
        self.ms_reconnect_btn.configure(state="normal", text="Reconnect Account")
        self._refresh_ms_ui()
        if success:
            messagebox.showinfo("Microsoft OAuth", f"Account successfully connected:\n{msg}")
        else:
            messagebox.showerror("Authentication Failed", f"Could not complete Microsoft sign-in:\n{msg}")

    def _on_ms_disconnect(self):
        if messagebox.askyesno("Disconnect Account", "Are you sure you want to disconnect your Microsoft 365 account?"):
            success, msg = self.ms_auth.disconnect_account()
            self._refresh_ms_ui()
            if success:
                messagebox.showinfo("Disconnected", "Microsoft 365 account disconnected.")
            else:
                messagebox.showerror("Error", msg)

    def _browse_output_folder(self):
        folder = filedialog.askdirectory(title="Select Output Folder for Payslips")
        if folder:
            self.output_folder_var.set(folder)

    def _save_settings(self, silent=False):
        try:
            provider = self.provider_var.get()
            
            # Get existing settings as fallback
            curr = self.db.get_settings()
            default_host = curr[1] if curr else 'smtp.gmail.com'
            default_port = curr[2] if curr else 587
            default_email = curr[3] if curr else ''
            default_pass = curr[4] if curr else ''
            default_tls = curr[5] if curr else 1
            default_resend_key = curr[7] if curr and len(curr) > 7 else ''
            default_resend_from = curr[8] if curr and len(curr) > 8 else ''
            default_cid = curr[9] if curr and len(curr) > 9 else ''
            default_tid = curr[10] if curr and len(curr) > 10 else ''
            default_output = curr[11] if curr and len(curr) > 11 else ''

            host = self.entries.get('host').get() if self.entries.get('host') else default_host
            port_val = self.entries.get('port').get() if self.entries.get('port') else str(default_port)
            port = int(port_val) if port_val else 587
            email = self.entries.get('email').get() if self.entries.get('email') else default_email
            password = self.entries.get('password').get() if self.entries.get('password') else default_pass
            tls = 1 if self.tls_var.get() else 0
            
            resend_key = self.entries.get('resend_key').get() if self.entries.get('resend_key') else default_resend_key
            resend_from = self.entries.get('resend_from').get() if self.entries.get('resend_from') else default_resend_from

            ms_client_id = self.entries.get('ms_client_id').get().strip() if self.entries.get('ms_client_id') else default_cid
            ms_tenant_id = self.entries.get('ms_tenant_id').get().strip() if self.entries.get('ms_tenant_id') else default_tid
            output_folder = self.output_folder_var.get().strip()

            # If provider is Microsoft 365, ensure sender_email is populated from OAuth status
            if provider == "microsoft":
                status_info = self.ms_auth.get_connection_status()
                if status_info.get("email"):
                    email = status_info.get("email")
                host = "smtp.office365.com"
                port = 587
                password = ""
            
            self.db.update_settings(host, port, email, password, tls, provider, resend_key, resend_from, ms_client_id, ms_tenant_id, output_folder)
            self.ms_auth = MicrosoftAuthService(self.db)
            if not silent:
                messagebox.showinfo("Success", "Settings saved successfully")
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to save: {e}")

    def _test_connection(self):
        curr = self.db.get_settings()
        default_host = curr[1] if curr else 'smtp.gmail.com'
        default_port = curr[2] if curr else 587
        default_email = curr[3] if curr else ''
        default_pass = curr[4] if curr else ''
        default_tls = curr[5] if curr else 1
        default_resend_key = curr[7] if curr and len(curr) > 7 else ''
        default_resend_from = curr[8] if curr and len(curr) > 8 else ''

        host = self.entries.get('host').get() if self.entries.get('host') else default_host
        port_val = self.entries.get('port').get() if self.entries.get('port') else str(default_port)
        port = int(port_val) if port_val else 587
        email = self.entries.get('email').get() if self.entries.get('email') else default_email
        password = self.entries.get('password').get() if self.entries.get('password') else default_pass
        tls = self.tls_var.get()
        
        provider = self.provider_var.get()
        resend_key = self.entries.get('resend_key').get() if self.entries.get('resend_key') else default_resend_key
        resend_from = self.entries.get('resend_from').get() if self.entries.get('resend_from') else default_resend_from
        
        success, msg = EmailSender.test_connection(
            host, port, email, password, tls, 
            provider=provider, 
            resend_key=resend_key, 
            resend_from=resend_from, 
            db_service=self.db
        )
        if success:
            messagebox.showinfo("Test Success", msg)
        else:
            messagebox.showerror("Test Failed", msg)
