### STAGE 4 – BACKEND DEVELOPMENT

#### 1. API_REFERENCE.md


# API Reference

This document outlines the key API endpoints for MyTypist, including authentication, document CRUD operations, signature workflow, analytics, and admin-specific endpoints. All endpoints use JSON for request and response payloads and follow RESTful conventions.

## Authentication

### /auth/register
- **Method**: POST
- **Description**: Registers a new user.
- **Payload**:
  ```json
  {
    "username": "string",
    "email": "string",
    "password": "string",
    "role": "string"  // Optional: defaults to "standard"
  }
  ```
- **Response**:
  - **201 Created**:
    ```json
    {
      "id": 1,
      "username": "string",
      "email": "string",
      "role": "standard",
      "created_at": "2025-07-19T23:00:00",
      "updated_at": "2025-07-19T23:00:00"
    }
    ```
  - **400 Bad Request**: Invalid input (e.g., missing fields).
  - **409 Conflict**: Username or email already exists.
- **Notes**: Passwords are hashed using bcrypt before storage.

### /auth/login
- **Method**: POST
- **Description**: Authenticates a user and returns a JWT token.
- **Payload**:
  ```json
  {
    "email": "string",
    "password": "string"
  }
  ```
- **Response**:
  - **200 OK**:
    ```json
    {
      "access_token": "jwt_token",
      "token_type": "bearer"
    }
    ```
  - **401 Unauthorized**: Invalid credentials.
- **Notes**: JWT token is required for authenticated endpoints.

### Tokens
- **Format**: JWT with payload containing `user_id`, `role`, and `exp` (expiration).
- **Expiration**: 24 hours.
- **Usage**: Include in the `Authorization` header as `Bearer <token>`.

## Documents CRUD

### /documents
- **Method**: POST
- **Description**: Creates a new document.
- **Payload**:
  ```json
  {
    "title": "string",
    "content": "string",
    "template_id": 1,  // Optional
    "placeholders": {"client_name": "string", "date": "string"}  // Optional
  }
  ```
- **Response**:
  - **201 Created**:
    ```json
    {
      "id": 1,
      "title": "string",
      "content": "string",
      "user_id": 1,
      "template_id": 1,
      "created_at": "2025-07-19T23:00:00",
      "updated_at": "2025-07-19T23:00:00"
    }
    ```
  - **400 Bad Request**: Invalid payload.
  - **401 Unauthorized**: Missing/invalid token.
- **Notes**: If `template_id` is provided, placeholders are filled using `python-docx`.

### /documents/{id}
- **Methods**: GET, PUT, DELETE
- **Description**:
  - **GET**: Retrieves a document by ID.
  - **PUT**: Updates a document.
  - **DELETE**: Deletes a document.
- **Payload (PUT)**:
  ```json
  {
    "title": "string",
    "content": "string"
  }
  ```
- **Response**:
  - **200 OK (GET/PUT)**:
    ```json
    {
      "id": 1,
      "title": "string",
      "content": "string",
      "user_id": 1,
      "template_id": 1,
      "created_at": "2025-07-19T23:00:00",
      "updated_at": "2025-07-19T23:00:00"
    }
    ```
  - **204 No Content (DELETE)**.
  - **404 Not Found**: Document not found.
  - **401 Unauthorized**: Missing/invalid token.
  - **403 Forbidden**: User lacks permission.

## Signature Workflow

### /signatures
- **Method**: POST
- **Description**: Adds a signature to a document.
- **Payload**:
  ```json
  {
    "document_id": 1,
    "signer_name": "string",
    "signature_data": "base64_string"  // Base64-encoded image
  }
  ```
- **Response**:
  - **201 Created**:
    ```json
    {
      "id": 1,
      "document_id": 1,
      "signer_name": "string",
      "signature_data": "base64_string",
      "signed_at": "2025-07-19T23:00:00"
    }
    ```
  - **400 Bad Request**: Invalid base64 data.
  - **404 Not Found**: Document not found.
  - **401 Unauthorized**: Missing/invalid token.

### Request Flow
1. Client sends a POST request with `document_id`, `signer_name`, and `signature_data`.
2. Backend validates the base64 string and document existence.
3. Signature is stored in the `signatures` table.
4. Document is updated with the signature embedded using `python-docx`.
5. Response confirms success or returns an error.

### Base64 vs. File Upload
- **Base64**: Preferred for simplicity; signatures are sent as encoded strings, reducing server-side processing.
- **File Upload**: Alternative for larger signatures, but increases complexity (e.g., file storage, validation). Base64 is used for MVP.

## Analytics

### /analytics/track
- **Method**: POST
- **Description**: Tracks a document visit.
- **Payload**:
  ```json
  {
    "document_id": 1,
    "visitor_ip": "string"
  }
  ```
- **Response**:
  - **201 Created**:
    ```json
    {
      "id": 1,
      "document_id": 1,
      "visitor_ip": "string",
      "visited_at": "2025-07-19T23:00:00"
    }
    ```
  - **400 Bad Request**: Invalid payload.
  - **404 Not Found**: Document not found.

