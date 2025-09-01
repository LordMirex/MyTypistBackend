### Revised Approach for Frontend Observability

**Assumption**: The "agent" is a software component (e.g., a monitoring tool, analytics agent, or automated testing bot) that needs to observe frontend behavior, such as page rendering, API interactions, and user actions. Observability will be achieved through structured logging, event tracking, and agent-friendly markup (e.g., semantic HTML, data attributes).

---

### 1. FRONTEND_AUDIT_AND_REFACTOR.md (Revised)



# Frontend Audit and Refactor

This document audits the existing frontend pages and components, maps them to API endpoints, evaluates props and state requirements, and prescribes changes to ensure observability by an external agent (e.g., monitoring tool or bot). Observability is achieved through structured logging, semantic HTML, and data attributes for agent parsing.

## Current Page Inventory

The frontend is built with React, Vite, and Tailwind CSS under `frontend/src`. Below is the inventory of `.tsx` pages and components:

```
frontend/src/
├── pages/
│   ├── Home.tsx
│   ├── Login.tsx
│   ├── Register.tsx
│   ├── Dashboard.tsx
│   ├── DocumentList.tsx
│   ├── DocumentCreate.tsx
│   ├── DocumentEdit.tsx
│   ├── DocumentView.tsx
│   ├── TemplateList.tsx
│   ├── TemplateCreate.tsx
│   ├── Analytics.tsx
│   ├── AdminDashboard.tsx
├── components/
│   ├── SignatureCanvas.tsx
│   ├── DocumentPreview.tsx
│   ├── TemplateCard.tsx
│   ├── UserProfile.tsx
│   ├── Navbar.tsx
│   ├── Footer.tsx
```

- **Pages**:
  - `Home.tsx`: Landing page with app overview.
  - `Login.tsx`: User login form.
  - `Register.tsx`: User registration form.
  - `Dashboard.tsx`: User dashboard showing recent documents.
  - `DocumentList.tsx`: Displays a list of user documents.
  - `DocumentCreate.tsx`: Form to create a new document.
  - `DocumentEdit.tsx`: Form to edit an existing document.
  - `DocumentView.tsx`: Displays a document with signature functionality.
  - `TemplateList.tsx`: Lists available templates.
  - `TemplateCreate.tsx`: Form to create/upload a new template.
  - `Analytics.tsx`: Displays document visit analytics.
  - `AdminDashboard.tsx`: Admin-only view for managing users/templates.

- **Components**:
  - `SignatureCanvas.tsx`: Canvas for capturing user signatures.
  - `DocumentPreview.tsx`: Renders a preview of a document.
  - `TemplateCard.tsx`: Card component for displaying template details.
  - `UserProfile.tsx`: Displays user information and settings.
  - `Navbar.tsx`: Navigation bar with links.
  - `Footer.tsx`: Footer with app information.

## Mapping to API Endpoints

| Component/Page          | API Endpoint(s)                        | Description                                      | Agent Observability Notes                     |
|-------------------------|----------------------------------------|--------------------------------------------------|----------------------------------------------|
| `Login.tsx`             | POST `/auth/login`                     | Authenticates user and retrieves JWT token.      | Log login attempts with `data-event="login"`. |
| `Register.tsx`          | POST `/auth/register`                  | Registers a new user.                            | Log registration with `data-event="register"`.|
| `Dashboard.tsx`         | GET `/documents`                       | Fetches recent documents for the user.           | Expose document count via `data-documents`.   |
| `DocumentList.tsx`      | GET `/documents`                       | Lists all user documents.                        | Add `data-document-id` to each list item.     |
| `DocumentCreate.tsx`    | POST `/documents`                      | Creates a new document with optional template.   | Log creation with `data-event="create_doc"`.  |
| `DocumentEdit.tsx`      | GET `/documents/{id}`, PUT `/documents/{id}` | Fetches and updates a document.            | Log edits with `data-event="edit_doc"`.       |
| `DocumentView.tsx`      | GET `/documents/{id}`, POST `/signatures` | Views document and adds signatures.           | Track views with `data-event="view_doc"`.     |
| `TemplateList.tsx`      | GET `/templates`                       | Lists available templates.                       | Add `data-template-id` to each template.      |
| `TemplateCreate.tsx`    | POST `/templates`                      | Creates a new template.                          | Log creation with `data-event="create_template"`. |
| `Analytics.tsx`         | GET `/analytics/visits`, POST `/analytics/track` | Tracks and displays document visits.      | Expose visit data via `data-visits`.          |
| `AdminDashboard.tsx`    | GET `/admin/users`, GET `/admin/templates` | Admin view for user/template management.     | Log admin actions with `data-event="admin_action"`. |

