"""Pytest configuration - set up test environment before any imports."""

import os

# Set test environment BEFORE any other imports
os.environ["FLASK_ENV"] = "testing"
