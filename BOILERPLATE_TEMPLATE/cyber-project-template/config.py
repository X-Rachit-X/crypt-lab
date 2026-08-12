"""
Configuration loader for Cyber Project Template.
Reads from .env file and provides type-safe settings.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """Application settings from environment variables."""
    
    # Gemini AI API configuration
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    # Real-time analysis behavior (optimized for reduced API calls)
    ANALYSIS_ENABLED: bool = os.getenv("ANALYSIS_ENABLED", "true").lower() == "true"
    ANALYSIS_SAMPLE_SIZE: int = int(os.getenv("ANALYSIS_SAMPLE_SIZE", "2000"))
    ANALYSIS_DEBOUNCE_MS: int = int(os.getenv("ANALYSIS_DEBOUNCE_MS", "2500"))
    
    # Debugging
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    @property
    def analysis_debounce_sec(self) -> float:
        """Convert debounce milliseconds to seconds."""
        return max(0.2, self.ANALYSIS_DEBOUNCE_MS / 1000)


settings = Settings()

if settings.DEBUG:
    print(f"[Config] Loaded settings:")
    print(f"  ANALYSIS_ENABLED: {settings.ANALYSIS_ENABLED}")
    print(f"  ANALYSIS_DEBOUNCE_MS: {settings.ANALYSIS_DEBOUNCE_MS}")
    print(f"  ANALYSIS_SAMPLE_SIZE: {settings.ANALYSIS_SAMPLE_SIZE}")
