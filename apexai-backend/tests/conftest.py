#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — pytest bootstrap.

Puts the backend root on sys.path so `src...` and `tests...` imports resolve
whether the suite is started with `pytest` or `python -m pytest`.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
