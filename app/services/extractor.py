import re
import fitz

# RapidOCR engine for image/scanned PDF recognition
try:
    from rapidocr_onnxruntime import RapidOCR
    OCR_ENGINE = RapidOCR()
except Exception:
    OCR_ENGINE = None

class Extractor:
    def __init__(self):
        # PAN Regex: 5 letters, 4 digits, 1 letter
        self.pan_regex = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b')
        # UAN Regex: 12 digits
        self.uan_regex = re.compile(r'\b\d{12}\b')
        # Emp Code Regex patterns
        self.code_patterns = [
            re.compile(r"Emp(?:loyee)?\s*Code\s*[:\-]?\s*([A-Za-z0-9\-\s]+)", re.IGNORECASE),
            re.compile(r"\bCode\s*[:\-]?\s*([A-Za-z0-9\-\s]+)", re.IGNORECASE),
        ]
        # Name Regex patterns
        self.name_patterns = [
            re.compile(r"Employee\s+Name\s*[:\-]?\s*([A-Za-z\s\.]+)", re.IGNORECASE),
            re.compile(r"\bName\s*[:\-]?\s*([A-Za-z\s\.]+)", re.IGNORECASE),
            re.compile(r"Emp\s+Name\s*[:\-]?\s*([A-Za-z\s\.]+)", re.IGNORECASE),
        ]

    def _parse_text(self, text):
        """Helper to find Code, PAN, UAN, and Name from a block of text."""
        code_val = None
        for pattern in self.code_patterns:
            match = pattern.search(text)
            if match:
                raw_code = match.group(1).split("\n")[0].split("\r")[0].strip()
                for delimiter in ["PAN", "UAN", "Grade", "Name", "Department", "Designation", "DOJ", "F/Name", "ESIC", "PF", "Branch"]:
                    if delimiter.lower() in raw_code.lower():
                        raw_code = re.split(re.escape(delimiter), raw_code, flags=re.IGNORECASE)[0].strip()
                if len(raw_code) >= 1:
                    code_val = raw_code.strip()
                    break

        pan_val = None
        pan_match = self.pan_regex.search(text)
        if pan_match:
            pan_val = pan_match.group(0)

        uan_val = None
        uan_match = self.uan_regex.search(text)
        if uan_match:
            uan_val = uan_match.group(0)

        name_val = None
        for pattern in self.name_patterns:
            match = pattern.search(text)
            if match:
                raw_name = match.group(1).split("\n")[0].split("\r")[0].strip()
                for delimiter in ["DEDUCTIONS", "EARNINGS", "Department", "Designation", "Grade", "PAN", "UAN", "P.F.", "PF", "Code", "F/Name", "Father's Name", "ESIC", "DOJ", "Branch"]:
                    if delimiter.lower() in raw_name.lower():
                        raw_name = re.split(re.escape(delimiter), raw_name, flags=re.IGNORECASE)[0].strip()
                if len(raw_name) >= 2 and not raw_name.lower().startswith("of the month"):
                    name_val = raw_name
                    break

        return code_val, name_val, pan_val, uan_val

    def extract_details(self, pdf_path):
        """
        Extracts Code, PAN, UAN, and Name from a single-page PDF.
        Pipeline:
        1. Fast Path: Direct PDF structured table & text parsing.
        2. Fallback Path: Offline OCR for scanned/image-flattened PDFs.
        """
        doc = fitz.open(pdf_path)
        text = ""
        table_text = ""
        for page in doc:
            try:
                tables = page.find_tables()
                for t in tables:
                    for row in t.extract():
                        for cell in row:
                            if cell:
                                table_text += str(cell) + "\n"
            except Exception:
                pass
            text += page.get_text() + "\n"

        full_text = table_text + "\n" + text
        code_val, name_val, pan_val, uan_val = self._parse_text(full_text)
        source = "pdf_text"

        # Fallback to OCR if key fields are missing or PDF has minimal digital text
        if not (code_val and pan_val and uan_val and name_val):
            if OCR_ENGINE and len(doc) > 0:
                try:
                    pix = doc[0].get_pixmap(dpi=200)
                    img_bytes = pix.tobytes("png")
                    ocr_res, _ = OCR_ENGINE(img_bytes)
                    if ocr_res:
                        ocr_lines = [box[1] for box in ocr_res]
                        ocr_text = "\n".join(ocr_lines)
                        c_ocr, n_ocr, p_ocr, u_ocr = self._parse_text(ocr_text)
                        code_val = code_val or c_ocr
                        name_val = name_val or n_ocr
                        pan_val = pan_val or p_ocr
                        uan_val = uan_val or u_ocr
                        full_text += "\n" + ocr_text
                        source = "ocr"
                except Exception:
                    pass

        doc.close()

        return {
            "code": code_val,
            "name": name_val,
            "pan": pan_val,
            "uan": uan_val,
            "raw_text": full_text,
            "extraction_source": source
        }

    @staticmethod
    def mask_pan(pan):
        if not pan or len(pan) < 10: return pan
        return f"{pan[:5]}****{pan[-1]}"

    @staticmethod
    def mask_uan(uan):
        if not uan or len(uan) < 12: return uan
        return f"****{uan[-6:]}"
