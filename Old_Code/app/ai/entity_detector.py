import re
import unicodedata
from typing import List, Dict, Any, Optional
from config import Config
from app.utils.logger import logger

class OrganizationDetector:
    """
    Named Entity & Target Organization Detector for Vietnamese Text.
    Supports robust regex pattern matching, word boundary protection,
    alias normalization, and multi-alias resolution.
    """

    def __init__(self, target_org: Optional[str] = None, aliases: Optional[List[str]] = None):
        self.target_org = target_org or Config.TARGET_ORGANIZATION
        self.aliases = aliases or Config.TARGET_ALIASES
        self.all_names = self._build_alias_list()
        self._compiled_patterns = self._compile_regex_patterns()

    def _build_alias_list(self) -> List[str]:
        """Consolidate target name and all configured aliases."""
        names = [self.target_org]
        for a in self.aliases:
            if a and a.strip() and a.lower() not in [n.lower() for n in names]:
                names.append(a.strip())
        return names

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize Unicode text to standard form NFC."""
        if not text:
            return ""
        return unicodedata.normalize("NFC", text)

    def _compile_regex_patterns(self) -> List[tuple]:
        """Compile regex patterns with boundary handling for each alias."""
        patterns = []
        for name in self.all_names:
            norm_name = self._normalize_text(name)
            # Escape regex special characters
            escaped_name = re.escape(norm_name)
            
            # Use word boundaries or space/punctuation padding for Vietnamese
            pattern_str = r'(?i)(?:\b|_|^)' + escaped_name + r'(?:\b|_|$)'
            pattern = re.compile(pattern_str, re.IGNORECASE | re.UNICODE)
            patterns.append((name, pattern))
        return patterns

    def detect(self, text: str) -> Dict[str, Any]:
        """
        Scans input text for mentions of the target organization or any of its aliases.
        
        Returns:
        {
            "org_detected": True / False,
            "matched_org": "Official Target / Matched Alias",
            "confidence": 1.0 (exact match) / 0.9 (regex match) / 0.0
        }
        """
        if not text:
            return {"org_detected": False, "matched_org": None, "confidence": 0.0}

        norm_text = self._normalize_text(text)

        # 1. Check compiled regex patterns
        for name, pattern in self._compiled_patterns:
            if pattern.search(norm_text):
                logger.debug(f"[OrganizationDetector] Matched organization '{name}' via pattern in text.")
                return {
                    "org_detected": True,
                    "matched_org": name,
                    "confidence": 0.95
                }

        # 2. Case-insensitive substring fallback for compound Vietnamese titles
        norm_text_lower = norm_text.lower()
        for name in self.all_names:
            if name.lower() in norm_text_lower:
                return {
                    "org_detected": True,
                    "matched_org": name,
                    "confidence": 0.85
                }

        return {
            "org_detected": False,
            "matched_org": None,
            "confidence": 0.0
        }