### /analytics/visits
- **Method**: GET
- **Description**: Retrieves visit history for a document.
- **Query Params**: `document_id` (required).
- **Response**:
  - **200 OK**:
    ```json
    [
      {
        "id": 1,
        "document_id": 1,
        "visitor_ip": "string",
        "visited_at": "2025-07-19T23:00:00"
      }
    ]
    ```
  - **401 Unauthorized**: Missing/invalid token.
  - **403 Forbidden**: User lacks permission.

## Admin Endpoints

### /admin/users
- **Method**: GET
- **Description**: Retrieves all users (admin only).
- **Response**:
  - **200 OK**:
    ```json
    [
      {
        "id": 1,
        "username": "string",
        "email": "string",
        "role": "standard",
        "created_at": "2025-07-19T23:00:00",
        "updated_at": "2025-07-19T23:00:00"
      }
    ]
    ```
  - **401 Unauthorized**: Missing/invalid token.
  - **403 Forbidden**: Non-admin user.

### /admin/templates
- **Method**: GET
- **Description**: Retrieves all templates (admin only).
- **Response**:
  - **200 OK**:
    ```json
    [
      {
        "id": 1,
        "name": "string",
        "file_path": "string",
        "placeholders": "string",
        "created_by": 1,
        "created_at": "2025-07-19T23:00:00",
        "updated_at": "2025-07-19T23:00:00"
      }
    ]
    ```
  - **401 Unauthorized**: Missing/invalid token.
  - **403 Forbidden**: Non-admin user.



---

#### 2. BACKEND_MODULE_STRUCTURE.md



# Backend Module Structure

This document outlines the folder structure and responsibilities of backend modules for MyTypist.

## Folder Layout

```
backend/
├── app/
│   ├── routes/
│   │   ├── auth.py
│   │   ├── documents.py
│   │   ├── signatures.py
│   │   ├── analytics.py
│   │   ├── admin.py
│   ├── services/
│   │   ├── document_service.py
│   │   ├── signature_service.py
│   │   ├── analytics_service.py
│   │   ├── auth_service.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── template.py
│   │   ├── document.py
│   │   ├── signature.py
│   │   ├── visit.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── template.py
│   │   ├── document.py
│   │   ├── signature.py
│   │   ├── visit.py
├── database.py
├── main.py
├── requirements.txt
```

