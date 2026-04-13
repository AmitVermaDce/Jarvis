"""
file parsingtool
supportPDF, Markdown, TXTfiletextextract
"""

import os
from pathlib import Path
from typing import List, Optional


def _read_text_with_fallback(file_path: str) -> str:
    """
     read fetch textfile, UTF-8failed time auto explore encoding.
    
     many level fallbackstrategy:
    1. first test UTF-8 parse code
    2. using charset_normalizer encoding
    3. fallback to chardet encoding
    4. most end using UTF-8 + errors='replace'
    
    Args:
        file_path: filepath
        
    Returns:
         parse code after textcontent
    """
    data = Path(file_path).read_bytes()
    
    # first test UTF-8
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        pass
    
    # test using charset_normalizer encoding
    encoding = None
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(data).best()
        if best and best.encoding:
            encoding = best.encoding
    except Exception:
        pass
    
    # fallback to chardet
    if not encoding:
        try:
            import chardet
            result = chardet.detect(data)
            encoding = result.get('encoding') if result else None
        except Exception:
            pass
    
    # most end : using UTF-8 + replace
    if not encoding:
        encoding = 'utf-8'
    
    return data.decode(encoding, errors='replace')


class FileParser:
    """file parsing"""
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.md', '.markdown', '.txt'}
    
    @classmethod
    def extract_text(cls, file_path: str) -> str:
        """
         from file in extracttext
        
        Args:
            file_path: filepath
            
        Returns:
            extracttextcontent
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"file not exist in : {file_path}")
        
        suffix = path.suffix.lower()
        
        if suffix not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f" not supportfileformat: {suffix}")
        
        if suffix == '.pdf':
            return cls._extract_from_pdf(file_path)
        elif suffix in {'.md', '.markdown'}:
            return cls._extract_from_md(file_path)
        elif suffix == '.txt':
            return cls._extract_from_txt(file_path)
        
        raise ValueError(f" no method processfileformat: {suffix}")
    
    @staticmethod
    def _extract_from_pdf(file_path: str) -> str:
        """ from PDFextracttext"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError(" need to installPyMuPDF: pip install PyMuPDF")
        
        text_parts = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)
        
        return "\n\n".join(text_parts)
    
    @staticmethod
    def _extract_from_md(file_path: str) -> str:
        """ from Markdownextracttext, supportautoencoding detection"""
        return _read_text_with_fallback(file_path)
    
    @staticmethod
    def _extract_from_txt(file_path: str) -> str:
        """ from TXTextracttext, supportautoencoding detection"""
        return _read_text_with_fallback(file_path)
    
    @classmethod
    def extract_from_multiple(cls, file_paths: List[str]) -> str:
        """
         from many fileextracttextmerge
        
        Args:
            file_paths: filepathlist
            
        Returns:
            merge after text
        """
        all_texts = []
        
        for i, file_path in enumerate(file_paths, 1):
            try:
                text = cls.extract_text(file_path)
                filename = Path(file_path).name
                all_texts.append(f"=== text {i}: {filename} ===\n{text}")
            except Exception as e:
                all_texts.append(f"=== text {i}: {file_path} (extractfailed: {str(e)}) ===")
        
        return "\n\n".join(all_texts)


def split_text_into_chunks(
    text: str, 
    chunk_size: int = 500, 
    overlap: int = 50
) -> List[str]:
    """
     will text divide small block
    
    Args:
        text: original begin Chinese
        chunk_size: each block character number
        overlap: character number
        
    Returns:
        text block list
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # test in sentence sub divide
        if end < len(text):
            # check find most near sentence sub end symbol
            for sep in ['. ', '! ', '? ', '.\n', '!\n', '?\n', '\n\n', '. ', '! ', '? ']:
                last_sep = text[start:end].rfind(sep)
                if last_sep != -1 and last_sep > chunk_size * 0.3:
                    end = start + last_sep + len(sep)
                    break
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # below one block from positionstart
        start = end - overlap if end < len(text) else len(text)
    
    return chunks

