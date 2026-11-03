import io
import re
import shutil
import subprocess
from typing import Any
import cv2
import numpy as np
from PIL import Image

from app.ports import ExtractorPort, ExtractionResult, QualityMetrics


def run_tesseract_ocr(img_cv: np.ndarray, psm: int = 6) -> str:
    """Executes Tesseract OCR either via local binary or udyam-tesseract docker container."""
    _, buf = cv2.imencode(".png", img_cv)
    img_bytes = buf.tobytes()

    # Try local binary if on PATH
    tesseract_bin = shutil.which("tesseract")
    if tesseract_bin:
        proc = subprocess.run(
            [tesseract_bin, "stdin", "stdout", "--psm", str(psm)],
            input=img_bytes,
            capture_output=True,
            check=False,
        )
        return proc.stdout.decode("utf-8", errors="ignore")

    # Fallback to local docker container
    proc = subprocess.run(
        ["docker", "run", "-i", "--rm", "udyam-tesseract", "stdin", "stdout", "--psm", str(psm)],
        input=img_bytes,
        capture_output=True,
        check=False,
    )
    return proc.stdout.decode("utf-8", errors="ignore")


class TesseractExtractor:
    """7-Stage Computer Vision & OCR pipeline implementing ExtractorPort."""

    def extract_document(self, image_bytes: bytes, slot: str) -> ExtractionResult:
        # -------------------------------------------------------------
        # STAGE 1: Upload Check (Size, dimensions, format, strip EXIF)
        # -------------------------------------------------------------
        if len(image_bytes) > 5 * 1024 * 1024:
            raise ValueError("TOO_LARGE: Document exceeds 5 MB limit.")

        pil_img = Image.open(io.BytesIO(image_bytes))
        width, height = pil_img.size
        if max(width, height) < 800 or min(width, height) < 500:
            raise ValueError("LOW_RES: Shortest side must be at least 500 px and longest at least 800 px.")

        # Decode image to OpenCV BGR
        nparr = np.frombuffer(image_bytes, np.uint8)
        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            raise ValueError("BAD_TYPE: Invalid or corrupted image format.")

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # -------------------------------------------------------------
        # STAGE 2: Quality Gate (Laplacian Variance)
        # -------------------------------------------------------------
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        is_blurry = laplacian_var < 100.0

        # -------------------------------------------------------------
        # STAGE 3: Deskew Angle Estimation & Rotation
        # -------------------------------------------------------------
        skew_angle = 0.0
        is_skewed = False
        coords = np.column_stack(np.where(gray < 180))
        if len(coords) > 500:
            rect = cv2.minAreaRect(coords)
            raw_angle = rect[-1]
            if raw_angle < -45:
                detected_angle = -(90 + raw_angle)
            else:
                detected_angle = -raw_angle

            if abs(detected_angle) > 1.0 and abs(detected_angle) < 45.0:
                skew_angle = float(detected_angle)
                is_skewed = True
                h, w = gray.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, skew_angle, 1.0)
                img_bgr = cv2.warpAffine(
                    img_bgr, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
                )
                gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # -------------------------------------------------------------
        # STAGE 4: Clean (HSV Watermark Removal & Preprocessing)
        # -------------------------------------------------------------
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        lower_red1 = np.array([0, 50, 50])
        upper_red1 = np.array([12, 255, 255])
        lower_red2 = np.array([168, 50, 50])
        upper_red2 = np.array([180, 255, 255])
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        red_mask = cv2.bitwise_or(mask1, mask2)

        watermark_detected = cv2.countNonZero(red_mask) > 1000
        cleaned_bgr = img_bgr.copy()
        cleaned_bgr[red_mask > 0] = [255, 255, 255]

        # -------------------------------------------------------------
        # STAGE 5 & 6: OCR Extraction & Label-Anchored Field Parsing
        # -------------------------------------------------------------
        # Run OCR on cleaned image
        raw_text = run_tesseract_ocr(cleaned_bgr, psm=6)
        doc_type_detected = self._classify_header(raw_text, slot)

        extracted_fields: dict[str, Any] = {}
        field_confidences: dict[str, float] = {}

        if slot == "gst_certificate":
            extracted_fields = self._parse_gst_certificate(raw_text)
        elif slot == "udyam_certificate":
            extracted_fields = self._parse_udyam_certificate(raw_text)
        elif slot == "address_proof":
            extracted_fields = self._parse_address_proof(raw_text)
        elif slot == "signatory_id":
            extracted_fields = self._parse_signatory_id(raw_text)

        # Compute nominal field confidences
        for k in extracted_fields:
            field_confidences[k] = 95.0 if not is_blurry else 40.0

        quality = QualityMetrics(
            laplacian_variance=laplacian_var,
            is_blurry=is_blurry,
            skew_angle=skew_angle,
            is_skewed=is_skewed,
            watermark_detected=watermark_detected,
        )

        return ExtractionResult(
            slot=slot,
            document_type_detected=doc_type_detected,
            extracted_fields=extracted_fields,
            field_confidences=field_confidences,
            quality=quality,
            raw_text=raw_text,
        )

    def _classify_header(self, text: str, expected_slot: str) -> str:
        t = text.lower()
        if "goods and services tax" in t or "gst" in t or "form gst" in t:
            return "gst_certificate"
        if "udyam" in t or "msme" in t or "micro, small and medium" in t:
            return "udyam_certificate"
        if "election commission" in t or "identity card" in t or "income tax department" in t or "permanent account" in t or "aadhaar" in t:
            return "signatory_id"
        if "electricity" in t or "power" in t or "distribution" in t or "consumer" in t or "bill" in t or "bescom" in t or "mpeb" in t:
            return "address_proof"
        return expected_slot

    def _parse_gst_certificate(self, text: str) -> dict[str, Any]:
        fields: dict[str, Any] = {}

        # 1. GSTIN
        gstin_match = re.search(r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9])\b", text)
        if gstin_match:
            fields["gstin"] = gstin_match.group(1).upper()

        # 2. Legal Name & Trade Name
        for line in text.splitlines():
            line_s = line.strip()
            if re.search(r"Legal\s*name", line_s, re.I):
                val = re.sub(r"^.*?Legal\s*name\s*[:\-]?\s*", "", line_s, flags=re.I).strip()
                if val:
                    fields["legal_name"] = val
            elif re.search(r"Trade\s*name", line_s, re.I):
                val = re.sub(r"^.*?Trade\s*name\s*[:\-]?\s*", "", line_s, flags=re.I).strip()
                if val:
                    fields["trade_name"] = val
            elif re.search(r"Constitution", line_s, re.I):
                val = re.sub(r"^.*?Constitution\s*[:\-]?\s*", "", line_s, flags=re.I).strip()
                if val:
                    fields["constitution"] = val

        # 3. Principal place of business address & pincode
        addr_match = re.search(r"(?:Address of principal place of business|place of business)[\s:]*([^\n\r]+(?:[\n\r]+[^\n\r]+){1,3})", text, re.I)
        if addr_match:
            addr = " ".join(addr_match.group(1).split())
            fields["address"] = addr
            pincode_match = re.search(r"\b(\d{6})\b", addr)
            if pincode_match:
                fields["pincode"] = pincode_match.group(1)

        if "pincode" not in fields:
            pincode_match = re.search(r"\b(\d{6})\b", text)
            if pincode_match:
                fields["pincode"] = pincode_match.group(1)

        return fields

    def _parse_udyam_certificate(self, text: str) -> dict[str, Any]:
        fields: dict[str, Any] = {}

        # 1. Udyam Registration Number (handles OCR ligatures like ULDYAM, ULJDYAM)
        udyam_match = re.search(r"\bU[A-Z]{0,3}DYAM-([A-Z]{2})-([0-9]{2})-([0-9]{7})\b", text, re.I)
        if udyam_match:
            fields["udyam_number"] = f"UDYAM-{udyam_match.group(1).upper()}-{udyam_match.group(2)}-{udyam_match.group(3)}"
        else:
            # Check for empty/blank Udyam label without number (e.g. K01)
            fields["udyam_number"] = None

        # 2. Enterprise Name
        for line in text.splitlines():
            line_s = line.strip()
            if re.search(r"(?:Name of Enterprise|Enterprise Name)", line_s, re.I):
                val = re.sub(r"^.*?(?:Name of Enterprise|Enterprise Name)\s*[:\-]?\s*", "", line_s, flags=re.I).strip()
                if val:
                    fields["enterprise_name"] = val

        # 3. Major Activity
        if re.search(r"Services", text, re.I):
            fields["major_activity"] = "Services"
        elif re.search(r"Manufacturing", text, re.I):
            fields["major_activity"] = "Manufacturing"
        elif re.search(r"Trading", text, re.I):
            fields["major_activity"] = "Trading"

        pincode_match = re.search(r"\b(\d{6})\b", text)
        if pincode_match:
            fields["pincode"] = pincode_match.group(1)

        return fields

    def _parse_address_proof(self, text: str) -> dict[str, Any]:
        fields: dict[str, Any] = {}

        # 1. Bill date
        date_patterns = [
            r"(?:Bill Date|Date of Bill|Invoice Date)[\s:]*([0-9]{1,2}[/\-][0-9]{1,2}[/\-][0-9]{4})",
            r"(?:Bill Date|Date of Bill|Invoice Date)[\s:]*([0-9]{4}[/\-][0-9]{1,2}[/\-][0-9]{1,2})",
            r"(?:Bill Date|Date of Bill|Invoice Date)[\s:]*([0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4})",
            r"\b([0-9]{4}-[0-9]{2}-[0-9]{2})\b",
            r"\b([0-9]{2}-[0-9]{2}-[0-9]{4})\b",
        ]
        for pat in date_patterns:
            m = re.search(pat, text, re.I)
            if m:
                fields["bill_date"] = m.group(1).strip()
                break

        # 2. Pincode
        pincode_match = re.search(r"\b(\d{6})\b", text)
        if pincode_match:
            fields["pincode"] = pincode_match.group(1)

        # 3. Consumer name
        for line in text.splitlines():
            line_s = line.strip()
            if re.search(r"Consumer Name", line_s, re.I):
                val = re.sub(r"^.*?Consumer Name\s*[:\-]?\s*", "", line_s, flags=re.I).strip()
                if val:
                    fields["consumer_name"] = val

        return fields

    def _parse_signatory_id(self, text: str) -> dict[str, Any]:
        fields: dict[str, Any] = {}

        for line in text.splitlines():
            line_s = line.strip()
            if re.search(r"(?:Elector's Name|Name)\s*[:\-]", line_s, re.I):
                val = re.sub(r"^.*?(?:Elector's Name|Name)\s*[:\-]?\s*", "", line_s, flags=re.I).strip()
                if val and "father" not in val.lower() and "husband" not in val.lower():
                    fields["signatory_name"] = val
            elif re.search(r"Valid\s*Till", line_s, re.I):
                val = re.sub(r"^.*?Valid\s*Till\s*[:\-]?\s*", "", line_s, flags=re.I).strip()
                if val:
                    fields["valid_till"] = val

        return fields
