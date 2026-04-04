"""
PDF Watermark utilities for adding QR code to downloaded documents
"""
import io
import os
from datetime import datetime
from PIL import Image
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from django.conf import settings


def scan_pdf_for_qr_code(pdf_path, expected_qr_data=None):
    """
    Scan a PDF file for QR codes and optionally verify they match expected data
    
    Args:
        pdf_path: Path to the PDF file
        expected_qr_data: Optional string to match against found QR codes
    
    Returns:
        dict: {
            'found': bool,           # Whether any QR code was found
            'matched': bool,         # Whether QR code matched expected data
            'qr_data': str,          # The data from the QR code
            'message': str           # Status message
        }
    """
    import sys
    
    # Try PyMuPDF first (doesn't require Poppler), then fall back to pdf2image
    pymupdf_available = False
    pyzbar_available = False
    opencv_available = False
    
    # Check if PyMuPDF is available
    try:
        import fitz  # PyMuPDF
        pymupdf_available = True
    except ImportError:
        pass
    
    # Check if pyzbar is available
    if pymupdf_available:
        try:
            import pyzbar
            # Test if pyzbar actually works (DLL check)
            test_img = Image.new('L', (100, 100))
            pyzbar.decode(test_img)
            pyzbar_available = True
        except Exception as e:
            # pyzbar might be installed but DLL missing
            pass
    
    # Try OpenCV as fallback (always check, not just if pyzbar unavailable)
    try:
        import cv2
        import numpy as np
        opencv_available = True
    except ImportError:
        pass
    
    if not pyzbar_available and not opencv_available:
        return {
            'found': False,
            'matched': False,
            'qr_data': None,
            'message': 'QR scanning libraries not properly installed. Skipping QR verification. Please install pyzbar with dependencies or opencv-python.'
        }
    
    if not os.path.exists(pdf_path):
        return {
            'found': False,
            'matched': False,
            'qr_data': None,
            'message': 'PDF file not found.'
        }
    
    # Helper function to check if QR data matches expected
    def check_qr_match(qr_data, expected_qr_data, page_num):
        if expected_qr_data:
            if expected_qr_data in qr_data:
                return {
                    'found': True,
                    'matched': True,
                    'qr_data': qr_data,
                    'message': f'QR code found and matched on page {page_num + 1}'
                }
            else:
                return {
                    'found': True,
                    'matched': False,
                    'qr_data': qr_data,
                    'message': f'QR code found but does not match file. Expected: {expected_qr_data}, Found: {qr_data[:50]}...'
                }
        else:
            return {
                'found': True,
                'matched': True,
                'qr_data': qr_data,
                'message': f'QR code found on page {page_num + 1}'
            }
    
    try:
        # Convert PDF pages to images using PyMuPDF with higher resolution
        if pymupdf_available:
            try:
                doc = fitz.open(pdf_path)
                images = []
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    # Use 3x resolution for better QR detection
                    pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    images.append((page_num, img))
                doc.close()
            except Exception as e:
                return {
                    'found': False,
                    'matched': False,
                    'qr_data': None,
                    'message': f'Error reading PDF with PyMuPDF: {str(e)}'
                }
        else:
            return {
                'found': False,
                'matched': False,
                'qr_data': None,
                'message': 'PyMuPDF not installed. Please install pymupdf for PDF scanning.'
            }
        
        # Try multiple preprocessing methods and both detectors
        for page_num, image in images:
            
            # Method 1: Try OpenCV first (usually more reliable)
            if opencv_available:
                try:
                    import cv2
                    import numpy as np
                    
                    # Convert PIL to OpenCV format
                    cv_image = cv2.cvtColor(np.array(image.convert('RGB')), cv2.COLOR_RGB2BGR)
                    
                    # Try multiple approaches with OpenCV
                    
                    # Approach 1a: Direct detection on grayscale
                    gray_cv = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
                    qr_detector = cv2.QRCodeDetector()
                    
                    # Try detectAndDecodeMulti first
                    retval, decoded_info, points, straight_qrcode = qr_detector.detectAndDecodeMulti(gray_cv)
                    
                    if retval and decoded_info is not None and len(decoded_info) > 0:
                        for qr_data in decoded_info:
                            if qr_data and len(qr_data) > 0:
                                result = check_qr_match(qr_data, expected_qr_data, page_num)
                                if result['found']:
                                    return result
                    
                    # Approach 1b: Try detectAndDecode (single QR)
                    retval, decoded_info = qr_detector.detectAndDecode(gray_cv)
                    if retval and decoded_info and len(decoded_info) > 0:
                        result = check_qr_match(decoded_info, expected_qr_data, page_num)
                        if result['found']:
                            return result
                    
                    # Approach 1c: Try on color image
                    retval, decoded_info, points, straight_qrcode = qr_detector.detectAndDecodeMulti(cv_image)
                    
                    if retval and decoded_info is not None and len(decoded_info) > 0:
                        for qr_data in decoded_info:
                            if qr_data and len(qr_data) > 0:
                                result = check_qr_match(qr_data, expected_qr_data, page_num)
                                if result['found']:
                                    return result
                    
                    # Approach 1d: Try with image preprocessing (contrast enhancement)
                    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                    enhanced = clahe.apply(gray_cv)
                    retval, decoded_info, points, straight_qrcode = qr_detector.detectAndDecodeMulti(enhanced)
                    
                    if retval and decoded_info is not None and len(decoded_info) > 0:
                        for qr_data in decoded_info:
                            if qr_data and len(qr_data) > 0:
                                result = check_qr_match(qr_data, expected_qr_data, page_num)
                                if result['found']:
                                    return result
                                
                except Exception as e:
                    # OpenCV failed, continue to try pyzbar
                    pass
            
            # Method 2: Try pyzbar
            if pyzbar_available:
                try:
                    import pyzbar
                    
                    # Try multiple image formats
                    for color_mode in ['L', 'RGB']:
                        if color_mode == 'L':
                            gray_image = image.convert('L')
                        else:
                            gray_image = image.convert('RGB')
                        
                        # Decode QR codes in the image
                        decoded_objects = pyzbar.decode(gray_image)
                        
                        for obj in decoded_objects:
                            qr_data = obj.data.decode('utf-8')
                            result = check_qr_match(qr_data, expected_qr_data, page_num)
                            if result['found']:
                                return result
                            
                        # Also try with ZBarSymbol.QRCODE explicitly
                        decoded_objects = pyzbar.decode(gray_image, symbols=[pyzbar.ZBarSymbol.QRCODE])
                        
                        for obj in decoded_objects:
                            qr_data = obj.data.decode('utf-8')
                            result = check_qr_match(qr_data, expected_qr_data, page_num)
                            if result['found']:
                                return result
                except Exception as e:
                    # pyzbar failed, continue
                    pass
        
        return {
            'found': False,
            'matched': False,
            'qr_data': None,
            'message': 'No QR code found in the PDF.'
        }
        
    except Exception as e:
        return {
            'found': False,
            'matched': False,
            'qr_data': None,
            'message': f'Error scanning PDF: {str(e)}'
        }


