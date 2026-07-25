#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — TestClient construction that survives the httpx 0.28 break.

httpx 0.28 removed the `app=` shortcut from `Client.__init__`. Starlette < 0.37
still forwards it (its ASGI plumbing already lives in a dedicated transport),
so on those combinations `TestClient(app)` raises:

    TypeError: Client.__init__() got an unexpected keyword argument 'app'
"""

import inspect

import httpx
from starlette.testclient import TestClient

_HTTPX_ACCEPTS_APP = "app" in inspect.signature(httpx.Client.__init__).parameters


def make_test_client(app, **kwargs) -> TestClient:
    """Build a TestClient whatever the httpx / starlette pairing is.

    Swallows the now-unsupported `app=` kwarg for the duration of the
    construction only; a no-op once starlette (or httpx) is upgraded.
    """
    if _HTTPX_ACCEPTS_APP:
        return TestClient(app, **kwargs)

    original_init = httpx.Client.__init__

    def init_without_app(self, *args, app=None, **kw):
        original_init(self, *args, **kw)

    httpx.Client.__init__ = init_without_app
    try:
        return TestClient(app, **kwargs)
    finally:
        httpx.Client.__init__ = original_init
