#!/usr/bin/env python3
"""Test that settings are loaded correctly."""
from config import settings

print(f"Database URL: {settings.database_url}")
print(f"Database Echo: {settings.db_echo}")
print(f"Flask Host: {settings.host}")
print(f"Flask Port: {settings.port}")