## Props & State Audit

### Components Needing Auth Tokens
- **Pages**: `Dashboard.tsx`, `DocumentList.tsx`, `DocumentCreate.tsx`, `DocumentEdit.tsx`, `DocumentView.tsx`, `TemplateList.tsx`, `TemplateCreate.tsx`, `Analytics.tsx`, `AdminDashboard.tsx`
- **Components**: `UserProfile.tsx`, `SignatureCanvas.tsx`
- **State**: Use `AuthContext` to manage JWT tokens.
- **Observability**: Add `data-authenticated="true/false"` to components to indicate authentication status for agent inspection.

### Components Needing Data Hydration
- **DocumentList.tsx**: Fetches documents via GET `/documents`.
- **DocumentCreate.tsx`: Fetches templates via GET `/templates`.
- **DocumentEdit.tsx`: Fetches document via GET `/documents/{id}`.
- **DocumentView.tsx`: Fetches document and signatures.
- **TemplateList.tsx`: Fetches templates.
- **Analytics.tsx`: Fetches visit data via GET `/analytics/visits`.
- **AdminDashboard.tsx`: Fetches users and templates.
- **Observability**: Add `data-hydrated="true/false"` to indicate data loading state.

### State Management
- **Redux**: Manages global state (documents, templates).
- **Local State**: Handles form inputs and UI toggles.
- **Observability**: Log state changes to `window.mytypistEvents` for agent access (e.g., `window.mytypistEvents.push({ event: "state_change", component: "DocumentList" })`).

## Refactor Plan

### Hook Up Axios Instance
- Centralize API calls in `src/api/index.ts` with an Axios instance.
- Add observability by logging API calls to `window.mytypistEvents`.
- Example:
  ```typescript
  import axios from 'axios';

  const apiClient = axios.create({
    baseURL: import.meta.env.VITE_API_URL,
    headers: { 'Content-Type': 'application/json' },
  });

  apiClient.interceptors.request.use(config => {
    window.mytypistEvents = window.mytypistEvents || [];
    window.mytypistEvents.push({ event: 'api_request', url: config.url });
    return config;
  });

  export default apiClient;
  ```

### Centralize API Client in src/api
- Structure:
  ```
  frontend/src/api/
  ├── index.ts
  ├── auth.ts
  ├── documents.ts
  ├── signatures.ts
  ├── analytics.ts
  ├── admin.ts
  ```
- Example (`documents.ts`):
  ```typescript
  import apiClient from './index';

  export const getDocuments = async () => {
    const response = await apiClient.get('/documents');
    window.mytypistEvents.push({ event: 'api_response', url: '/documents', status: response.status });
    return response.data;
  };
  ```

### Update Existing HTTP Calls
- Replace `fetch` or outdated calls with `apiClient`.
- Add `data-event` attributes to DOM elements for agent parsing (e.g., `<button data-event="create_doc">Create</button>`).
- Ensure all API responses are logged to `window.mytypistEvents` for observability.



---

### 2. FRONTEND_ROUTES.md (Revised)



# Frontend Routes

This document outlines the routing structure, authentication guards, lazy loading, and observability features for agent monitoring.

