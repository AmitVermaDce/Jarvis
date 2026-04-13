"""
textprocessservice
"""

from typing import List, Optional
from ..utils.file_parser import FileParser, split_text_into_chunks


class TextProcessor:
    """textprocess"""
    
    @staticmethod
    def extract_from_files(file_paths: List[str]) -> str:
        """ from many fileextracttext"""
        return FileParser.extract_from_multiple(file_paths)
    
    @staticmethod
    def split_text(
        text: str,
        chunk_size: int = 500,
        overlap: int = 50
    ) -> List[str]:
        """
         divide text
        
        Args:
            text: original begin Chinese
            chunk_size: block large small
            overlap: large small
            
        Returns:
            text block list
        """
        return split_text_into_chunks(text, chunk_size, overlap)
    
    @staticmethod
    def preprocess_text(text: str) -> str:
        """
        processtext
        - remove many remaining empty
        - standard switch line
        
        Args:
            text: original begin Chinese
            
        Returns:
            process after text
        """
        import re
        
        # standard switch line
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # remove continue empty line ( protect most many switch line )
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # remove line first line tail empty
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        return text.strip()
    
    @staticmethod
    def get_text_stats(text: str) -> dict:
        """ fetch textstatisticsinfo"""
        return {
            "total_chars": len(text),
            "total_lines": text.count('\n') + 1,
            "total_words": len(text.split()),
        }

