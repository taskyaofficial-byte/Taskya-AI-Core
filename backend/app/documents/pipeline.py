from pathlib import Path

class DocumentPipeline:
    def extract_text(self, path):
        p=Path(path); ext=p.suffix.lower()
        if ext=='.pdf':
            try:
                import pypdf
                return '\n'.join((x.extract_text() or '') for x in pypdf.PdfReader(str(p)).pages)
            except ImportError: raise RuntimeError('Install pypdf for PDF extraction')
        if ext in {'.txt','.md','.csv','.json','.py','.html'}: return p.read_text(encoding='utf-8', errors='ignore')
        raise RuntimeError(f'Unsupported document type: {ext}')

    def ocr(self, image_path, lang='eng'):
        try: import pytesseract
        except ImportError as e: raise RuntimeError('Install pytesseract and the Tesseract engine for OCR') from e
        from PIL import Image
        return pytesseract.image_to_string(Image.open(image_path), lang=lang)
