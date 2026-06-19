import io
from typing import Dict, Any, Union
import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image

def extract_text(file_bytes: bytes, content_type: str) -> Dict[str, Any]:
    """
    Extracts text from PDF or Image files.
    Returns:
    {
        "text": str,
        "confidence": float,
        "method": "pdfplumber" | "tesseract" | "unsupported"
    }
    """
    
    # 1. Handle PDF
    if "pdf" in content_type.lower():
        # Try pdfplumber first (fast, works on selectable text)
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                full_text = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text.append(text)
                
                extracted = "\n".join(full_text).strip()
                if extracted and len(extracted) > 50:
                    # High confidence if pdfplumber found substantial text layer
                    return {
                        "text": extracted,
                        "confidence": 1.0,
                        "method": "pdfplumber"
                    }
        except Exception:
            pass # Fall back to OCR if pdfplumber fails
            
        # Fallback to Tesseract OCR for scanned PDFs
        try:
            images = convert_from_bytes(file_bytes)
            full_text = []
            total_confidence = 0
            word_count = 0
            
            for img in images:
                # Get data for confidence scores
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                for i, word in enumerate(data['text']):
                    if word.strip():
                        conf = int(data['conf'][i])
                        if conf >= 0: # -1 means no confidence value
                            total_confidence += conf
                            word_count += 1
                
                text = pytesseract.image_to_string(img)
                full_text.append(text)
                
            avg_conf = (total_confidence / word_count) if word_count > 0 else 0
            # Scale to 0.0 - 1.0
            confidence_score = avg_conf / 100.0
            
            return {
                "text": "\n".join(full_text).strip(),
                "confidence": confidence_score,
                "method": "tesseract"
            }
        except Exception as e:
            print(f"OCR Failed for PDF: {e}")
            return {"text": "", "confidence": 0.0, "method": "tesseract"}

    # 2. Handle Images directly
    elif "image" in content_type.lower():
        try:
            img = Image.open(io.BytesIO(file_bytes))
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            
            total_confidence = 0
            word_count = 0
            
            for i, word in enumerate(data['text']):
                if word.strip():
                    conf = int(data['conf'][i])
                    if conf >= 0:
                        total_confidence += conf
                        word_count += 1
                        
            text = pytesseract.image_to_string(img)
            avg_conf = (total_confidence / word_count) if word_count > 0 else 0
            
            return {
                "text": text.strip(),
                "confidence": avg_conf / 100.0,
                "method": "tesseract"
            }
        except Exception as e:
            print(f"OCR Failed for Image: {e}")
            return {"text": "", "confidence": 0.0, "method": "tesseract"}
            
    # Unsupported format
    return {
        "text": "",
        "confidence": 0.0,
        "method": "unsupported"
    }
