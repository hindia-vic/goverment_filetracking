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


def create_qr_watermark(qr_code_path, file_info=None, position='top-right'):
    """
    Create a PDF page with QR code watermark
    
    Args:
        qr_code_path: Path to the QR code image
        file_info: Optional dict with file info (reference, title, etc.)
        position: Position of watermark ('top-right', 'top-left', 'bottom-right', 'bottom-left')
    
    Returns:
        BytesIO: PDF page as bytes
    """
    # QR code size on the PDF (in points)
    qr_size = 80
    
    # Create a small PDF with the QR code
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    
    # Get page width
    page_width, page_height = letter
    
    # Calculate position
    margin = 20
    if position == 'top-right':
        x = page_width - qr_size - margin
        y = page_height - qr_size - margin
    elif position == 'top-left':
        x = margin
        y = page_height - qr_size - margin
    elif position == 'bottom-right':
        x = page_width - qr_size - margin
        y = margin
    elif position == 'bottom-left':
        x = margin
        y = margin
    else:  # default top-right
        x = page_width - qr_size - margin
        y = page_height - qr_size - margin
    
    # Draw QR code image
    if qr_code_path and os.path.exists(qr_code_path):
        try:
            # Open and resize the QR code image
            qr_image = Image.open(qr_code_path)
            qr_image = qr_image.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
            
            # Save to temp bytes for ReportLab
            temp_buffer = io.BytesIO()
            qr_image.save(temp_buffer, format='PNG')
            temp_buffer.seek(0)
            
            # Draw image on PDF
            can.drawImage(ImageReader(temp_buffer), x, y, width=qr_size, height=qr_size)
        except Exception as e:
            print(f"Error adding QR code: {e}")
    
    # Add file info text if provided
    if file_info:
        text_y = y - 15
        can.setFont("Helvetica-Bold", 8)
        can.drawString(x, text_y, f"Ref: {file_info.get('reference', '')}")
        
        text_y -= 10
        can.setFont("Helvetica", 6)
        can.drawString(x, text_y, f"Title: {file_info.get('title', '')[:25]}")
        
        text_y -= 8
        can.drawString(x, text_y, f"Downloaded: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        text_y -= 8
        can.drawString(x, text_y, f"By: {file_info.get('downloaded_by', '')}")
    
    can.save()
    packet.seek(0)
    
    return packet


def add_qr_watermark_to_pdf(input_pdf_path, output_pdf_path, qr_code_path, file_info=None, position='top-right'):
    """
    Add QR code watermark to all pages of a PDF
    
    Args:
        input_pdf_path: Path to input PDF file
        output_pdf_path: Path to output PDF file
        qr_code_path: Path to QR code image
        file_info: Optional dict with file info
        position: Position of watermark
    
    Returns:
        bool: True if successful
    """
    try:
        # Read the input PDF
        reader = PdfReader(input_pdf_path)
        writer = PdfWriter()
        
        # Create watermark page
        watermark_packet = create_qr_watermark(qr_code_path, file_info, position)
        watermark_pdf = PdfReader(watermark_packet)
        watermark_page = watermark_pdf.pages[0]
        
        # Add watermark to each page
        for page in reader.pages:
            # Merge watermark onto the page
            page.merge_page(watermark_page)
            writer.add_page(page)
        
        # Write output
        with open(output_pdf_path, 'wb') as output_file:
            writer.write(output_file)
        
        return True
    except Exception as e:
        print(f"Error adding watermark to PDF: {e}")
        return False


def add_qr_watermark_to_pdf_bytes(input_pdf_bytes, qr_code_path, file_info=None, position='top-right'):
    """
    Add QR code watermark to PDF from bytes
    
    Args:
        input_pdf_bytes: BytesIO or bytes of input PDF
        qr_code_path: Path to QR code image
        file_info: Optional dict with file info
        position: Position of watermark
    
    Returns:
        BytesIO: PDF with watermark
    """
    try:
        # Read the input PDF
        if isinstance(input_pdf_bytes, bytes):
            input_stream = io.BytesIO(input_pdf_bytes)
        else:
            input_stream = input_pdf_bytes
            
        reader = PdfReader(input_stream)
        writer = PdfWriter()
        
        # Create watermark page
        watermark_packet = create_qr_watermark(qr_code_path, file_info, position)
        watermark_pdf = PdfReader(watermark_packet)
        watermark_page = watermark_pdf.pages[0]
        
        # Add watermark to each page
        for page in reader.pages:
            page.merge_page(watermark_page)
            writer.add_page(page)
        
        # Return as bytes
        output_stream = io.BytesIO()
        writer.write(output_stream)
        output_stream.seek(0)
        
        return output_stream
    except Exception as e:
        print(f"Error adding watermark to PDF: {e}")
        return None


def get_file_with_watermark(file_instance, request, version=None):
    """
    Get a file with QR watermark for download
    
    Args:
        file_instance: File model instance
        request: Django request object
        version: Optional FileVersion instance
    
    Returns:
        tuple: (file_path, needs_watermark, file_info)
    """
    # Determine which file to use
    if version and version.file_attachment:
        file_path = version.file_attachment.path
        file_name = version.original_filename or version.file_attachment.name
    elif file_instance.file_attachment:
        file_path = file_instance.file_attachment.path
        file_name = file_instance.original_filename or file_instance.file_attachment.name
    else:
        return None, False, None
    
    # Check if it's a PDF
    is_pdf = file_name.lower().endswith('.pdf')
    
    # Get QR code path
    qr_code_path = None
    if file_instance.qr_code:
        qr_code_path = file_instance.qr_code.path
    
    # Prepare file info for watermark
    file_info = {
        'reference': file_instance.reference,
        'title': file_instance.title,
        'downloaded_by': request.user.get_full_name() or request.user.username,
    }
    
    return file_path, is_pdf, file_info, qr_code_path
