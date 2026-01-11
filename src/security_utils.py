import os
import re

class SecurityUtils:
    """
    Utilities for handling sensitive data security, including redaction.
    """
    
    _SENSITIVE_KEYS = [
        "GITHUB_TOKEN",
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY"
    ]

    @staticmethod
    def redact_text(text: str) -> str:
        """
        Scans text for values of known sensitive environment variables and replaces them with [REDACTED].
        
        Args:
            text: The text to sanitize.
            
        Returns:
            The sanitized text.
        """
        if not text:
            return ""
            
        redacted_text = text
        
        for key in SecurityUtils._SENSITIVE_KEYS:
            secret_value = os.getenv(key)
            if secret_value and len(secret_value) > 4:  # Avoid redacting short common strings if a key is weirdly short
                # Simple string replacement
                redacted_text = redacted_text.replace(secret_value, "[REDACTED]")
                
        return redacted_text

    @staticmethod
    def safe_print(message: str, **kwargs):
        """
        Safely prints a message after redacting sensitive information.
        
        Args:
            message: The message to print.
            **kwargs: Additional arguments passed to the print function.
        """
        sanitized_message = SecurityUtils.redact_text(str(message))
        print(sanitized_message, **kwargs)
