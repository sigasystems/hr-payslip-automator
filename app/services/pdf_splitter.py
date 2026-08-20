import fitz  # PyMuPDF
import os
import platform
from pathlib import Path

def get_user_documents_dir():
    """
    Returns the real Windows user Documents directory,
    even when redirected to OneDrive/Documents or custom locations.
    """
    if platform.system() == "Windows":
        try:
            import ctypes.wintypes
            CSIDL_PERSONAL = 5  # My Documents folder
            SHGFP_TYPE_CURRENT = 0
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)
            if buf.value and os.path.exists(buf.value):
                return buf.value
        except Exception:
            pass

    # Fallback to standard ~/Documents
    docs_standard = os.path.join(os.path.expanduser("~"), "Documents")
    if os.path.exists(docs_standard):
        return docs_standard

    # Fallback to OneDrive/Documents if present
    onedrive_docs = os.path.join(os.path.expanduser("~"), "OneDrive", "Documents")
    if os.path.exists(onedrive_docs):
        return onedrive_docs

    return os.path.expanduser("~")

class PDFSplitter:
    def __init__(self, output_dir=None):
        if output_dir is None:
            docs_dir = get_user_documents_dir()
            self.base_dir = os.path.join(docs_dir, "Payslips")
        else:
            self.base_dir = output_dir
            
        os.makedirs(self.base_dir, exist_ok=True)

    def split_pdf(self, input_pdf_path, month_year_folder=None):
        """
        Splits a multi-page PDF into individual pages stored under Documents/Payslips/<Month Year>/.
        Returns a list of paths to the individual PDF files.
        """
        if month_year_folder:
            target_dir = os.path.join(self.base_dir, month_year_folder)
        else:
            target_dir = self.base_dir

        os.makedirs(target_dir, exist_ok=True)

        doc = fitz.open(input_pdf_path)
        split_files = []
        
        for page_num in range(len(doc)):
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            
            output_filename = f"page_{page_num + 1}.pdf"
            output_path = os.path.join(target_dir, output_filename)
            
            new_doc.save(output_path)
            new_doc.close()
            split_files.append(output_path)
            
        doc.close()
        return split_files
