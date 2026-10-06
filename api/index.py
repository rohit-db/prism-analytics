"""Vercel entrypoint for the edge gateway.

Vercel serves the ASGI object named ``app`` from this module, and uploads only
files under the project root — which is why the whole repo is the project and
``.vercelignore`` trims it, rather than the edge living in a folder of its own.
``edge`` imports itself absolutely (``from edge.config import CONFIG``) and pulls
the shared login template out of ``server``, so the repo root has to be on the
path before either import runs.

Configuration comes from Vercel environment variables; there is no ``.env`` in a
serverless deployment. See docs/handoff/whitelabel-auth-and-hosting.md.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from edge.app import app  # noqa: E402

__all__ = ["app"]