def add_watermark_to_pdf(input_pdf, output_pdf, qr_data, file_reference):
    """
    Add a QR code watermark to a PDF file
    
    Args:
        input_pdf: Path to the input PDF file
        output_pdf: Path to save the watermarked PDF
        qr_data: Data to encode in the QR code
        file_reference: Reference number of the file
    """
    # Generate QR code
    import qrcode
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Save QR code to temporary bytes
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    
    # Open PDF
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    
    # Add watermark to each page
    for page in reader.pages:
        # Create watermark layer
        watermark_canvas = canvas.Canvas(io.BytesIO(), pagesize=letter)
        
        # Draw QR code on watermark layer
        watermark_canvas.drawImage(
            ImageReader(qr_buffer),
            400, 50,  # Position (bottom-right)
            80, 80,   # Size
            mask='auto'
        )
        
        # Add watermark text
        watermark_canvas.drawString(400, 140, f"Ref: {file_reference}")
        watermark_canvas.drawString(400, 125, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        watermark_canvas.save()
        watermark_buffer = io.BytesIO()
        watermark_canvas = canvas.Canvas(watermark_buffer, pagesize=letter)
        
        # Overlay watermark
        page.merge_page(watermark_buffer)
        writer.add_page(page)
    
    # Save output
    with open(output_pdf, 'wb') as output:
        writer.write(output)


def add_qr_to_image(image_path, qr_data, output_path=None):
    """
    Add QR code to an image file
    
    Args:
        image_path: Path to the image
        qr_data: Data to encode in QR code
        output_path: Optional output path, defaults to overwriting input
    """
    import qrcode
    from PIL import Image
    
    # Generate QR
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Open original image
    img = Image.open(image_path)
    
    # Calculate position for QR (bottom-right corner)
    qr_size = 100
    margin = 10
    pos = (img.width - qr_size - margin, img.height - qr_size - margin)
    
    # Paste QR onto image
    img.paste(qr_img, pos)
    
    # Save
    if output_path is None:
        output_path = image_path
    
    img.save(output_path)


def add_qr_watermark_to_pdf_bytes(input_pdf_bytes, qr_image_path, file_info=None, position='bottom-right'):
    """
    Add QR code watermark to a PDF from bytes
    
    Specifications:
    - Size: Small (40px-80px width, adaptive to page size)
    - Opacity: Low (10% - 15%) to act as a watermark
    - Color: Neutral gray
    - Error correction: High (to remain scannable despite low visibility)
    - Placement: Bottom-right corner (margin area)
    
    Args:
        input_pdf_bytes: BytesIO containing the PDF
        qr_image_path: Path to the QR code image file
        file_info: Optional dict with file info (reference, title, etc.)
        position: Position of QR code (default: 'bottom-right')
    
    Returns:
        BytesIO: The watermarked PDF content
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from PyPDF2 import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        from reportlab.lib.pagesizes import letter
        import io
        
        # Check if QR image path exists
        if not os.path.exists(qr_image_path):
            logger.error(f"QR code image not found at path: {qr_image_path}")
            return None
        
        # Read the input PDF
        input_pdf_bytes.seek(0)
        reader = PdfReader(input_pdf_bytes)
        writer = PdfWriter()
        
        # Load QR code image and prepare it for watermark
        qr_image = Image.open(qr_image_path)
        
        # Keep original black/white QR code (better contrast for scanning)
        qr_rgba = qr_image.convert('RGBA')
        
        # Create a transparent image preserving the original QR pattern
        width, height = qr_rgba.size
        transparent_qr = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        
        # Copy QR pattern - keep black modules, transparent background
        black = (0, 0, 0, 255)  # Pure black for high contrast
        transparent = (0, 0, 0, 0)
        
        for y in range(height):
            for x in range(width):
                pixel = qr_rgba.getpixel((x, y))
                if isinstance(pixel, tuple):
                    gray_value = pixel[0] if len(pixel) > 0 else 255
                else:
                    gray_value = pixel
                    
                # If pixel is dark (QR module), use black; otherwise transparent
                if gray_value < 128:
                    transparent_qr.putpixel((x, y), black)
                else:
                    transparent_qr.putpixel((x, y), transparent)
        
        # Save transparent QR to buffer
        qr_buffer = io.BytesIO()
        transparent_qr.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        
        # Process each page
        for page_num, page in enumerate(reader.pages):
            # Get page dimensions
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)
            
            # Calculate adaptive QR size (between 40-80px based on page width)
            if page_width < 400:  # Very small page
                qr_width = 40
                qr_height = 40
            elif page_width < 600:  # A4 or smaller
                qr_width = 50
                qr_height = 50
            elif page_width < 800:  # Larger than A4
                qr_width = 60
                qr_height = 60
            else:  # Large format
                qr_width = 70
                qr_height = 70
            
            # Calculate position - bottom-right corner (margin area)
            margin = 30
            
            if position == 'top-right':
                x = page_width - qr_width - margin
                y = page_height - qr_height - margin
            elif position == 'bottom-left':
                x = margin
                y = margin
            elif position == 'top-left':
                x = margin
                y = page_height - qr_height - margin
            else:  # bottom-right (default)
                x = page_width - qr_width - margin
                y = margin
            
            # Create watermark overlay
            watermark_buffer = io.BytesIO()
            c = canvas.Canvas(watermark_buffer, pagesize=(page_width, page_height))
            
            # Draw QR code from transparent image (already has transparency)
            qr_buffer.seek(0)
            c.drawImage(
                ImageReader(qr_buffer),
                x, y,
                width=qr_width,
                height=qr_height,
                mask='auto'
            )
            
            c.save()
            watermark_buffer.seek(0)
            
            # Merge watermark with page
            watermark_reader = PdfReader(watermark_buffer)
            watermark_page = watermark_reader.pages[0]
            page.merge_page(watermark_page)
            
            writer.add_page(page)
        
        # Write to output buffer
        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        output_buffer.seek(0)
        
        return output_buffer
        
    except Exception as e:
        import logging
        logging.error(f"Error adding QR watermark to PDF: {str(e)}")
        return None
