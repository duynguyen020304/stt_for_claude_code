#!/usr/bin/env python
"""Verification script for is_running method."""
import sys
sys.path.insert(0, 'stt_desktop_client/src')

from server_manager import ServerManager

mgr = ServerManager('http://localhost:8000')
if hasattr(mgr, 'is_running'):
    print('is_running method exists')
    sys.exit(0)
else:
    print('ERROR')
    sys.exit(1)