- **app/**: Core application logic.
  - **routes/**: Defines API endpoints.
  - **services/**: Contains business logic for processing requests.
  - **models/**: SQLAlchemy models for database interactions.
  - **schemas/**: Pydantic schemas for request/response validation.
- **database.py**: Database connection and session management.
- **main.py**: Entry point for the FastAPI application.
- **requirements.txt**: Lists dependencies.

## Responsibility Matrix

| File/Directory            | Owner       | Responsibilities                                                                 |
|---------------------------|-------------|---------------------------------------------------------------------------------|
| `app/routes/auth.py`      | Backend Dev | Defines endpoints for registration, login, and token management.                |
| `app/routes/documents.py` | Backend Dev | Handles CRUD operations for documents.                                          |
| `app/routes/signatures.py`| Backend Dev | Manages signature creation and retrieval.                                      |
| `app/routes/analytics.py` | Backend Dev | Tracks document visits and retrieves analytics data.                            |
| `app/routes/admin.py`     | Backend Dev | Admin-only endpoints for managing users and templates.                          |
| `app/services/document_service.py` | Backend Dev | Logic for document creation, placeholder parsing, and updates.                 |
| `app/services/signature_service.py`| Backend Dev | Logic for embedding signatures into documents.                                 |
| `app/services/analytics_service.py`| Backend Dev | Logic for tracking visits and generating analytics reports.                    |
| `app/services/auth_service.py`     | Backend Dev | Handles authentication and JWT token generation/validation.                    |
| `app/models/*`            | Backend Dev | Defines SQLAlchemy models for database tables.                                  |
| `app/schemas/*`           | Backend Dev | Defines Pydantic schemas for API payloads and responses.                        |
| `database.py`             | Backend Dev | Configures database connection and session management.                         |
| `main.py`                 | Backend Dev | Initializes FastAPI app and mounts routes.                                      |
| `requirements.txt`        | Backend Dev | Maintains list of Python dependencies.                                          |

The **Backend Developer** owns all files, as MyTypist is initially built by a small team. As the project grows, responsibilities may be split among specialized roles (e.g., Database Admin, API Developer).



---

#### 3. FEATURE_LOGIC_BACKEND.md



# Feature Logic (Backend)

This document details the backend logic for key features: placeholder parsing, transaction flow for signatures, Redis caching, and error/edge-case handling.

## Placeholder Parsing

### Logic
- **Input**: Document content or template with placeholders (e.g., `Hello {client_name}, signed on {date}`) and a dictionary of values (e.g., `{"client_name": "John", "date": "2025-07-19"}`).
- **Process**:
  1. Use `python-docx` to load the template.
  2. Parse placeholders using regex (e.g., `r"\{([^}]+)\}"`) or SpaCy for advanced NLP.
  3. Replace placeholders with user-provided values.
  4. Save the updated document to storage and metadata to the database.
- **Output**: A processed document with filled placeholders.

### Example
```python
import re
from docx import Document

def parse_placeholders(doc_path: str, placeholders: dict) -> str:
    doc = Document(doc_path)
    for paragraph in doc.paragraphs:
        for key, value in placeholders.items():
            paragraph.text = re.sub(f"{{{key}}}", value, paragraph.text)
    output_path = doc_path.replace(".docx", "_filled.docx")
    doc.save(output_path)
    return output_path
```

## Transaction Flow (Sign & Save)

### Logic
1. **Request**: Client sends a POST to `/signatures` with `document_id`, `signer_name`, and `signature_data` (Base64).
2. **Validation**: Verify document exists and `signature_data` is valid Base64.
3. **Processing**:
   - Store signature metadata in the `signatures` table.
   - Use `python-docx` to embed the signature image in the document.
   - Update the document in storage and database.
4. **Response**: Return the signature details and updated document metadata.
5. **Transaction**: Wrap database operations in a transaction to ensure consistency.

### Example
```python
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.signature import Signature
from docx import Document

def add_signature(db: Session, document_id: int, signer_name: str, signature_data: str):
    try:
        # Validate document existence
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Validate Base64 (simplified)
        if not is_valid_base64(signature_data):
            raise HTTPException(status_code=400, detail="Invalid signature data")
        
        # Save signature
        signature = Signature(
            document_id=document_id,
            signer_name=signer_name,
            signature_data=signature_data
        )
        db.add(signature)
        
        # Embed signature in document
        doc = Document(document.file_path)
        doc.add_picture(decode_base64(signature_data))
        doc.save(document.file_path)
        
        db.commit()
        return signature
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
```

## Redis Caching Plan

### When to Use
- Cache frequently accessed data (e.g., template metadata, user sessions).
- Use as a message broker for Celery tasks (e.g., batch document processing).

### Implementation
- **Caching**:
  - Store template metadata (e.g., `name`, `placeholders`) in Redis with a TTL of 1 hour.
  - Key format: `template:<id>` (e.g., `template:1`).
- **Task Queue**:
  - Use Redis as the Celery backend for asynchronous tasks like batch document generation.
- **Setup**:
  ```python
  from redis import Redis

  redis_client = Redis.from_url("redis://localhost:6379")
  
  def cache_template(template_id: int, data: dict):
      redis_client.setex(f"template:{template_id}", 3600, json.dumps(data))
  ```

## Error & Edge-Case Handling

### Common Errors
- **Invalid Input**: Return `400 Bad Request` with detailed messages (e.g., missing placeholders).
- **Unauthorized Access**: Return `401 Unauthorized` for invalid tokens.
- **Resource Not Found**: Return `404 Not Found` for missing documents/templates.
- **Server Errors**: Return `500 Internal Server Error` and log to Sentry.

### Edge Cases
- **Duplicate Placeholders**: Ensure unique placeholder names in templates.
- **Large Documents**: Limit file size to 10MB to prevent memory issues.
- **Concurrent Edits**: Use optimistic locking with version control in the database.
- **Invalid Base64**: Validate signature data before processing.

### Example
```python
from fastapi import HTTPException

def validate_placeholders(placeholders: dict, template: Template):
    expected = set(json.loads(template.placeholders))
    provided = set(placeholders.keys())
    if expected != provided:
        raise HTTPException(
            status_code=400,
            detail=f"Expected placeholders: {expected}, provided: {provided}"
        )
```



---

This completes the requested documents for **Stage 4 – Backend Development**. Each document is designed to be comprehensive, aligning with the previously provided artifacts and the project’s goal of delivering a scalable, efficient document automation platform for Nigerian businesses. Let me know if you need further clarification or additional details!



---

## Data Flow
The data flow in MyTypist follows a structured request-response cycle to handle user interactions efficiently.

### Request → Auth → Service → DB → Response
Here’s an example of creating a document:
1. **Request**: The Client sends a POST request to `/api/documents/create` with document data and placeholders.
2. **Authentication**: The API validates the user’s JWT token to confirm authorization.
3. **Service**: FastAPI processes the request, uses `python-docx` to populate placeholders, and generates the document.
4. **Database**: Metadata (e.g., user ID, file path) is stored in SQLite or PostgreSQL.
5. **Response**: The API returns a success message with the document ID and a download link.

---

## Error Handling Strategy
MyTypist employs a clear and robust error handling approach to ensure reliability and user-friendliness.

### 4xx vs. 5xx
- **4xx Client Errors**: Indicate user-side issues, such as:
  - `400 Bad Request`: Invalid input data.
  - `401 Unauthorized`: Missing or invalid authentication token.
  - `403 Forbidden`: Insufficient permissions.
- **5xx Server Errors**: Indicate server-side problems, such as:
  - `500 Internal Server Error`: Unexpected failures during processing.
  - `503 Service Unavailable`: System down for maintenance.

### Error Response Format
Errors are returned in a consistent JSON structure:
```json
{
  "error": "Error Type",
  "message": "Detailed description",
  "code": 400
}
