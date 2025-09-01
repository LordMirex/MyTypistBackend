# Stage 2

Below is a complete **Tech Stack Decision Document** for **MyTypist**, tailored to the founders' goal of building a scalable, efficient, and cost-effective document automation platform for Nigerian businesses. This document outlines the technology choices, their rationale, versions, and additional considerations.


# TECH_STACK_DECISION.md

## Overview of Choices
MyTypist’s tech stack is designed to optimize performance, developer productivity, and scalability while keeping costs low during the initial beta phase. The stack is split into frontend, backend, and supporting tools, each selected to meet specific project needs.

### Frontend
- **Framework**: React.js with Vite  
- **UI Components**: shadcn-ui and Tailwind CSS  
- **State Management**: Redux (for complex state handling)  
- **Routing**: React Router  
- **API Calls**: Axios  

### Backend
- **Framework**: FastAPI  
- **Database**: SQLite (MVP)  
- **Caching & Task Queue**: Redis 
- **Document Processing**: python-docx, PyPDF2, SpaCy (for NLP)  
- **Asynchronous Tasks**: Celery  

### Additional Tools
- **Containerization**: Docker  
- **Error Monitoring**: Sentry  
- **Payment Gateway**: Paystack (sandbox for testing, live for production)  

---

## Why FastAPI vs. Alternatives
FastAPI was chosen as the backend framework over alternatives like Flask or Django for the following reasons:

- **Performance**: Built on Starlette and Uvicorn, FastAPI is one of the fastest Python frameworks, meeting the <200ms API response time requirement critical for real-time features.  
- **Asynchronous Support**: Native async capabilities allow efficient handling of multiple requests, ideal for collaborative editing and high concurrency.  
- **Developer Productivity**: Features like automatic API documentation (Swagger UI) and type hints via Pydantic reduce development time and bugs.  
- **Scalability**: Its lightweight architecture and compatibility with tools like Celery make it easy to scale as user demand increases.  
- **Community & Ecosystem**: FastAPI’s growing adoption ensures robust support and access to modern Python libraries.  


FastAPI strikes the perfect balance for MyTypist’s needs.

---

## Why Vite + React
Vite paired with React was selected for the frontend due to its speed, flexibility, and modern development experience:

- **Fast Development**: Vite’s instant hot module replacement (HMR) and near-instant server startup accelerate the development cycle.  
- **Optimized Builds**: Vite leverages Rollup for production builds, producing small, efficient bundles for faster load times.  
- **React’s Strengths**: React’s reusable components and virtual DOM enable a dynamic, interactive UI tailored to document automation.  
- **Ecosystem**: React’s mature ecosystem, including React Router and Redux, supports complex routing and state management needs.  


Vite + React delivers a fast, developer-friendly experience without overcomplicating the stack.

---

## Versioning & Compatibility
To ensure stability and compatibility, the following versions of key technologies are recommended:

### Backend
- **Python**: 3.10 (latest stable version with performance enhancements)  
- **FastAPI**: 0.115.0  
- **Uvicorn**: 0.30.6  
- **SQLAlchemy**: 2.0.35 (ORM for SQLite/PostgreSQL)  
- **python-docx**: 1.1.2  
- **PyPDF2**: 3.0.1  
- **SpaCy**: 3.7.6 (for NLP-based placeholder detection)  

### Frontend
- **Node.js**: 20.17.0 (LTS version)  
- **React**: 18.3.1  
- **Vite**: 5.4.8  
- **Tailwind CSS**: 3.4.13  
- **Redux**: 5.0.1  
- **React Router**: 6.26.2  
- **Axios**: 1.7.7  

These versions are selected for their stability, mutual compatibility, and inclusion of the latest security updates.

---

## Optional Add-ons

### When/Why to Enable Redis Locally
- **When to Enable**: Activate Redis locally when testing features like real-time collaborative editing or background task processing (e.g., batch document generation).  
- **Why**: Redis offers in-memory caching for faster data retrieval and serves as a message broker for Celery, ensuring efficient task queuing and execution.  
- **Setup**: Run Redis locally using Docker with the command:  
  ```
  docker run -d -p 6379:6379 redis
  ```

### Future: Paystack Sandbox vs. Live
- **Sandbox**: Use Paystack’s sandbox environment during development to test subscription payments without real transactions.  
- **Live**: Switch to live mode for production to process actual payments from users.  
- **Why**: The sandbox provides a safe testing ground, while live mode enables real revenue generation once the platform launches.  

---\



Below are the artifacts for **STAGE 2 – PROJECT SETUP (ENVIRONMENT)** and **STAGE 3 – DATABASE DESIGN** as requested.

---

### STAGE 2 – PROJECT SETUP (ENVIRONMENT)

#### 1. PROJECT_SETUP_GUIDE.md



# Project Setup Guide

## Prerequisites

To set up and run MyTypist locally, ensure you have the following:

- **Operating System**: Windows, macOS, or Linux
- **Tools**:
  - Git (for cloning the repository)
  - Python 3.8 or higher
  - Node.js 14 or higher
  - npm (or yarn as an alternative)
  - Docker (optional, for running Redis locally)
- **Ports**: Ensure ports 8000 (backend) and 3000 (frontend) are available.

## Project Structure

The project is organized as follows:

```
mytypist/
├── backend/          # Backend code (FastAPI)
├── frontend/         # Frontend code (React + Vite)
├── docs/             # Documentation
├── .env.example      # Example environment variables
└── README.md         # Project overview
```

## Step-by-Step Setup

### 1. Clone the Repository
Clone the MyTypist repository from GitHub:

```bash
git clone https://github.com/your-repo/mytypist.git
cd mytypist
```

### 2. Set Up the Backend
Navigate to the backend directory, create a virtual environment, and install dependencies:

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Set Up the Frontend
Navigate to the frontend directory and install dependencies:

```bash
cd ../frontend
npm install  # or yarn install
```

### 4. Configure Environment Variables
Copy the example environment file and configure it:

```bash
cd ..
cp .env.example .env
```

Edit `.env`:
- Generate a secure `SECRET_KEY`:
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
  Paste the output as the `SECRET_KEY` value.
- Set `DATABASE_URL=sqlite:///./local.db` for local SQLite development.
- If using Redis, ensure it’s running at `REDIS_URL=redis://localhost:6379`. Start Redis with Docker (optional):
  ```bash
  docker run -d -p 6379:6379 redis
  ```

### 5. Run the Application
- **Backend**: Start the FastAPI server:
  ```bash
  cd backend
  uvicorn main:app --reload
  ```
- **Frontend**: Start the Vite development server:
  ```bash
  cd ../frontend
  npm run dev
  ```

### 6. Verify
- Open your browser and visit `http://localhost:3000` to access the frontend.
- The backend API should be available at `http://localhost:8000`.



#### 2. .env.example



# Backend
DATABASE_URL=sqlite:///./local.db  # Database connection string (SQLite for local dev)
SECRET_KEY=your_secret_key_here    # Secret key for security (generate a random string)
REDIS_URL=redis://localhost:6379   # Redis URL (optional for caching/task queues)

# Frontend
VITE_API_URL=http://localhost:8000 # Backend API URL for frontend requests


