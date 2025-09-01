"""
API routes for MyTypist backend
"""

# Import all routers to make them available
from . import auth, documents, templates, signatures, analytics, payments, admin, feedback

__all__ = ["auth", "documents", "templates", "signatures", "analytics", "payments", "admin", "feedback"]
