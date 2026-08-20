import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
import re
from datetime import datetime, date
from services.pdf_splitter import PDFSplitter
from services.extractor import Extractor
from services.matcher import Matcher
from services.email_sender import EmailSender

class UploadScreen(ctk.CTkFrame):
    MONTHS = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    def __init__(self, parent, db_service):
        super().__init__(parent, fg_color="transparent")
        self.db = db_service
        self.splitter = PDFSplitter()
        self.extractor = Extractor()
        self.matcher = Matcher(self.db)
        self.is_processing = False
        self._setup_ui()

    def _get_default_month_year(self):
        """Calculates the previous month and corresponding year by default."""
        today = date.today()
        # If current month is January, previous month is December of previous year
        if today.month == 1:
            prev_month_idx = 12
            prev_year = today.year - 1
        else:
            prev_month_idx = today.month - 1
            prev_year = today.year
        return self.MONTHS[prev_month_idx - 1], str(prev_year)

    def _setup_ui(self):
        # Header
        header = ctk.CTkLabel(self, text="Upload & Process Payslips", font=ctk.CTkFont(size=24, weight="bold"))
        header.pack(pady=(0, 15), anchor="w")

        # Period Selection Frame (Month & Year Dropdowns)
        period_frame = ctk.CTkFrame(self)
        period_frame.pack(fill="x", pady=(0, 10), padx=5)

        default_month, default_year = self._get_default_month_year()

        current_year = date.today().year
        year_options = [str(y) for y in range(current_year - 3, current_year + 4)]

        # Month Selector
        month_label = ctk.CTkLabel(period_frame, text="Payslip Month:", font=ctk.CTkFont(size=13, weight="bold"))
        month_label.pack(side="left", padx=(15, 5), pady=12)

        self.month_var = ctk.StringVar(value=default_month)
        self.month_dropdown = ctk.CTkOptionMenu(
            period_frame,
            values=self.MONTHS,
            variable=self.month_var,
            width=140
        )
        self.month_dropdown.pack(side="left", padx=(0, 20), pady=12)

        # Year Selector
        year_label = ctk.CTkLabel(period_frame, text="Payslip Year:", font=ctk.CTkFont(size=13, weight="bold"))
        year_label.pack(side="left", padx=(5, 5), pady=12)

        self.year_var = ctk.StringVar(value=default_year)
        self.year_dropdown = ctk.CTkOptionMenu(
            period_frame,
            values=year_options,
            variable=self.year_var,
            width=110
        )
        self.year_dropdown.pack(side="left", padx=(0, 15), pady=12)

        # Upload Area
        upload_frame = ctk.CTkFrame(self)
        upload_frame.pack(fill="x", pady=5, padx=5)
        
        self.file_path_var = ctk.StringVar(value="No file selected")
        self.path_entry = ctk.CTkEntry(upload_frame, textvariable=self.file_path_var, width=380, state="disabled")
        self.path_entry.pack(side="left", padx=10, pady=15)
        
        self.browse_btn = ctk.CTkButton(upload_frame, text="Browse PDF", command=self._browse_file)
        self.browse_btn.pack(side="left", padx=10)
        
        self.process_btn = ctk.CTkButton(upload_frame, text="Start Processing", fg_color="green", hover_color="darkgreen", command=self._start_processing)
        self.process_btn.pack(side="right", padx=10)

        # Progress Area
        self.progress_frame = ctk.CTkFrame(self)
        self.progress_frame.pack(fill="x", pady=15)
        
        self.status_label = ctk.CTkLabel(self.progress_frame, text="Ready to process", font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=(10, 5))
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=20, pady=10)
        
        # Log Area
        log_label = ctk.CTkLabel(self, text="Live Processing Logs", font=ctk.CTkFont(size=16, weight="bold"))
        log_label.pack(pady=(5, 5), anchor="w")
        
        self.log_textbox = ctk.CTkTextbox(self, height=260)
        self.log_textbox.pack(fill="both", expand=True)

    def _browse_file(self):
        filename = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if filename:
            self.file_path_var.set(filename)

    def _log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_textbox.insert("end", f"[{timestamp}] {message}\n")
        self.log_textbox.see("end")

    def _start_processing(self):
        pdf_path = self.file_path_var.get()
        if not pdf_path or pdf_path == "No file selected" or not os.path.exists(pdf_path):
            messagebox.showerror("Error", "Please select a valid PDF file.")
            return

        if self.is_processing:
            return

        selected_month = self.month_var.get()
        selected_year = self.year_var.get()
        selected_period = f"{selected_month} {selected_year}"

        self.is_processing = True
        self.process_btn.configure(state="disabled")
        self.browse_btn.configure(state="disabled")
        self.month_dropdown.configure(state="disabled")
        self.year_dropdown.configure(state="disabled")
        self.log_textbox.delete("1.0", "end")
        
        # Run in background
        thread = threading.Thread(target=self._run_task, args=(pdf_path, selected_period))
        thread.start()

    def _run_task(self, pdf_path, month_year):
        try:
            self._log(f"Starting processing: {os.path.basename(pdf_path)}")
            self._log(f"Target Period: {month_year}")
            
            # 1. Split PDF into Documents/Payslips/<Month Year>/
            self.status_label.configure(text=f"Splitting PDF for {month_year}...")
            split_files = self.splitter.split_pdf(pdf_path, month_year_folder=month_year)
            self._log(f"Split into {len(split_files)} individual pages under Documents/Payslips/{month_year}/.")
            
            # 2. Process each page
            total = len(split_files)
            success_count = 0
            
            settings = self.db.get_settings()
            email_sender = EmailSender(settings, db_service=self.db)

            for i, file in enumerate(split_files):
                progress = (i + 1) / total
                self.progress_bar.set(progress)
                
                # Extract
                details = self.extractor.extract_details(file)
                ext_name = details.get("name")
                ext_source = details.get("extraction_source", "pdf_text")
                if ext_source == "ocr":
                    self._log(f"Page {i+1}: Scanned/Image PDF detected, extracted details using OCR.")
                self.status_label.configure(text=f"Processing: {ext_name or f'Page {i+1}'}")
                
                # Match
                match_status, emp = self.matcher.match_employee(details)
                
                if match_status == 'MATCH':
                    # emp: (id, emp_id, name, email, dept, pan, uan, created_at)
                    emp_id = emp[1]
                    emp_name = emp[2]
                    emp_email = emp[3]
                    
                    self._log(f"Matched: {emp_name} ({emp_id})")
                    
                    # Sanitize filename for Windows: "Employee Name - EMP Code - Month Year.pdf"
                    clean_emp_name = re.sub(r'[\\/*?:"<>|]', "", emp_name).strip()
                    clean_emp_id = re.sub(r'[\\/*?:"<>|]', "", emp_id).strip()
                    clean_month_year = re.sub(r'[\\/*?:"<>|]', "", month_year).strip()
                    renamed_filename = f"{clean_emp_name} - {clean_emp_id} - {clean_month_year}.pdf"
                    
                    new_pdf_path = os.path.join(os.path.dirname(file), renamed_filename)
                    try:
                        if os.path.exists(new_pdf_path) and os.path.abspath(new_pdf_path) != os.path.abspath(file):
                            os.remove(new_pdf_path)
                        os.rename(file, new_pdf_path)
                        file = new_pdf_path
                    except Exception as e:
                        self._log(f"Warning: Could not rename PDF: {e}")

                    # Send Email
                    sent, msg = email_sender.send_payslip(emp_email, emp_name, month_year, file)
                    if sent:
                        self.db.add_log(emp_id, ext_name, details['pan'], details['uan'], 'SENT', pdf_path=file)
                        self._log(f"Email sent to {emp_email} for {month_year}")
                        success_count += 1
                    else:
                        self.db.add_log(emp_id, ext_name, details['pan'], details['uan'], 'FAILED', error=msg, pdf_path=file)
                        self._log(f"Failed to send to {emp_email}: {msg}")
                
                elif match_status == 'CONFLICT':
                    self.db.add_log(details.get('code'), ext_name, details['pan'], details['uan'], 'CONFLICT', error="Multiple matches found", pdf_path=file)
                    self._log(f"Conflict: Multiple employees match {ext_name or details['pan'] or details.get('code')}")
                
                else: # UNMATCHED
                    self.db.add_log(details.get('code'), ext_name, details['pan'], details['uan'], 'UNMATCHED', error="No employee found in database", pdf_path=file)
                    self._log(f"Unmatched: No record found for {ext_name or details['pan'] or details.get('code') or 'Unknown'}")

            self._log(f"Task completed. {success_count}/{total} processed successfully.")
            self.status_label.configure(text="Processing Complete")
            
        except Exception as e:
            self._log(f"Critical Error: {str(e)}")
            self.status_label.configure(text="Processing Failed")
        finally:
            self.is_processing = False
            self.process_btn.configure(state="normal")
            self.browse_btn.configure(state="normal")
            self.month_dropdown.configure(state="normal")
            self.year_dropdown.configure(state="normal")
