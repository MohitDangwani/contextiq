"""ContextIQ MCP server package.

Lives as a sibling to backend/, not nested inside it (see
docs/architecture.md's repository layout) -- it's a second, independent
interface onto the same app.services.* layer the FastAPI backend and the
LangGraph agent already use, not a component either of those calls into.

Since mcp_server/ is a sibling directory rather than a subpackage of
backend/, backend/ has to be put on sys.path before anything here can
`import app...`. Done once, here in the package __init__, so it runs no
matter which submodule (server.py, a tools/* module, or a test) is
imported first.
"""
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