## Route ↔ Component Table

| Route Path             | Component              | Description                              | Requires Auth | Observability Notes                       |
|------------------------|------------------------|------------------------------------------|---------------|-------------------------------------------|
| `/`                    | `Home.tsx`             | Landing page                             | No            | `<main data-page="home">`                 |
| `/login`               | `Login.tsx`            | User login form                          | No            | `<form data-event="login_form">`          |
| `/register`            | `Register.tsx`         | User registration form                   | No            | `<form data-event="register_form">`       |
| `/dashboard`           | `Dashboard.tsx`        | User dashboard with recent documents     | Yes           | `<div data-page="dashboard">`             |
| `/documents`           | `DocumentList.tsx`     | List of user documents                   | Yes           | `<ul data-component="document_list">`     |
| `/documents/new`       | `DocumentCreate.tsx`   | Create a new document                    | Yes           | `<form data-event="create_doc_form">`     |
| `/documents/:id/edit`  | `DocumentEdit.tsx`     | Edit an existing document                | Yes           | `<form data-event="edit_doc_form">`       |
| `/documents/:id`       | `DocumentView.tsx`     | View document with signature option      | Yes           | `<div data-page="document_view">`         |
| `/templates`           | `TemplateList.tsx`     | List of available templates              | Yes           | `<ul data-component="template_list">`     |
| `/templates/new`       | `TemplateCreate.tsx`   | Create a new template                    | Yes           | `<form data-event="create_template_form">`|
| `/analytics`           | `Analytics.tsx`        | Document visit analytics                 | Yes           | `<div data-page="analytics">`             |
| `/admin`               | `AdminDashboard.tsx`   | Admin management interface               | Yes (Admin)   | `<div data-page="admin_dashboard">`       |

## Auth Guards
- **Implementation**: Use `ProtectedRoute` to enforce authentication and role checks.
- **Logic**:
  - Check for JWT token in `AuthContext`.
  - For `/admin`, verify `user.role === 'admin'`.
  - Log guard actions to `window.mytypistEvents` (e.g., `{ event: "auth_guard", route: "/dashboard" }`).
- **Example**:
  ```typescript
  import { Navigate } from 'react-router-dom';
  import { useAuth } from '../contexts/AuthContext';

  const ProtectedRoute = ({ children, adminOnly = false }) => {
    const { token, user } = useAuth();
    window.mytypistEvents = window.mytypistEvents || [];
    if (!token) {
      window.mytypistEvents.push({ event: 'auth_guard', status: 'unauthorized', route: window.location.pathname });
      return <Navigate to="/login" />;
    }
    if (adminOnly && user?.role !== 'admin') {
      window.mytypistEvents.push({ event: 'auth_guard', status: 'forbidden', route: window.location.pathname });
      return <Navigate to="/dashboard" />;
    }
    return children;
  };
  ```

## Lazy/Suspense Loading
- **Implementation**: Use `lazy` and `Suspense` for code splitting.
- **Observability**: Add `data-loading="true/false"` to indicate loading state.
- **Example**:
  ```typescript
  import { lazy, Suspense } from 'react';
  const DocumentList = lazy(() => import('./pages/DocumentList'));

  const App = () => (
    <Suspense fallback={<div data-loading="true">Loading...</div>}>
      <Routes>
        <Route path="/documents" element={<DocumentList />} />
      </Routes>
    </Suspense>
  );
  ```



---

### 3. FEATURE_LOGIC_FRONTEND.md (Revised)



# Feature Logic (Frontend)

This document details the frontend logic for state management, placeholder rendering, signature canvas, and analytics tracking, with observability for an external agent.

## State Management

### Contexts: AuthContext, ApiContext

