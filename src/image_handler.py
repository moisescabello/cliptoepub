#!/usr/bin/env python3
"""
Image Handler Module for Clipboard to ePub
Handles image detection, optimization, and embedding in ePub files
"""

import os
import io
import base64
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Tuple, Any
from PIL import Image, ImageOps
import pytesseract
from datetime import datetime

logger = logging.getLogger('ImageHandler')


class ImageHandler:
    """Handles image processing for ePub conversion"""

    # Supported image formats
    SUPPORTED_FORMATS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff'}

    # Max dimensions for images in ePub
    MAX_WIDTH = 1200
    MAX_HEIGHT = 1600

    # JPEG quality for optimization
    JPEG_QUALITY = 85

    def __init__(self, enable_ocr: bool = False, optimize_images: bool = True):
        """
        Initialize image handler

        Args:
            enable_ocr: Whether to enable OCR for text extraction
            optimize_images: Whether to optimize images for ePub
        """
        self.enable_ocr = enable_ocr
        self.optimize_images = optimize_images
        self.image_cache = {}  # Cache for processed images

    def detect_image_in_clipboard(self) -> Optional[Image.Image]:
        """
        Detect if clipboard contains an image

        Returns:
            PIL Image object if clipboard contains image, None otherwise
        """
        try:
            # Try to get image from clipboard using PIL
            # Note: This requires platform-specific implementation
            # For macOS, we'll use a workaround with pasteboard

            import subprocess
            import tempfile

            # Use osascript to check clipboard type
            script = '''
            on run
                set theType to (clipboard info)
                return theType as string
            end run
            '''

            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True
            )

            if 'TIFF' in result.stdout or 'PNG' in result.stdout:
                tmp_path = None
                try:
                    # Save clipboard image to temp file
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                        tmp_path = tmp.name

                    # Try to coerce clipboard to PNG to improve compatibility
                    subprocess.run(
                        ['osascript', '-e',
                         'set the clipboard to (read (the clipboard as «class PNGf») as «class PNGf»)'],
                        capture_output=True
                    )

                    # Try using pngpaste if available
                    try:
                        subprocess.run(['pngpaste', tmp_path], check=True)
                        # Fully load image into memory so temp file can be removed
                        with Image.open(tmp_path) as img:
                            img.load()
                            image = img.copy()
                        os.unlink(tmp_path)
                        tmp_path = None
                        return image
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        # pngpaste not available; fall through
                        pass
                finally:
                    # Ensure temp file is removed on any failure path
                    if tmp_path and os.path.exists(tmp_path):
                        try:
                            os.unlink(tmp_path)
                        except OSError:
                            pass

            return None

        except Exception as e:
            logger.debug(f"No image detected in clipboard: {e}")
            return None

    def optimize_image(self, image: Image.Image, format: str = 'JPEG') -> Tuple[bytes, str]:
        """
        Optimize image for ePub

        Args:
            image: PIL Image object
            format: Output format (JPEG, PNG, etc.)

        Returns:
            Tuple of (optimized image bytes, media type)
        """
        try:
            # Convert RGBA to RGB if saving as JPEG
            if format.upper() == 'JPEG' and image.mode in ('RGBA', 'LA', 'P'):
                # Create a white background
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background

            # Resize if necessary
            if self.optimize_images:
                # Pillow < 9.1 does not have Image.Resampling; fall back to LANCZOS/ANTIALIAS
                try:
                    resample_filter = Image.Resampling.LANCZOS  # type: ignore[attr-defined]
                except AttributeError:
                    resample_filter = getattr(Image, "LANCZOS", getattr(Image, "ANTIALIAS", Image.BICUBIC))
                image.thumbnail((self.MAX_WIDTH, self.MAX_HEIGHT), resample_filter)

            # Auto-orient based on EXIF data
            image = ImageOps.exif_transpose(image)

            # Save to bytes
            output = io.BytesIO()

            if format.upper() == 'JPEG':
                image.save(output, format='JPEG', quality=self.JPEG_QUALITY, optimize=True)
                media_type = 'image/jpeg'
            else:
                image.save(output, format='PNG', optimize=True)
                media_type = 'image/png'

            return output.getvalue(), media_type

        except Exception as e:
            logger.error(f"Error optimizing image: {e}")
            raise

    def extract_text_from_image(self, image: Image.Image) -> Optional[str]:
        """
        Extract text from image using OCR

        Args:
            image: PIL Image object

        Returns:
            Extracted text or None if OCR fails
        """
        if not self.enable_ocr:
            return None

        try:
            # Convert to grayscale for better OCR
            if image.mode != 'L':
                image = image.convert('L')

            # Apply some preprocessing for better OCR
            # Increase contrast
            image = ImageOps.autocontrast(image)

            # Extract text using Tesseract
            text = pytesseract.image_to_string(image, lang='eng')

            # Clean up the text
            text = text.strip()

            if text:
                logger.info(f"Extracted {len(text)} characters from image using OCR")
                return text

            return None

        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return None

    def process_image_for_epub(self, image: Image.Image,
                              title: Optional[str] = None,
                              enable_ocr: bool = None) -> Dict[str, Any]:
        """
        Process an image for inclusion in ePub

        Args:
            image: PIL Image object
            title: Optional title for the image
            enable_ocr: Override OCR setting for this image

        Returns:
            Dict with processed image data
        """
        result = {
            'type': 'image',
            'title': title or f'Image_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'format': 'image',
            'metadata': {
                'width': image.width,
                'height': image.height,
                'mode': image.mode,
                'format': image.format or 'unknown'
            }
        }

        # Generate unique ID for the image
        image_bytes = image.tobytes()
        image_hash = hashlib.md5(image_bytes).hexdigest()[:10]
        result['id'] = f'img_{image_hash}'

        # Check cache
        if image_hash in self.image_cache:
            logger.info("Using cached image")
            return self.image_cache[image_hash]

        # Optimize image
        optimized_bytes, media_type = self.optimize_image(image)
        result['data'] = base64.b64encode(optimized_bytes).decode('utf-8')
        result['media_type'] = media_type
        result['size'] = len(optimized_bytes)

        # Extract text if OCR is enabled
        if enable_ocr if enable_ocr is not None else self.enable_ocr:
            ocr_text = self.extract_text_from_image(image)
            if ocr_text:
                result['ocr_text'] = ocr_text
                result['has_text'] = True
            else:
                result['has_text'] = False

        # Cache the result
        self.image_cache[image_hash] = result

        logger.info(f"Processed image: {result['title']} "
                   f"({result['metadata']['width']}x{result['metadata']['height']}, "
                   f"{result['size'] / 1024:.1f} KB)")

        return result

    def create_image_chapter(self, image_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Create an ePub chapter from image data

        Args:
            image_data: Processed image data from process_image_for_epub

        Returns:
            Chapter dict with title and content
        """
        title = image_data['title']

        # Create HTML content for the image
        content = f'''
        <div class="image-container">
            <img src="data:{image_data['media_type']};base64,{image_data['data']}"
                 alt="{title}"
                 style="max-width: 100%; height: auto; display: block; margin: 0 auto;" />
            <p class="image-caption">{title}</p>
        '''

        # Add OCR text if available
        if image_data.get('has_text') and image_data.get('ocr_text'):
            content += f'''
            <div class="ocr-text">
                <h3>Extracted Text</h3>
                <div class="ocr-content">
                    {image_data['ocr_text'].replace(chr(10), '<br/>')}
                </div>
            </div>
            '''

        # Add metadata
        content += f'''
            <div class="image-metadata">
                <p>Dimensions: {image_data['metadata']['width']}×{image_data['metadata']['height']}</p>
                <p>Format: {image_data['metadata']['format']}</p>
                <p>Size: {image_data['size'] / 1024:.1f} KB</p>
            </div>
        </div>
        '''

        return {
            'title': title,
            'content': content
        }

    def get_image_css(self) -> str:
        """
        Get CSS styles for image display

        Returns:
            CSS string for image styling
        """
        return '''
        /* Image Styles */
        .image-container {
            text-align: center;
            margin: 2em 0;
            page-break-inside: avoid;
        }

        .image-container img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 0 auto;
            border: 1px solid #ddd;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .image-caption {
            margin-top: 1em;
            font-style: italic;
            color: #666;
            font-size: 0.9em;
        }

        .ocr-text {
            margin-top: 2em;
            padding: 1em;
            background-color: #f9f9f9;
            border-left: 4px solid #4CAF50;
        }

        .ocr-text h3 {
            margin-top: 0;
            color: #4CAF50;
        }

        .ocr-content {
            line-height: 1.6;
            color: #333;
        }

        .image-metadata {
            margin-top: 2em;
            padding: 1em;
            background-color: #f0f0f0;
            font-size: 0.85em;
            color: #666;
        }

        .image-metadata p {
            margin: 0.5em 0;
        }
        '''


# Utility functions for testing
def test_image_handler():
    """Test image handler functionality"""
    handler = ImageHandler(enable_ocr=True, optimize_images=True)

    # Test image detection
    image = handler.detect_image_in_clipboard()
    if image:
        print(f"Found image in clipboard: {image.size}")

        # Process the image
        processed = handler.process_image_for_epub(image)
        print(f"Processed image: {processed['title']}")

        if processed.get('has_text'):
            print(f"OCR Text: {processed['ocr_text'][:100]}...")

        # Create chapter
        chapter = handler.create_image_chapter(processed)
        print(f"Created chapter: {chapter['title']}")
    else:
        print("No image found in clipboard")


if __name__ == '__main__':
    test_image_handler()
