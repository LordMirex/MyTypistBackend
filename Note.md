# MyTypist Development Notes

## Architecture Overview

MyTypist is built as a high-performance document automation SaaS platform using FastAPI, designed specifically for the Nigerian market with Flutterwave payment integration.

### Core Components

1. **FastAPI Backend** - High-performance async API server
2. **SQLite with WAL** - Optimized database for high concurrency
3. **Redis** - Caching and session management
4. **Celery** - Background task processing
5. **Flutterwave** - Payment processing for Nigerian market

## Key Design Decisions

### Database Choice: SQLite with WAL Mode

**Why SQLite over PostgreSQL for MVP:**
- Simplified deployment (single file database)
- Excellent performance for read-heavy workloads
- WAL mode enables high concurrency
- Zero configuration required
- Easy backup and replication

**WAL Mode Benefits:**
- Readers don't block writers
- Writers don't block readers  
- Significantly improved concurrency
- Atomic commits
- Better crash recovery

### Payment Integration: Flutterwave

**Why Flutterwave over Stripe:**
- Optimized for Nigerian market
- Supports local payment methods (USSD, Bank Transfer, Mobile Money)
- Better NGN currency handling
- Lower fees for local transactions
- Regulatory compliance for Nigeria

### Document Processing Strategy

**Template-based Generation:**
- Upload DOCX templates with placeholders (`${variable_name}`)
- Real-time placeholder extraction using python-docx
- Background document generation for scalability
- Support for complex formatting preservation

**Performance Optimizations:**
- Template caching in Redis
- Async document generation
- File compression for old documents
- Thumbnail generation for previews

## Security Implementation

### Authentication & Authorization

```python
# JWT-based authentication
# Role-based access control (RBAC)
# API key support for server-to-server

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    STANDARD = "standard" 
    GUEST = "guest"