#### AuthContext
- **Purpose**: Manages authentication state.
- **Observability**: Log state changes to `window.mytypistEvents`.
- **Implementation**:
  ```typescript
  import { createContext, useContext, useState } from 'react';

  interface AuthContextType {
    token: string | null;
    user: { id: number; username: string; role: string } | null;
    login: (token: string, user: any) => void;
    logout: () => void;
  }

  const AuthContext = createContext<AuthContextType | undefined>(undefined);

  export const AuthProvider = ({ children }) => {
    const [token, setToken] = useState<string | null>(null);
    const [user, setUser] = useState(null);

    const login = (token: string, user: any) => {
      setToken(token);
      setUser(user);
      localStorage.setItem('token', token);
      window.mytypistEvents.push({ event: 'auth_login', user_id: user.id });
    };

    const logout = () => {
      setToken(null);
      setUser(null);
      localStorage.removeItem('token');
      window.mytypistEvents.push({ event: 'auth_logout' });
    };

    return (
      <AuthContext.Provider value={{ token, user, login, logout }}>
        {children}
      </AuthContext.Provider>
    );
  };
  ```

#### ApiContext
- **Purpose**: Provides the Axios instance.
- **Observability**: API calls are logged in `apiClient` interceptors.
- **Implementation**: See `API_INTEGRATION_GUIDE.md`.

## Placeholder Rendering

### Logic
- **Input**: Document content with placeholders.
- **Process**:
  1. Fetch document/template via API.
  2. Parse placeholders with regex for preview.
  3. Render a form for placeholder input.
  4. Update preview in `DocumentPreview.tsx`.
  5. Add `data-placeholder` attributes for agent parsing.
- **Example**:
  ```typescript
  import { useState } from 'react';

  const DocumentCreate = () => {
    const [placeholders, setPlaceholders] = useState({});
    const content = 'Hello {client_name}, signed on {date}';
    const regex = /\{([^}]+)\}/g;
    const matches = [...content.matchAll(regex)].map(match => match[1]);

    return (
      <div data-component="document_create">
        {matches.map(key => (
          <input
            key={key}
            type="text"
            placeholder={key}
            data-placeholder={key}
            onChange={e => {
              setPlaceholders({ ...placeholders, [key]: e.target.value });
              window.mytypistEvents.push({ event: 'placeholder_update', key, value: e.target.value });
            }}
          />
        ))}
        <DocumentPreview content={content} placeholders={placeholders} />
      </div>
    );
  };
  ```

## Signature Canvas Component

### Logic
- **Implementation**: Use `react-signature-canvas`.
- **Process**:
  1. Render a canvas for signature capture.
  2. Convert to Base64 and send to POST `/signatures`.
  3. Add `data-event="signature"` for observability.
- **Example**:
  ```typescript
  import SignatureCanvas from 'react-signature-canvas';
  import { useRef } from 'react';
  import { useApi } from '../contexts/ApiContext';

  const SignatureCanvasComponent = ({ documentId }) => {
    const sigCanvas = useRef(null);
    const api = useApi();

    const saveSignature = async () => {
      const signatureData = sigCanvas.current.toDataURL();
      await api.post('/signatures', {
        document_id: documentId,
        signer_name: 'User Name',
        signature_data: signatureData,
      });
      window.mytypistEvents.push({ event: 'signature_saved', document_id: documentId });
    };

    return (
      <div data-component="signature_canvas">
        <SignatureCanvas ref={sigCanvas} canvasProps={{ width: 500, height: 200, 'data-event': 'signature' }} />
        <button onClick={saveSignature} data-event="save_signature">Save Signature</button>
      </div>
    );
  };
  ```

## Analytics Tracker Script

### Logic
- **Purpose**: Track document visits via POST `/analytics/track`.
- **Observability**: Log visits to `window.mytypistEvents`.
- **Example**:
  ```typescript
  import { useEffect } from 'react';
  import { useApi } from '../contexts/ApiContext';

  const AnalyticsTracker = ({ documentId }) => {
    const api = useApi();

    useEffect(() => {
      api.post('/analytics/track', { document_id: documentId, visitor_ip: 'unknown' });
      window.mytypistEvents.push({ event: 'document_view', document_id: documentId });
    }, [documentId, api]);

    return <div data-event="analytics_tracker" />;
  };
  ```



