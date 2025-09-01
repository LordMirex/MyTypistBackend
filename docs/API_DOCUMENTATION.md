# MyTypist Backend API Documentation

## Overview

MyTypist provides a comprehensive RESTful API for document automation, template management, user authentication, payment processing, and system monitoring. All endpoints return JSON responses and use standard HTTP status codes.

## Base URL
- **Development**: `http://localhost:5000`
- **Production**: `https://your-domain.com`

## Authentication

### JWT Token-Based Authentication
All protected endpoints require a valid JWT token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

### Token Endpoints

#### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "your_password"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": 1,
    "email": "user@example.com",
    "full_name": "John Doe",
    "role": "user"
  }
}
```

#### Register
```http
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure_password",
  "full_name": "John Doe",
  "company_name": "Acme Corp"
}
```

#### Refresh Token
```http
POST /api/auth/refresh
Authorization: Bearer <refresh_token>
```

#### Get Current User
```http
GET /api/auth/me
Authorization: Bearer <access_token>
```

---

## Document Management

### Generate Document
```http
POST /api/documents/generate
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "template_id": 1,
  "placeholders": {
    "customer_name": "John Doe",
    "invoice_number": "INV-001",
    "date": "2025-01-15",
    "amount": "₦50,000"
  },
  "output_format": "pdf"
}
```

**Response:**
```json
{
  "document_id": 123,
  "download_url": "/api/documents/123/download",
  "file_name": "invoice_INV-001.pdf",
  "file_size": 245760,
  "generated_at": "2025-01-15T10:30:00Z",
  "expires_at": "2025-01-22T10:30:00Z"
}
```

### List Documents
```http
GET /api/documents?page=1&limit=20&search=invoice
Authorization: Bearer <access_token>
```

### Download Document
```http
GET /api/documents/{document_id}/download
Authorization: Bearer <access_token>
```

### Delete Document
```http
DELETE /api/documents/{document_id}
Authorization: Bearer <access_token>
```

---

## Template Management

### Upload Template
```http
POST /api/templates/upload
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

{
  "file": <template.docx>,
  "name": "Invoice Template",
  "description": "Standard invoice template for Nigerian businesses"
}
```

### List Templates
```http
GET /api/templates?category=invoice&public=true
Authorization: Bearer <access_token>
```

### Get Template Details
```http
GET /api/templates/{template_id}
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "id": 1,
  "name": "Invoice Template",
  "description": "Standard invoice template",
  "placeholders": [
    {
      "name": "customer_name",
      "type": "text",
      "required": true,
      "description": "Customer full name"
    },
    {
      "name": "amount",
      "type": "currency",
      "required": true,
      "description": "Invoice amount in Naira"
    }
  ],
  "category": "invoice",
  "is_public": true,
  "created_at": "2025-01-15T10:00:00Z"
}
```

---

## Payment Processing

### Initiate Payment
```http
POST /api/payments/initiate
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "amount": 5000,
  "currency": "NGN",
  "payment_method": "card",
  "customer": {
    "email": "customer@example.com",
    "phone": "+2348012345678",
    "name": "John Doe"
  },
  "metadata": {
    "purpose": "document_generation",
    "documents_count": 5
  }
}
```

### Verify Payment
```http
GET /api/payments/{transaction_id}/verify
Authorization: Bearer <access_token>
```

### Payment History
```http
GET /api/payments/history?status=completed&limit=50
Authorization: Bearer <access_token>
```

---

## Digital Signatures

### Upload Signature
```http
POST /api/signatures/upload
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

{
  "signature_file": <signature.png>,
  "signature_type": "image"
}
```

### Sign Document
```http
POST /api/documents/{document_id}/sign
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "signature_id": 1,
  "position": {
    "page": 1,
    "x": 100,
    "y": 200
  }
}
```

---

## System Monitoring

### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "MyTypist Backend",
  "version": "1.0.0"
}
```

### Detailed Health Check
```http
GET /api/monitoring/health/detailed
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": 1705318200,
  "checks": {
    "database": {
      "status": "healthy",
      "pool_info": {
        "pool_utilization": 15.5,
        "active_connections": 3,
        "total_connections": 50
      }
    },
    "cache": {
      "status": "healthy"
    },
    "memory": {
      "status": "healthy",
      "stats": {
        "memory_usage_mb": 245.8,
        "memory_percent": 12.3
      }
    }
  }
}
```

### Performance Statistics (Admin Only)
```http
GET /api/monitoring/performance/stats
Authorization: Bearer <admin_access_token>
```

---

## Error Responses

### Standard Error Format
```json
{
  "detail": "Error message",
  "error_code": "VALIDATION_ERROR",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### Common HTTP Status Codes
- **200**: Success
- **201**: Created
- **400**: Bad Request (validation errors)
- **401**: Unauthorized (invalid/missing token)
- **403**: Forbidden (insufficient permissions)
- **404**: Not Found
- **413**: Payload Too Large (file too big)
- **429**: Too Many Requests (rate limit exceeded)
- **500**: Internal Server Error

---

## Rate Limits

| Endpoint Category | Limit | Window |
|------------------|-------|---------|
| Authentication | 5 requests | 5 minutes |
| Registration | 3 requests | 1 hour |
| Document Generation | 20 requests | 1 minute |
| File Upload | 10 requests | 1 minute |
| General API | 100 requests | 1 minute |

---

## File Upload Limits

- **Maximum file size**: 100MB
- **Supported formats**: .docx, .doc, .pdf, .xlsx, .pptx, .png, .jpg, .jpeg
- **Security**: All files are scanned for malicious content
- **Storage**: Files are encrypted at rest using AES-256

---

## Pagination

List endpoints support pagination with these parameters:
- **page**: Page number (starts from 1)
- **limit**: Items per page (max 100)
- **search**: Search query
- **sort**: Sort field
- **order**: Sort order (asc/desc)

**Example:**
```http
GET /api/documents?page=2&limit=20&search=invoice&sort=created_at&order=desc
```

---

## Webhooks

### Payment Webhook
MyTypist receives payment status updates from Flutterwave:

```http
POST /api/payments/webhook
Content-Type: application/json
X-Flw-Signature: <webhook_signature>

{
  "event": "charge.completed",
  "data": {
    "id": 123456,
    "tx_ref": "TXN_12345",
    "status": "successful",
    "amount": 5000,
    "currency": "NGN"
  }
}
```

### Signature Verification
All webhooks are verified using HMAC-SHA256 signature validation for security.

---

## SDKs and Integration

### JavaScript/TypeScript
```javascript
// API client example
const api = axios.create({
  baseURL: 'https://api.mytypist.com',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});

// Generate document
const response = await api.post('/api/documents/generate', {
  template_id: 1,
  placeholders: {
    customer_name: 'John Doe',
    amount: '₦50,000'
  }
});
```

### Python
```python
import httpx

# API client
client = httpx.AsyncClient(
    base_url="https://api.mytypist.com",
    headers={"Authorization": f"Bearer {token}"}
)

# Generate document
response = await client.post("/api/documents/generate", json={
    "template_id": 1,
    "placeholders": {
        "customer_name": "John Doe",
        "amount": "₦50,000"
    }
})
```

---

## OpenAPI Documentation

Interactive API documentation is available at:
- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`
- **OpenAPI JSON**: `/openapi.json`

These endpoints provide comprehensive API exploration with example requests and responses.