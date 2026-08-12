"""
Configuration tests for Cyber Project Template.
"""

import pytest
import os
from config import Settings


class TestSettings:
    """Test configuration loading."""
    
    def test_default_settings(self):
        """Test default configuration values."""
        # Clear any existing env vars
        for key in ['GEMINI_API_KEY', 'ANALYSIS_ENABLED', 'DEBUG']:
            os.environ.pop(key, None)
        
        # Reimport to get defaults
        from config import settings
        
        assert settings.ANALYSIS_ENABLED == True
        assert settings.ANALYSIS_SAMPLE_SIZE == 2000
        assert settings.ANALYSIS_DEBOUNCE_MS == 2500
        assert settings.DEBUG == False
    
    def test_custom_settings(self, monkeypatch):
        """Test custom configuration override."""
        monkeypatch.setenv("ANALYSIS_DEBOUNCE_MS", "5000")
        monkeypatch.setenv("ANALYSIS_SAMPLE_SIZE", "1000")
        
        # Create new settings instance
        custom_settings = Settings()
        
        assert custom_settings.ANALYSIS_DEBOUNCE_MS == 5000
        assert custom_settings.ANALYSIS_SAMPLE_SIZE == 1000
    
    def test_debounce_sec_property(self):
        """Test debounce_sec property conversion."""
        custom_settings = Settings()
        custom_settings.ANALYSIS_DEBOUNCE_MS = 2500
        
        expected = 2.5
        assert custom_settings.analysis_debounce_sec == expected