---

### 4. API_INTEGRATION_GUIDE.md (Revised)



# API Integration Guide

This document outlines Axios setup, interceptors, error handling, and data mocking, with observability for agent monitoring.

## Axios Setup

### Configuration
- Centralize API calls in `src/api/index.ts`.
- Example:
  ```typescript
  import axios from 'axios';

  const apiClient = axios.create({
    baseURL: import.meta.env.VITE_API_URL,
    headers: { 'Content-Type': 'application/json' },
  });

  export default apiClient;
  ```

## Interceptors (Auth Token)

### Implementation
- Add interceptors for JWT tokens and observability.
- Example:
  ```typescript
  import { useAuth } from '../contexts/AuthContext';

  apiClient.interceptors.request.use(config => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    window.mytypistEvents = window.mytypistEvents || [];
    window.mytypistEvents.push({ event: 'api_request', url: config.url, method: config.method });
    return config;
  });

  apiClient.interceptors.response.use(
    response => {
      window.mytypistEvents.push({ event: 'api_response', url: response.config.url, status: response.status });
      return response;
    },
    error => {
      window.mytypistEvents.push({ event: 'api_error', url: error.config.url, status: error.response?.status });
      if (error.response?.status === 401) {
        localStorage.removeItem('token');
        window.location.href = '/login';
      }
      return Promise.reject(error);
    }
  );
  ```

## Error Handling (Toasts)

### Implementation
- Use `react-hot-toast` for user notifications.
- Log errors to `window.mytypistEvents`.
- Example:
  ```typescript
  import toast from 'react-hot-toast';

  const handleApiError = (error) => {
    const message = error.response?.data?.message || 'An error occurred';
    toast.error(message);
    window.mytypistEvents.push({ event: 'error_toast', message });
    throw error;
  };

  export const getDocuments = async () => {
    try {
      const response = await apiClient.get('/documents');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  };
  ```

## Mocking Data for Early UI Work

### Strategy
- Use `msw` for mocking API responses.
- Add mock events to `window.mytypistEvents` for agent observability.
- Setup:
  ```bash
  npm install msw --save-dev
  ```
- Example (`src/mocks/handlers.ts`):
  ```typescript
  import { rest } from 'msw';

  export const handlers = [
    rest.get('http://localhost:8000/documents', (req, res, ctx) => {
      window.mytypistEvents.push({ event: 'mock_response', url: '/documents' });
      return res(
        ctx.status(200),
        ctx.json([
          { id: 1, title: 'Mock Document', content: 'Hello {client_name}' },
        ])
      );
    }),
  ];
  ```



---

### Clarifications and Next Steps

1. **Agent Observability**: The revised documents add `data-*` attributes and a global `window.mytypistEvents` array to log events (e.g., API calls, state changes, user actions) for an agent to monitor. If the agent requires specific formats (e.g., JSON logs, WebSocket events), please clarify.
2. **Existing Artifacts**: The changes build on the previous artifacts, ensuring consistency with the FastAPI backend, SQLite database, and React frontend.
3. **Potential Misalignment**: If the "agent" refers to something specific (e.g., a Nigerian regulatory agent, a browser user agent, or an AI agent), please provide details so I can adjust the observability mechanism (e.g., structured logs for compliance, user-agent detection, or API endpoints for AI interaction).

To ensure I’m not misunderstanding further, could you confirm:
- What type of agent needs to observe the frontend (e.g., monitoring tool, bot, human agent)?
- Any specific observability requirements (e.g., log formats, events to track)?
- Are there existing frontend pages that need specific refactoring beyond what’s outlined?

I’m committed to getting this right for MyTypist. Please share more details, and I’ll refine the artifacts to meet your exact needs!