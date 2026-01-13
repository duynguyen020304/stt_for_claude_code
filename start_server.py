#!/usr/bin/env python3
"""
Startup script for Audio Transcription Server

This script sets environment variables before importing modules
to handle CPU-only systems properly.
"""

import os
import sys

# Force CPU mode initially - will be overridden by auto-detection in server.py
# This prevents torchaudio from trying to load CUDA libraries at import time
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["TORCH_CUDA_ARCH_LIST"] = ""

# Now import and run the server
if __name__ == "__main__":
    import server
    # The server's main block will handle the rest
