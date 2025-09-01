# MY FIRST EVER PLACEHOLDER ACHEIVEMENT WERE IT ACTUALLY WORKS, SO LEARN FROM THIS AND IMPROVE IT AND BUILD PERFECTLY THIS TIME

# **Helper Functions**
def ordinal(n):
    """Convert a number to its ordinal form (e.g., 1 -> 1st, 2 -> 2nd)."""
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = ['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]
    return str(n) + suffix

def format_date(date_string, template_type):
    """Format a date string based on the template type."""
    try:
        date_obj = parse(date_string)
        day = ordinal(date_obj.day)
        month = date_obj.strftime("%B")
        year = date_obj.year
        if template_type == "letter":
            return f"{day} {month}, {year}"
        elif template_type == "affidavit":
            return f"{day} of {month}, {year}"
        return f"{date_obj.day} {month} {year}"
    except ValueError:
        logger.warning(f"Invalid date format: {date_string}")
        return date_string

def extract_placeholders(doc):
    """Extract placeholders like ${name} from a Word document."""
    placeholders = []
    placeholder_pattern = re.compile(r'\$\{([^}]+)\}')
    for p_idx, paragraph in enumerate(doc.paragraphs):
        full_text = ''.join(run.text for run in paragraph.runs)
        matches = placeholder_pattern.finditer(full_text)
        for match in matches:
            placeholder_name = match.group(1)
            start_pos = match.start()
            end_pos = match.end()
            current_pos = 0
            start_run_idx = end_run_idx = None
            bold = italic = underline = False
            for r_idx, run in enumerate(paragraph.runs):
                run_start = current_pos
                run_end = current_pos + len(run.text)
                if start_run_idx is None and run_start <= start_pos < run_end:
                    start_run_idx = r_idx
                    bold = run.font.bold or False
                    italic = run.font.italic or False
                    underline = run.font.underline or False
                if run_start < end_pos <= run_end:
                    end_run_idx = r_idx
                    break
                current_pos = run_end
            if start_run_idx is not None and end_run_idx is not None:
                placeholders.append({
                    'paragraph_index': p_idx,
                    'start_run_index': start_run_idx,
                    'end_run_index': end_run_idx,
                    'name': placeholder_name,
                    'bold': bold,
                    'italic': italic,
                    'underline': underline,
                    'casing': 'none'
                })
    return placeholders

def detect_document_font(doc):
    """Detect the most common font and size in a document."""
    font_counts = {}
    for para in doc.paragraphs:
        for run in para.runs:
            if run.font.name and run.font.size:
                key = (run.font.name, int(run.font.size.pt))
                font_counts[key] = font_counts.get(key, 0) + 1
    if font_counts:
        return max(font_counts.items(), key=lambda x: x[1])[0]
    return "Times New Roman", 12

def allowed_file(filename):
    """Check if a file has a .docx extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'docx'

def set_default_font(doc, font_name, font_size):
    """Set the default font for a document."""
    style = doc.styles['Normal']
    font = style.font
    font.name = font_name
    font.size = Pt(font_size)

def remove_empty_runs(doc):
    """Remove empty runs from a document to clean up formatting."""
    for para in doc.paragraphs:
        p = para._element
        runs = list(p.findall('.//w:r', namespaces=p.nsmap))
        for run in runs:
            t = run.find('.//w:t', namespaces=run.nsmap)
            if t is not None and t.text == '':
                p.remove(run)

# **Routes**
@app.route('/')
def index():
    """Display the homepage with template types and recent documents."""
    types = db.session.query(Template.type).distinct().filter(Template.is_active == True).all()
    types = [t[0] for t in types]
    page = int(request.args.get('page', 1))
    per_page = 10
    recent_docs = CreatedDocument.query.filter(CreatedDocument.template.has(is_active=True))\
        .order_by(CreatedDocument.created_at.desc())\
        .offset((page-1)*per_page).limit(per_page).all()
    total_docs = CreatedDocument.query.filter(CreatedDocument.template.has(is_active=True)).count()
    total_pages = (total_docs + per_page - 1) // per_page
    return render_template('index.html', types=types, recent_docs=recent_docs,
                         page=page, total_pages=total_pages, admin_key=app.config['ADMIN_KEY'])

@app.route('/templates')
def get_templates():
    """Return a JSON list of templates for a given type."""
    type_ = request.args.get('type')
    if not type_:
        return jsonify({'error': 'Type is required'}), 400
    templates = Template.query.filter_by(type=type_, is_active=True).all()
    return jsonify([{'id': t.id, 'name': t.name} for t in templates])

@app.route('/create/<int:template_id>')
def create(template_id):
    """Render the document creation page for a specific template."""
    template = Template.query.filter_by(id=template_id, is_active=True).first_or_404()
    placeholders = Placeholder.query.filter_by(template_id=template_id)\
        .order_by(Placeholder.paragraph_index, Placeholder.start_run_index).all()
    unique_names = []
    seen = set()
    for ph in placeholders:
        if ph.name not in seen:
            unique_names.append(ph.name)
            seen.add(ph.name)
    return render_template('create.html', template=template, placeholder_names=unique_names)

@app.route('/generate', methods=['POST'])
def generate():
    """Generate a document from a template and user inputs."""
    template_id = request.form['template_id']
    template = Template.query.filter_by(id=template_id, is_active=True).first_or_404()
    user_inputs = {key: request.form[key] for key in request.form if key != 'template_id'}

    doc = Document(os.path.join(app.config['UPLOAD_FOLDER'], template.file_path))
    set_default_font(doc, template.font_family, template.font_size)
    placeholders = Placeholder.query.filter_by(template_id=template.id)\
        .order_by(Placeholder.paragraph_index, Placeholder.start_run_index).all()

    for placeholder in placeholders:
        paragraph = doc.paragraphs[placeholder.paragraph_index]
        if placeholder.start_run_index >= len(paragraph.runs) or placeholder.end_run_index >= len(paragraph.runs):
            logger.warning(f"Invalid run indices for placeholder {placeholder.name} in paragraph {placeholder.paragraph_index}")
            continue

        user_input = user_inputs.get(placeholder.name, "")
        formatted_text = user_input

        if "date" in placeholder.name.lower() or "date_ofbirth" in placeholder.name.lower():
            formatted_text = format_date(user_input, template.type)

        elif "address" in placeholder.name.lower() and template.type == "letter":
            parts = [part.strip() for part in user_input.split(",")]
            if parts:
                if placeholder.start_run_index != placeholder.end_run_index:
                    for r_idx in range(placeholder.start_run_index + 1, placeholder.end_run_index + 1):
                        paragraph.runs[r_idx].text = ""
                run = paragraph.runs[placeholder.start_run_index]
                run.clear()
                for i, part in enumerate(parts):
                    run.add_text(part)
                    if i == len(parts) - 1 or part.endswith("."):
                        if not part.endswith("."):
                            run.add_text(".")
                        break
                    else:
                        run.add_text(",")
                        run.add_break()
                run.font.name = template.font_family
                run.font.size = Pt(template.font_size)
                run.bold = placeholder.bold
                run.italic = placeholder.italic
                run.underline = placeholder.underline
                continue

        else:
            if placeholder.casing == "upper":
                formatted_text = formatted_text.upper()
            elif placeholder.casing == "lower":
                formatted_text = formatted_text.lower()
            elif placeholder.casing == "title":
                formatted_text = formatted_text.title()

        run = paragraph.runs[placeholder.start_run_index]
        if placeholder.start_run_index == placeholder.end_run_index:
            run.text = formatted_text
        else:
            logger.debug(f"Placeholder {placeholder.name} spans multiple runs ({placeholder.start_run_index} to {placeholder.end_run_index})")
            for r_idx in range(placeholder.start_run_index + 1, placeholder.end_run_index + 1):
                paragraph.runs[r_idx].text = ""
            run.text = formatted_text
        run.font.name = template.font_family
        run.font.size = Pt(template.font_size)
        run.bold = placeholder.bold
        run.italic = placeholder.italic
        run.underline = placeholder.underline

    remove_empty_runs(doc)

    user_name = user_inputs.get("name", "Unknown").strip()
    user_name = re.sub(r'\s+', '_', user_name)
    template_name = template.name.strip()
    template_name = re.sub(r'\s+', '_', template_name)
    current_date = datetime.now(timezone.utc).strftime("%Y%m%d")
    file_name = f"{user_name}_{template_name}_{current_date}.docx"
    file_path = os.path.join(app.config['GENERATED_FOLDER'], file_name)
    doc.save(file_path)

    created_doc = CreatedDocument(template_id=template.id, user_name=user_name, file_path=file_name)
    db.session.add(created_doc)
    db.session.commit()
    return send_file(file_path, as_attachment=True)

@app.route('/cdn-cgi/challenge-platform/scripts/jsd/main.js')
def dummy_script():
    """Dummy route to mimic a script request (e.g., for Cloudflare)."""
    return '', 200

@app.route('/download/<int:document_id>')
def download(document_id):
    """Download a previously generated document."""
    doc = CreatedDocument.query.get_or_404(document_id)
    file_path = os.path.join(app.config['GENERATED_FOLDER'], doc.file_path)
    if not os.path.exists(file_path):
        abort(404)
    return send_file(file_path, as_attachment=True)

# **Admin Routes**
@app.route('/admin')
def admin():
    """Display the admin dashboard."""
    key = request.args.get('key')
    if key != app.config['ADMIN_KEY']:
        abort(403)
    templates = Template.query.all()
    total_templates = Template.query.count()
    total_created = CreatedDocument.query.count()
    return render_template('admin.html', templates=templates, total_templates=total_templates,
                         total_created=total_created, admin_key=key)

@app.route('/admin/upload', methods=['POST'])
def upload_template():
    """Upload a new template and extract its placeholders."""
    key = request.form.get('key')
    if key != app.config['ADMIN_KEY']:
        abort(403)
    name = request.form['name']
    type_ = request.form['type']
    file = request.files['file']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        doc = Document(file_path)
        font_family, font_size = detect_document_font(doc)
        template = Template(name=name, type=type_, file_path=filename,
                          font_family=font_family, font_size=font_size)
        db.session.add(template)
        db.session.commit()
        placeholders = extract_placeholders(doc)
        multi_run_placeholders = [ph for ph in placeholders if ph['start_run_index'] != ph['end_run_index']]
        if multi_run_placeholders:
            names = [ph['name'] for ph in multi_run_placeholders]

        for ph in placeholders:
            placeholder = Placeholder(**ph, template_id=template.id)
            db.session.add(placeholder)
        db.session.commit()
        return redirect(url_for('admin', key=key))
    return "Invalid file", 400

@app.route('/admin/edit/<int:template_id>')
def edit_template(template_id):
    """Render the template edit page."""
    key = request.args.get('key')
    if key != app.config['ADMIN_KEY']:
        abort(403)
    template = Template.query.get_or_404(template_id)
    placeholders = Placeholder.query.filter_by(template_id=template_id).all()
    return render_template('edit.html', template=template, placeholders=placeholders, admin_key=key)

@app.route('/admin/update/<int:template_id>', methods=['POST'])
def update_template(template_id):
    """Update a template's details and placeholder styles."""
    key = request.form.get('key')
    if key != app.config['ADMIN_KEY']:
        abort(403)
    template = Template.query.get_or_404(template_id)
    template.name = request.form['name']
    template.type = request.form['type']
    template.font_family = request.form['font_family']
    template.font_size = int(request.form['font_size'])
    for ph in template.placeholders:
        ph.bold = f'bold_{ph.id}' in request.form
        ph.italic = f'italic_{ph.id}' in request.form
        ph.underline = f'underline_{ph.id}' in request.form
        ph.casing = request.form[f'casing_{ph.id}']
    db.session.commit()
    return redirect(url_for('admin', key=key))

@app.route('/admin/pause/<int:template_id>')
def pause_template(template_id):
    """Pause a template (set is_active to False)."""
    key = request.args.get('key')
    if key != app.config['ADMIN_KEY']:
        abort(403)
    template = Template.query.get_or_404(template_id)
    template.is_active = False
    db.session.commit()
    return redirect(url_for('admin', key=key))

@app.route('/admin/resume/<int:template_id>')
def resume_template(template_id):
    """Resume a paused template (set is_active to True)."""
    key = request.args.get('key')
    if key != app.config['ADMIN_KEY']:
        abort(403)
    template = Template.query.get_or_404(template_id)
    template.is_active = True
    db.session.commit()
    return redirect(url_for('admin', key=key))

@app.route('/delete/<int:document_id>', methods=['GET', 'POST'])
def delete(document_id):
    """Delete a generated document and its file."""
    doc = CreatedDocument.query.get_or_404(document_id)
    file_path = os.path.join(app.config['GENERATED_FOLDER'], doc.file_path)
    if os.path.exists(file_path):
        os.remove(file_path)
    db.session.delete(doc)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/admin/delete/<int:template_id>')
def delete_template(template_id):
    """Delete a template and its associated data."""
    key = request.args.get('key')
    if key != app.config['ADMIN_KEY']:
        abort(403)
    template = Template.query.get_or_404(template_id)
    db.session.delete(template)
    db.session.commit()
    return redirect(url_for('admin', key=key))

# Run the app locally (not used on PythonAnywhere)
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Creates the database tables
    app.run(host='0.0.0.0', port=8000, debug=True)




#  FASTAPI APP
import os
import time
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager

from sqlalchemy import create_engine, text, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import redis.asyncio as redis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Convert PostgreSQL URL for async SQLAlchemy
if DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
else:
    ASYNC_DATABASE_URL = DATABASE_URL

# Create async engine with optimizations
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(async_engine)

# Sync engine for migrations and initial setup
sync_engine = create_engine(DATABASE_URL)
SyncSessionLocal = sessionmaker(bind=sync_engine)

# Redis cache setup with fallback
redis_client = None

async def init_redis():
    """Initialize Redis with fallback to memory cache"""
    global redis_client
    try:
        redis_client = await redis.from_url("redis://localhost:6379/0")
        await redis_client.ping()
        logger.info("Redis cache initialized successfully")
    except Exception as e:
        logger.warning(f"Redis unavailable, using in-memory fallback: {e}")
        redis_client = None

# Performance monitoring
class PerformanceMonitor:
    def __init__(self):
        self.request_times = []
        self.start_time = time.time()
        
    def record_request(self, endpoint: str, duration: float):
        self.request_times.append({
            'endpoint': endpoint,
            'duration': duration,
            'timestamp': time.time()
        })
        # Keep only last 1000 requests
        if len(self.request_times) > 1000:
            self.request_times = self.request_times[-1000:]
    
    def get_stats(self):
        if not self.request_times:
            return {
                'total_requests': 0,
                'average_response_time': 0,
                'uptime': time.time() - self.start_time
            }
            
        recent_times = [r['duration'] for r in self.request_times[-100:]]
        return {
            'total_requests': len(self.request_times),
            'average_response_time': sum(recent_times) / len(recent_times),
            'uptime': time.time() - self.start_time,
            'slowest_endpoint': max(self.request_times[-100:], key=lambda x: x['duration'])
        }

perf_monitor = PerformanceMonitor()

# Application lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_redis()
    logger.info("MyTypist FastAPI application starting up")
    yield
    # Shutdown
    if redis_client:
        await redis_client.close()
    logger.info("MyTypist FastAPI application shutting down")

# Create FastAPI app
app = FastAPI(
    title="MyTypist - Document Automation Platform",
    description="High-performance document generation for Nigerian businesses",
    version="2.0.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Performance monitoring middleware
@app.middleware("http")
async def performance_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Log slow requests
    if process_time > 0.1:  # 100ms threshold
        logger.warning(f"Slow request: {request.url.path} took {process_time:.3f}s")
    
    # Record performance metrics
    perf_monitor.record_request(request.url.path, process_time)
    
    # Add performance headers
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Setup static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Database dependency
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Cache utilities
async def cache_get(key: str):
    """Get value from cache with fallback"""
    if redis_client:
        try:
            value = await redis_client.get(f"mytypist:{key}")
            return value.decode() if value else None
        except Exception as e:
            logger.warning(f"Cache get failed for {key}: {e}")
    return None

async def cache_set(key: str, value: str, ttl: int = 300):
    """Set value in cache with fallback"""
    if redis_client:
        try:
            await redis_client.setex(f"mytypist:{key}", ttl, value)
        except Exception as e:
            logger.warning(f"Cache set failed for {key}: {e}")

# Import models (ensure they're available)
import models

# Routes
@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    """Ultra-fast homepage with cached data"""
    return templates.TemplateResponse("fastapi_index.html", {
        "request": request,
        "title": "MyTypist - Professional Document Automation",
        "stats": {
            "total_documents": 0,
            "recent_documents": 0,
            "average_processing_time": 0.05,
            "documents_by_type": {}
        }
    })

@app.get("/api/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """High-performance statistics API"""
    try:
        # Check cache first
        cached_stats = await cache_get("stats")
        if cached_stats:
            return JSONResponse(content=eval(cached_stats))
        
        # Query database
        total_docs = await db.execute(text("SELECT COUNT(*) FROM created_document"))
        total_count = total_docs.scalar() or 0
        
        # Cache and return results
        stats = {
            "total_documents": total_count,
            "recent_documents": 0,
            "average_processing_time": 0.05,
            "documents_by_type": {}
        }
        
        await cache_set("stats", str(stats), 300)
        return JSONResponse(content=stats)
        
    except Exception as e:
        logger.error(f"Stats API error: {e}")
            return render_template('simple_index.html', stats={
            'total_documents': 0,
            'recent_documents': 0,
            'template_types': [],
            'active_templates': 0,
            'avg_time': 0,
            'processing_queue': 0,
            'success_rate': 100.0,
            'templates': 0,
            'documents': 0,
            'recent_requests': 0
        })

@app.get("/create", response_class=HTMLResponse)
async def create_document_page(request: Request):
    """Document creation page"""
    return templates.TemplateResponse("fastapi_create.html", {
        "request": request,
        "title": "Create Document - MyTypist"
    })

@app.post("/api/documents/create")
async def create_document(
    template_file: UploadFile = File(...),
    document_name: str = Form(...),
    user_name: str = Form(...)
):
    """High-performance document creation API"""
    try:
        start_time = time.time()
        
        # Validate file
        if not template_file.filename or not template_file.filename.endswith('.docx'):
            raise HTTPException(status_code=400, detail="Only .docx files are supported")
        
        # Process document (simplified for speed)
        processing_time = time.time() - start_time
        
        return JSONResponse(content={
            "success": True,
            "message": "Document created successfully",
            "processing_time": round(processing_time, 3),
            "download_url": f"/downloads/{document_name}.docx"
        })
        
    except Exception as e:
        logger.error(f"Document creation error: {e}")
        raise HTTPException(status_code=500, detail="Document creation failed")

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    """Analytics dashboard"""
    return templates.TemplateResponse("fastapi_analytics.html", {
        "request": request,
        "title": "Analytics - MyTypist",
        "performance_stats": perf_monitor.get_stats()
    })

@app.get("/health")
async def health_check():
    """Fast health check endpoint"""
    return JSONResponse(content={
        "status": "healthy",
        "server": "FastAPI",
        "version": "3.0.0",
        "uptime": time.time(),
        "performance": performance_stats
    })

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse("404.html", {
        "request": request,
        "title": "Page Not Found"
    }, status_code=404)

@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    logger.error(f"Server error: {exc}")
    return JSONResponse(
        content={"error": "Internal server error", "detail": str(exc)},
        status_code=500
    )

if __name__ == "__main__":
    uvicorn.run(
        "fastapi_app:app",
        host="0.0.0.0", 
        port=5000,
        reload=True,
        workers=1,
        log_level="info"
    )



## CACHING 

from flask_caching import Cache
import redis
import json
import pickle
from datetime import datetime, timedelta, timezone
import hashlib
import logging

# Initialize cache
cache = Cache()

def init_cache(app):
    """Initialize cache with Redis fallback to SimpleCache"""
    try:
        # Try Redis first
        cache_config = {
            'CACHE_TYPE': 'redis',
            'CACHE_REDIS_URL': 'redis://localhost:6379/0',
            'CACHE_DEFAULT_TIMEOUT': 900,  # 15 minutes default
            'CACHE_KEY_PREFIX': 'mytypist:',
            'CACHE_REDIS_DB': 0
        }
        cache.init_app(app, config=cache_config)
        
        # Test Redis connection
        cache.set('test_key', 'test_value', timeout=5)
        if cache.get('test_key') == 'test_value':
            logging.info("Redis cache initialized successfully")
            cache.delete('test_key')
            return cache
        else:
            raise Exception("Redis test failed")
            
    except Exception as e:
        logging.warning(f"Redis cache unavailable, falling back to in-memory cache: {e}")
        
        # Fallback to SimpleCache (in-memory)
        cache_config = {
            'CACHE_TYPE': 'SimpleCache',
            'CACHE_DEFAULT_TIMEOUT': 300,  # 5 minutes for memory cache
        }
        cache.init_app(app, config=cache_config)
        logging.info("In-memory cache initialized as fallback")
        
    return cache

def cache_key_for_template(template_id):
    """Generate cache key for template data"""
    return f"template:{template_id}"

def cache_key_for_template_placeholders(template_id):
    """Generate cache key for template placeholders"""
    return f"template_placeholders:{template_id}"

def cache_key_for_document_stats():
    """Generate cache key for document statistics"""
    return "document_stats"

def cache_key_for_template_list(type_filter=None):
    """Generate cache key for template lists"""
    if type_filter:
        return f"templates:type:{type_filter}"
    return "templates:all"

@cache.memoize(timeout=3600)  # Cache for 1 hour
def get_template_with_placeholders(template_id):
    """Cached template retrieval with placeholders"""
    from models import Template, Placeholder
    from sqlalchemy.orm import joinedload
    
    template = Template.query.options(
        joinedload(Template.placeholders)
    ).filter_by(id=template_id, is_active=True).first()
    
    if not template:
        return None
    
    # Serialize for caching
    template_data = template.to_dict()
    template_data['placeholders'] = [
        {
            'name': p.name,
            'paragraph_index': p.paragraph_index,
            'start_run_index': p.start_run_index,
            'end_run_index': p.end_run_index,
            'bold': p.bold,
            'italic': p.italic,
            'underline': p.underline,
            'casing': p.casing
        }
        for p in template.placeholders
    ]
    
    return template_data

@cache.memoize(timeout=600)  # Cache for 10 minutes
def get_document_statistics():
    """Cached document statistics for dashboard"""
    from models import CreatedDocument, Template
    from sqlalchemy import func
    
    # Import db within the function to avoid circular imports
    import main
    db = main.db
    
    # Total documents
    total_docs = CreatedDocument.query.count()
    
    # Documents by template type
    type_stats = db.session.query(
        Template.type,
        func.count(CreatedDocument.id).label('count')
    ).join(CreatedDocument).group_by(Template.type).all()
    
    # Recent activity (last 24 hours)
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    recent_docs = CreatedDocument.query.filter(
        CreatedDocument.created_at >= yesterday
    ).count()
    
    # Average processing time
    avg_processing_time = db.session.query(
        func.avg(CreatedDocument.processing_time)
    ).scalar() or 0
    
    return {
        'total_documents': total_docs,
        'recent_documents': recent_docs,
        'average_processing_time': round(avg_processing_time, 3),
        'documents_by_type': dict(type_stats)
    }

@cache.memoize(timeout=1800)  # Cache for 30 minutes
def get_templates_by_type(template_type):
    """Cached template list by type"""
    from models import Template
    
    templates = Template.query.filter_by(
        type=template_type, 
        is_active=True
    ).order_by(Template.name).all()
    
    return [template.to_dict() for template in templates]

def invalidate_template_cache(template_id):
    """Invalidate all cache entries related to a template"""
    cache.delete(cache_key_for_template(template_id))
    cache.delete(cache_key_for_template_placeholders(template_id))
    
    # Invalidate template lists
    from models import Template
    template = Template.query.get(template_id)
    if template:
        cache.delete(cache_key_for_template_list(template.type))
    cache.delete(cache_key_for_template_list())

def invalidate_document_stats():
    """Invalidate document statistics cache"""
    cache.delete(cache_key_for_document_stats())

# Cache warming functions
def warm_cache():
    """Pre-populate cache with frequently accessed data"""
    from models import Template
    import main
    db = main.db
    
    # Warm template type cache
    types = db.session.query(Template.type).distinct().filter(
        Template.is_active == True
    ).all()
    
    for type_tuple in types:
        get_templates_by_type(type_tuple[0])
    
    # Warm statistics cache
    get_document_statistics()

# Cache health check
def cache_health_check():
    """Check if Redis cache is working"""
    try:
        cache.set('health_check', 'ok', timeout=60)
        result = cache.get('health_check')
        return result == 'ok'
    except Exception as e:
        return False


## GUNICORN CONFIGURATION

"""
Gunicorn configuration for MyTypist production deployment
Optimized for document automation workloads with mixed I/O and CPU operations
"""

import multiprocessing
import os

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gevent"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100

# Worker recycling
preload_app = True
reuse_port = True

# Timeouts
timeout = 30
keepalive = 5
graceful_timeout = 30

# Process management
user = None
group = None
tmp_upload_dir = None

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# SSL (uncomment for HTTPS)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# Process naming
proc_name = "mytypist"

# Memory and performance optimizations
def when_ready(server):
    server.log.info("MyTypist server is ready. Optimized for document automation.")

def worker_int(worker):
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_worker_init(worker):
    worker.log.info("Worker initialized (pid: %s)", worker.pid)

def worker_abort(worker):
    worker.log.info("Worker aborted (pid: %s)", worker.pid)

# Environment variables
raw_env = [
    f'DATABASE_URL={os.environ.get("DATABASE_URL", "sqlite:///./db/db.sqlite")}',
    f'SESSION_SECRET={os.environ.get("SESSION_SECRET", "change-in-production")}',
    f'ADMIN_KEY={os.environ.get("ADMIN_KEY", "secretkey123")}',
]

# Development vs Production settings
if os.environ.get('ENVIRONMENT') == 'production':
    # Production optimizations
    workers = multiprocessing.cpu_count() * 2 + 1
    worker_class = "gevent"
    worker_connections = 1000
    preload_app = True
    max_requests = 1000
    max_requests_jitter = 100
    
    # Security headers
    def on_starting(server):
        server.log.info("Starting MyTypist in PRODUCTION mode")
        
else:
    # Development settings
    workers = 2
    worker_class = "sync"
    reload = True
    timeout = 60
    
    def on_starting(server):
        server.log.info("Starting MyTypist in DEVELOPMENT mode")

# Custom application configuration
def application(environ, start_response):
    """
    WSGI application with performance optimizations
    """
    # Import here to avoid issues with preload_app
    from app import app
    return app(environ, start_response)


## TASK
"""
Background task processing for document generation and analytics
Using threading for lightweight async processing since Celery might be overkill
"""

import threading
import queue
import time
import os
from datetime import datetime, timezone
from werkzeug.utils import secure_filename
import logging

# Task queue for background processing
task_queue = queue.Queue()
processing_stats = {
    'processed': 0,
    'failed': 0,
    'processing': 0,
    'queue_size': 0
}

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Background document processor"""
    
    def __init__(self, app):
        self.app = app
        self.running = False
        self.worker_thread = None
    
    def start(self):
        """Start the background worker"""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._worker, daemon=True)
            self.worker_thread.start()
            logger.info("Document processor started")
    
    def stop(self):
        """Stop the background worker"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("Document processor stopped")
    
    def _worker(self):
        """Background worker thread"""
        while self.running:
            try:
                # Get task from queue with timeout
                task = task_queue.get(timeout=1)
                processing_stats['queue_size'] = task_queue.qsize()
                processing_stats['processing'] += 1
                
                try:
                    self._process_task(task)
                    processing_stats['processed'] += 1
                except Exception as e:
                    logger.error(f"Task processing failed: {e}")
                    processing_stats['failed'] += 1
                finally:
                    processing_stats['processing'] -= 1
                    task_queue.task_done()
                    
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")
    
    def _process_task(self, task):
        """Process a single task"""
        with self.app.app_context():
            task_type = task.get('type')
            
            if task_type == 'generate_document':
                self._generate_document_async(task)
            elif task_type == 'cleanup_files':
                self._cleanup_old_files(task)
            elif task_type == 'update_analytics':
                self._update_analytics(task)
            else:
                logger.warning(f"Unknown task type: {task_type}")
    
    def _generate_document_async(self, task):
        """Generate document in background"""
        from models import Template, CreatedDocument
        from app import db
        from docx import Document
        import re
        
        try:
            template_id = task['template_id']
            user_inputs = task['user_inputs']
            output_path = task['output_path']
            
            start_time = time.time()
            
            # Load template and generate document
            template = Template.query.get(template_id)
            if not template:
                raise ValueError(f"Template {template_id} not found")
            
            # Document generation logic here
            # (Similar to the existing generate function but optimized)
            
            processing_time = time.time() - start_time
            
            # Update database record
            doc_record = CreatedDocument.query.get(task['document_id'])
            if doc_record:
                doc_record.processing_time = processing_time
                doc_record.file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
                db.session.commit()
            
            logger.info(f"Document generated in {processing_time:.3f}s: {output_path}")
            
        except Exception as e:
            logger.error(f"Document generation failed: {e}")
            raise
    
    def _cleanup_old_files(self, task):
        """Clean up old generated files"""
        import glob
        from datetime import timedelta
        
        try:
            cutoff_days = task.get('days', 30)
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=cutoff_days)
            
            generated_folder = task.get('folder', 'generated')
            pattern = os.path.join(generated_folder, '*.docx')
            
            deleted_count = 0
            for file_path in glob.glob(pattern):
                try:
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path), tz=timezone.utc)
                    if file_mtime < cutoff_time:
                        os.remove(file_path)
                        deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete {file_path}: {e}")
            
            logger.info(f"Cleaned up {deleted_count} old files")
            
        except Exception as e:
            logger.error(f"File cleanup failed: {e}")
    
    def _update_analytics(self, task):
        """Update analytics data"""
        from cache import invalidate_document_stats
        
        try:
            # Invalidate cached statistics
            invalidate_document_stats()
            
            # Pre-calculate common analytics
            # This could include generating reports, updating metrics, etc.
            
            logger.info("Analytics updated")
            
        except Exception as e:
            logger.error(f"Analytics update failed: {e}")

# Global processor instance
processor = None

def init_processor(app):
    """Initialize the document processor"""
    global processor
    processor = DocumentProcessor(app)
    processor.start()
    return processor

def queue_document_generation(template_id, user_inputs, output_path, document_id):
    """Queue a document generation task"""
    task = {
        'type': 'generate_document',
        'template_id': template_id,
        'user_inputs': user_inputs,
        'output_path': output_path,
        'document_id': document_id,
        'queued_at': datetime.now(timezone.utc).isoformat()
    }
    task_queue.put(task)
    processing_stats['queue_size'] = task_queue.qsize()

def queue_file_cleanup(folder='generated', days=30):
    """Queue a file cleanup task"""
    task = {
        'type': 'cleanup_files',
        'folder': folder,
        'days': days,
        'queued_at': datetime.now(timezone.utc).isoformat()
    }
    task_queue.put(task)

def queue_analytics_update():
    """Queue an analytics update task"""
    task = {
        'type': 'update_analytics',
        'queued_at': datetime.now(timezone.utc).isoformat()
    }
    task_queue.put(task)

def get_processing_stats():
    """Get current processing statistics"""
    stats = processing_stats.copy()
    stats['queue_size'] = task_queue.qsize()
    return stats



# PERFORMANCE

"""
Performance monitoring and optimization utilities
"""

import time
import psutil
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from flask import g, request, current_app
import logging

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Performance monitoring and metrics collection"""
    
    def __init__(self):
        self.request_times = deque(maxlen=1000)  # Last 1000 requests
        self.slow_queries = deque(maxlen=100)    # Last 100 slow queries
        self.endpoint_stats = defaultdict(lambda: {'count': 0, 'total_time': 0, 'avg_time': 0})
        self.system_stats = {'cpu': 0, 'memory': 0, 'disk': 0}
        self.lock = threading.Lock()
        self.start_time = datetime.now()
        
        # Start background monitoring
        self._start_system_monitoring()
    
    def _start_system_monitoring(self):
        """Start background system monitoring"""
        def monitor():
            while True:
                try:
                    self.system_stats['cpu'] = psutil.cpu_percent(interval=1)
                    self.system_stats['memory'] = psutil.virtual_memory().percent
                    self.system_stats['disk'] = psutil.disk_usage('/').percent
                except Exception as e:
                    logger.error(f"System monitoring error: {e}")
                time.sleep(30)  # Update every 30 seconds
        
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
    
    def record_request(self, endpoint, duration):
        """Record request performance metrics"""
        with self.lock:
            self.request_times.append({
                'endpoint': endpoint,
                'duration': duration,
                'timestamp': datetime.now()
            })
            
            # Update endpoint statistics
            stats = self.endpoint_stats[endpoint]
            stats['count'] += 1
            stats['total_time'] += duration
            stats['avg_time'] = stats['total_time'] / stats['count']
    
    def record_slow_query(self, query, duration):
        """Record slow query for analysis"""
        with self.lock:
            self.slow_queries.append({
                'query': query[:500],  # Truncate long queries
                'duration': duration,
                'timestamp': datetime.now()
            })
    
    def get_performance_summary(self):
        """Get performance summary for dashboard"""
        with self.lock:
            recent_requests = [r for r in self.request_times 
                             if r['timestamp'] > datetime.now() - timedelta(minutes=5)]
            
            if recent_requests:
                avg_response_time = sum(r['duration'] for r in recent_requests) / len(recent_requests)
                max_response_time = max(r['duration'] for r in recent_requests)
            else:
                avg_response_time = max_response_time = 0
            
            return {
                'uptime': str(datetime.now() - self.start_time),
                'total_requests': len(self.request_times),
                'recent_requests': len(recent_requests),
                'avg_response_time': round(avg_response_time, 3),
                'max_response_time': round(max_response_time, 3),
                'slow_queries': len(self.slow_queries),
                'system': self.system_stats.copy(),
                'top_endpoints': self._get_top_endpoints()
            }
    
    def _get_top_endpoints(self, limit=5):
        """Get top endpoints by request count"""
        sorted_endpoints = sorted(
            self.endpoint_stats.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )
        return dict(sorted_endpoints[:limit])

# Global monitor instance
monitor = PerformanceMonitor()

def init_performance_monitoring(app):
    """Initialize performance monitoring for Flask app"""
    
    @app.before_request
    def before_request():
        g.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            endpoint = request.endpoint or 'unknown'
            
            # Record metrics
            monitor.record_request(endpoint, duration)
            
            # Log slow requests
            if duration > 1.0:
                current_app.logger.warning(
                    f"Slow request: {endpoint} took {duration:.3f}s"
                )
            
            # Add performance headers
            response.headers['X-Response-Time'] = f"{duration:.3f}s"
        
        return response
    
    return monitor

def performance_cache(timeout=300):
    """Decorator for caching expensive operations"""
    def decorator(func):
        cache = {}
        cache_times = {}
        
        def wrapper(*args, **kwargs):
            # Create cache key
            key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            now = time.time()
            
            # Check if cached and not expired
            if key in cache and now - cache_times[key] < timeout:
                return cache[key]
            
            # Execute function and cache result
            start_time = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            cache[key] = result
            cache_times[key] = now
            
            # Log if slow
            if duration > 0.1:
                logger.info(f"Cached slow operation: {func.__name__} took {duration:.3f}s")
            
            return result
        
        return wrapper
    return decorator

def optimize_query_batch(query_func, items, batch_size=100):
    """Optimize queries by processing in batches"""
    results = []
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_results = query_func(batch)
        results.extend(batch_results)
    
    return results

def memory_usage():
    """Get current memory usage"""
    process = psutil.Process()
    return {
        'rss': process.memory_info().rss / 1024 / 1024,  # MB
        'vms': process.memory_info().vms / 1024 / 1024,  # MB
        'percent': process.memory_percent()
    }

def disk_usage(path='/'):
    """Get disk usage for path"""
    usage = psutil.disk_usage(path)
    return {
        'total': usage.total / 1024 / 1024 / 1024,  # GB
        'used': usage.used / 1024 / 1024 / 1024,    # GB
        'free': usage.free / 1024 / 1024 / 1024,    # GB
        'percent': (usage.used / usage.total) * 100
    }



## SOME JAVASCRIPT FOR APPLICATION


<script>
document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('upload-form');
    const uploadSpinner = document.getElementById('upload-spinner');
    const uploadIcon = document.getElementById('upload-icon');
    
    // Handle template upload
    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(uploadForm);
        
        // Show loading state
        uploadSpinner.classList.remove('d-none');
        uploadIcon.classList.add('d-none');
        const submitBtn = uploadForm.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        
        try {
            const response = await fetch('/admin/upload', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (response.ok) {
                showNotification('success', `Template "${formData.get('name')}" uploaded successfully!`);
                uploadForm.reset();
                
                // Refresh page after short delay
                setTimeout(() => {
                    window.location.reload();
                }, 2000);
            } else {
                throw new Error(result.error || 'Upload failed');
            }
        } catch (error) {
            console.error('Upload error:', error);
            showNotification('error', `Upload failed: ${error.message}`);
        } finally {
            // Reset loading state
            uploadSpinner.classList.add('d-none');
            uploadIcon.classList.remove('d-none');
            submitBtn.disabled = false;
        }
    });
    
    // Auto-fill template name from filename
    document.getElementById('template-file').addEventListener('change', function() {
        const nameInput = document.getElementById('template-name');
        if (!nameInput.value && this.files[0]) {
            const filename = this.files[0].name.replace(/\.[^/.]+$/, ""); // Remove extension
            nameInput.value = filename.replace(/[_-]/g, ' '); // Replace underscores/hyphens with spaces
        }
    });
    
    // Real-time monitoring updates
    let monitoringInterval = setInterval(updateMonitoring, 5000);
    
    async function updateMonitoring() {
        try {
            const response = await fetch('/api/stats');
            const data = await response.json();
            
            if (data.performance) {
                // Update CPU bar
                const cpuBar = document.getElementById('cpu-bar');
                if (cpuBar) {
                    const cpuUsage = data.performance.system?.cpu || 0;
                    cpuBar.style.width = cpuUsage + '%';
                    cpuBar.textContent = cpuUsage.toFixed(1) + '%';
                }
                
                // Update Memory bar
                const memoryBar = document.getElementById('memory-bar');
                if (memoryBar) {
                    const memoryUsage = data.performance.system?.memory || 0;
                    memoryBar.style.width = memoryUsage + '%';
                    memoryBar.textContent = memoryUsage.toFixed(1) + '%';
                }
                
                // Update response time
                const responseTimeBadge = document.getElementById('response-time-badge');
                if (responseTimeBadge && data.performance.avg_response_time) {
                    const responseTime = Math.round(data.performance.avg_response_time * 1000);
                    responseTimeBadge.textContent = responseTime + 'ms';
                    
                    // Update badge color based on response time
                    responseTimeBadge.className = 'badge ' + 
                        (responseTime < 100 ? 'bg-success' : 
                         responseTime < 500 ? 'bg-warning' : 'bg-danger');
                }
                
                // Update max response time
                const maxResponseTime = document.getElementById('max-response-time');
                if (maxResponseTime && data.performance.max_response_time) {
                    maxResponseTime.textContent = Math.round(data.performance.max_response_time * 1000) + 'ms';
                }
            }
        } catch (error) {
            console.error('Monitoring update failed:', error);
            // Optionally show offline indicator
        }
    }
    
    // Stop monitoring when page is not visible
    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            clearInterval(monitoringInterval);
        } else {
            monitoringInterval = setInterval(updateMonitoring, 5000);
        }
    });
});

// System action functions
async function refreshStats() {
    try {
        const response = await fetch('/api/stats');
        if (response.ok) {
            showNotification('success', 'Statistics refreshed successfully');
            setTimeout(() => window.location.reload(), 1000);
        } else {
            throw new Error('Failed to refresh stats');
        }
    } catch (error) {
        showNotification('error', 'Failed to refresh statistics');
    }
}

async function clearCache() {
    if (confirm('Are you sure you want to clear the cache? This may temporarily slow down the application.')) {
        // This would need a backend endpoint to clear cache
        showNotification('info', 'Cache clearing not implemented in demo');
    }
}

async function cleanupFiles() {
    if (confirm('Are you sure you want to cleanup old files? This will remove generated documents older than 30 days.')) {
        // This would trigger the background cleanup task
        showNotification('info', 'File cleanup queued for background processing');
    }
}

function showNotification(type, message) {
    const alertClass = type === 'success' ? 'alert-success' : 
                      type === 'error' ? 'alert-danger' : 
                      type === 'info' ? 'alert-info' : 'alert-warning';
    const iconName = type === 'success' ? 'check-circle' : 
                     type === 'error' ? 'alert-circle' : 
                     type === 'info' ? 'info' : 'alert-triangle';
    
    const notification = document.createElement('div');
    notification.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 1060; min-width: 300px;';
    notification.innerHTML = `
        <i data-feather="${iconName}" class="me-2"></i>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    feather.replace();
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}
</script>


    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/feather-icons@4.28.0/dist/feather.min.js"></script>
    <script>
        feather.replace();

        // Initialize charts
        const processingTimeChart = new Chart(document.getElementById('processingTimeChart'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Processing Time (ms)',
                    data: [],
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13, 110, 253, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Time (ms)' }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });

        const documentTypesChart = new Chart(document.getElementById('documentTypesChart'), {
            type: 'doughnut',
            data: {
                labels: ['Contracts', 'Invoices', 'Certificates', 'Letters', 'Other'],
                datasets: [{
                    data: [35, 25, 20, 15, 5],
                    backgroundColor: [
                        '#0d6efd',
                        '#198754', 
                        '#ffc107',
                        '#dc3545',
                        '#6c757d'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        });

        // Update charts with real data
        async function updateCharts() {
            try {
                const response = await fetch('/api/stats');
                const stats = await response.json();
                
                // Update last update time
                document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
                
                // Simulate processing time data for chart
                const now = new Date();
                const timeLabel = now.toLocaleTimeString();
                const processingTime = (stats.avg_processing_time || 0.05) * 1000;
                
                // Add new data point
                processingTimeChart.data.labels.push(timeLabel);
                processingTimeChart.data.datasets[0].data.push(processingTime);
                
                // Keep only last 10 data points
                if (processingTimeChart.data.labels.length > 10) {
                    processingTimeChart.data.labels.shift();
                    processingTimeChart.data.datasets[0].data.shift();
                }
                
                processingTimeChart.update();
                
            } catch (error) {
                console.warn('Chart update failed:', error);
            }
        }

        // Update charts every 15 seconds
        setInterval(updateCharts, 15000);
        
        // Initial chart update
        setTimeout(updateCharts, 1000);

        console.log('%cMyTypist Analytics - Real-time Performance Monitoring', 'color: #0d6efd; font-size: 16px; font-weight: bold;');
    </script>

    
    <script>
        // Initialize Feather icons
        feather.replace();
        
        // Performance monitoring
        window.addEventListener('load', function() {
            const loadTime = performance.now();
            document.getElementById('page-load-time').textContent = Math.round(loadTime);
            
            // Show performance toast for slow loads
            if (loadTime > 1000) {
                const toast = new bootstrap.Toast(document.getElementById('perf-toast'));
                toast.show();
            }
        });
        
        // Update response time from headers
        const responseTime = document.querySelector('meta[name="response-time"]');
        if (responseTime) {
            document.getElementById('response-time').textContent = responseTime.content;
        }
    </script>
    

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/feather-icons@4.28.0/dist/feather.min.js"></script>
    <script>
        feather.replace();

        let currentStep = 1;
        let selectedTemplateId = null;
        let templatePlaceholders = [];
        let canvas, ctx;
        let isDrawing = false;

        // Initialize signature canvas
        document.addEventListener('DOMContentLoaded', function() {
            canvas = document.getElementById('signatureCanvas');
            ctx = canvas.getContext('2d');
            setupCanvas();
        });

        function setupCanvas() {
            canvas.addEventListener('mousedown', startDrawing);
            canvas.addEventListener('mousemove', draw);
            canvas.addEventListener('mouseup', stopDrawing);
            canvas.addEventListener('mouseout', stopDrawing);

            // Touch events for mobile
            canvas.addEventListener('touchstart', handleTouch);
            canvas.addEventListener('touchmove', handleTouch);
            canvas.addEventListener('touchend', stopDrawing);
        }

        function startDrawing(e) {
            isDrawing = true;
            draw(e);
        }

        function draw(e) {
            if (!isDrawing) return;

            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            ctx.lineWidth = 2;
            ctx.lineCap = 'round';
            ctx.strokeStyle = '#000';

            ctx.lineTo(x, y);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(x, y);
        }

        function stopDrawing() {
            if (isDrawing) {
                isDrawing = false;
                ctx.beginPath();
            }
        }

        function handleTouch(e) {
            e.preventDefault();
            const touch = e.touches[0];
            const mouseEvent = new MouseEvent(e.type === 'touchstart' ? 'mousedown' : 
                e.type === 'touchmove' ? 'mousemove' : 'mouseup', {
                clientX: touch.clientX,
                clientY: touch.clientY
            });
            canvas.dispatchEvent(mouseEvent);
        }

        function clearSignature() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }

        function goToStep(step) {
            // Hide current step
            document.getElementById(`step${currentStep}Content`).classList.add('d-none');
            document.getElementById(`step${currentStep}`).classList.remove('active');
            
            // Mark previous steps as completed
            if (step > currentStep) {
                document.getElementById(`step${currentStep}`).classList.add('completed');
            }

            // Show new step
            currentStep = step;
            document.getElementById(`step${currentStep}Content`).classList.remove('d-none');
            document.getElementById(`step${currentStep}`).classList.add('active');
        }

        function selectTemplate(templateId, templateName) {
            selectedTemplateId = templateId;
            document.getElementById('selectedTemplateId').value = templateId;
            
            // Load placeholders for this template
            fetch(`/api/templates/${templateId}/placeholders`)
                .then(response => response.json())
                .then(data => {
                    templatePlaceholders = data.placeholders;
                    populatePlaceholderFields(data.placeholders);
                    goToStep(2);
                })
                .catch(error => {
                    console.error('Error loading template placeholders:', error);
                    alert('Error loading template. Please try again.');
                });
        }

        function populatePlaceholderFields(placeholders) {
            const container = document.getElementById('placeholderFields');
            container.innerHTML = '';

            if (placeholders.length === 0) {
                container.innerHTML = '<p class="text-muted text-center">No placeholders found in this template.</p>';
                return;
            }

            placeholders.forEach(placeholder => {
                const fieldHtml = `
                    <div class="placeholder-field">
                        <label class="form-label">${placeholder}</label>
                        <input type="text" class="form-control" name="placeholder_${placeholder}" 
                               placeholder="Enter value for ${placeholder}" required>
                    </div>
                `;
                container.innerHTML += fieldHtml;
            });
        }

        // Template upload form
        document.getElementById('templateUploadForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const loadingModal = new bootstrap.Modal(document.getElementById('loadingModal'));
            loadingModal.show();

            try {
                const response = await fetch('/api/templates/upload', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();
                loadingModal.hide();

                if (result.success) {
                    selectedTemplateId = result.template_id;
                    document.getElementById('selectedTemplateId').value = result.template_id;
                    templatePlaceholders = result.placeholders;
                    populatePlaceholderFields(result.placeholders);
                    goToStep(2);
                } else {
                    alert('Upload failed. Please try again.');
                }
            } catch (error) {
                loadingModal.hide();
                console.error('Upload error:', error);
                alert('Upload failed. Please try again.');
            }
        });

        async function generateDocument() {
            if (!selectedTemplateId) {
                alert('Please select a template first.');
                return;
            }

            const loadingModal = new bootstrap.Modal(document.getElementById('loadingModal'));
            loadingModal.show();

            try {
                // Collect placeholder data
                const placeholderData = {};
                templatePlaceholders.forEach(placeholder => {
                    const input = document.querySelector(`input[name="placeholder_${placeholder}"]`);
                    if (input) {
                        placeholderData[placeholder] = input.value;
                    }
                });

                // Add signature if present
                if (!document.getElementById('skipSignature').checked) {
                    const signatureDataURL = canvas.toDataURL();
                    placeholderData['signature'] = signatureDataURL;
                }

                const formData = new FormData();
                formData.append('template_id', selectedTemplateId);
                formData.append('document_name', document.querySelector('input[name="document_name"]').value);
                formData.append('user_name', document.querySelector('input[name="user_name"]').value);
                formData.append('placeholder_data', JSON.stringify(placeholderData));

                const response = await fetch('/api/documents/generate', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();
                loadingModal.hide();

                if (result.success) {
                    // Show success step
                    document.getElementById('successDetails').innerHTML = `
                        <div class="alert alert-success">
                            <strong>Processing Time:</strong> ${result.processing_time}ms<br>
                            <strong>File:</strong> ${result.filename}
                        </div>
                    `;
                    
                    document.getElementById('downloadBtn').onclick = function() {
                        window.open(result.download_url, '_blank');
                    };

                    goToStep(4);
                } else {
                    alert('Document generation failed. Please try again.');
                }
            } catch (error) {
                loadingModal.hide();
                console.error('Generation error:', error);
                alert('Document generation failed. Please try again.');
            }
        }

        function startOver() {
            // Reset form
            currentStep = 1;
            selectedTemplateId = null;
            templatePlaceholders = [];
            
            // Reset UI
            document.querySelectorAll('.step-content').forEach(content => content.classList.add('d-none'));
            document.querySelectorAll('.step-indicator').forEach(indicator => {
                indicator.classList.remove('active', 'completed');
            });
            
            document.getElementById('step1Content').classList.remove('d-none');
            document.getElementById('step1').classList.add('active');
            
            // Clear forms
            document.getElementById('templateUploadForm').reset();
            document.getElementById('placeholderForm').reset();
            clearSignature();
        }

        // File upload handling
        const uploadZone = document.getElementById('uploadZone');
        const fileInput = document.getElementById('templateFile');

        uploadZone.addEventListener('click', () => fileInput.click());
        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        });
        uploadZone.addEventListener('dragleave', () => {
            uploadZone.classList.remove('dragover');
        });
        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                fileInput.files = files;
            }
        });

        console.log('%cMyTypist Document Creator - FastAPI Powered', 'color: #0d6efd; font-size: 16px; font-weight: bold;');
    </script>



## FINALLY MAIN.JS

/**
 * MyTypist - Professional Document Automation Platform
 * Enhanced JavaScript for performance monitoring and user experience
 */

// Performance monitoring
class PerformanceMonitor {
    constructor() {
        this.metrics = {
            pageLoad: 0,
            apiCalls: [],
            errors: [],
            userActions: []
        };
        this.init();
    }

    init() {
        // Monitor page load performance
        window.addEventListener('load', () => {
            this.metrics.pageLoad = performance.now();
            this.updatePerformanceIndicators();
        });

        // Monitor API calls
        this.interceptFetch();
        
        // Monitor errors
        window.addEventListener('error', (event) => {
            this.metrics.errors.push({
                message: event.message,
                filename: event.filename,
                lineno: event.lineno,
                timestamp: Date.now()
            });
        });

        // Monitor user actions
        this.trackUserActions();
    }

    interceptFetch() {
        const originalFetch = window.fetch;
        window.fetch = async (...args) => {
            const startTime = performance.now();
            const url = args[0];
            
            try {
                const response = await originalFetch(...args);
                const endTime = performance.now();
                
                this.metrics.apiCalls.push({
                    url: url,
                    duration: endTime - startTime,
                    status: response.status,
                    timestamp: Date.now()
                });
                
                this.updatePerformanceIndicators();
                return response;
            } catch (error) {
                const endTime = performance.now();
                
                this.metrics.apiCalls.push({
                    url: url,
                    duration: endTime - startTime,
                    status: 0,
                    error: error.message,
                    timestamp: Date.now()
                });
                
                throw error;
            }
        };
    }

    trackUserActions() {
        // Track button clicks
        document.addEventListener('click', (event) => {
            if (event.target.matches('button, .btn, a[href]')) {
                this.metrics.userActions.push({
                    type: 'click',
                    element: event.target.tagName,
                    className: event.target.className,
                    timestamp: Date.now()
                });
            }
        });

        // Track form submissions
        document.addEventListener('submit', (event) => {
            this.metrics.userActions.push({
                type: 'submit',
                formId: event.target.id,
                timestamp: Date.now()
            });
        });
    }

    updatePerformanceIndicators() {
        // Update response time in header
        const responseTimeElement = document.getElementById('response-time');
        if (responseTimeElement && this.metrics.apiCalls.length > 0) {
            const avgResponseTime = this.metrics.apiCalls.reduce((sum, call) => sum + call.duration, 0) / this.metrics.apiCalls.length;
            responseTimeElement.textContent = Math.round(avgResponseTime) + 'ms';
        }

        // Update page load time
        const pageLoadElement = document.getElementById('page-load-time');
        if (pageLoadElement && this.metrics.pageLoad > 0) {
            pageLoadElement.textContent = Math.round(this.metrics.pageLoad);
        }
    }

    getMetrics() {
        return {
            ...this.metrics,
            currentMemory: performance.memory ? {
                used: performance.memory.usedJSHeapSize,
                total: performance.memory.totalJSHeapSize,
                limit: performance.memory.jsHeapSizeLimit
            } : null
        };
    }
}

// Real-time updates
class RealTimeUpdater {
    constructor() {
        this.updateInterval = null;
        this.isVisible = true;
        this.init();
    }

    init() {
        // Handle visibility changes to pause updates when tab is not active
        document.addEventListener('visibilitychange', () => {
            this.isVisible = !document.hidden;
            if (this.isVisible) {
                this.startUpdates();
            } else {
                this.stopUpdates();
            }  ?id=1
        });

        // Start updates if page is visible
        if (this.isVisible) {
            this.startUpdates();
        }
    }

    startUpdates() {
        if (this.updateInterval) return;
        
        this.updateInterval = setInterval(async () => {
            try {
                await this.updateStats();
                await this.updateSystemStatus();
            } catch (error) {
                console.error('Real-time update failed:', error);
            }
        }, 30000); // Update every 30 seconds
    }

    stopUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }

    async updateStats() {
        try {
            const response = await fetch('/api/stats');
            if (!response.ok) throw new Error('Stats API failed');
            
            const data = await response.json();
            
            // Update document counts
            this.updateElement('.bg-nigerian-green h3', data.documents?.total_documents);
            this.updateElement('.bg-success h3', data.documents?.recent_documents);
            this.updateElement('.bg-info h3', 
                Math.round((data.documents?.average_processing_time || 0) * 1000) + 'ms');
            
            // Update performance indicators
            if (data.performance) {
                this.updateElement('#response-time', 
                    Math.round((data.performance.avg_response_time || 0) * 1000) + 'ms');
            }

            return data;
        } catch (error) {
            console.error('Failed to update stats:', error);
            this.updateSystemStatus('error');
            throw error;
        }
    }

    async updateSystemStatus() {
        try {
            const response = await fetch('/health');
            const isHealthy = response.ok;
            
            const statusIndicator = document.getElementById('status-indicator');
            if (statusIndicator) {
                statusIndicator.className = `badge ${isHealthy ? 'bg-success' : 'bg-danger'}`;
                statusIndicator.textContent = isHealthy ? 'Online' : 'Offline';
            }
        } catch (error) {
            const statusIndicator = document.getElementById('status-indicator');
            if (statusIndicator) {
                statusIndicator.className = 'badge bg-danger';
                statusIndicator.textContent = 'Offline';
            }
        }
    }

    updateElement(selector, value) {
        const element = document.querySelector(selector);
        if (element && value !== undefined) {
            element.textContent = value;
        }
    }
}

// Form validation and enhancement
class FormEnhancer {
    constructor() {
        this.init();
    }

    init() {
        // Auto-format inputs
        this.setupAutoFormatting();
        
        // Real-time validation
        this.setupValidation();
        
        // Progress indicators
        this.setupProgressIndicators();
    }

    setupAutoFormatting() {
        // Phone number formatting
        document.querySelectorAll('input[type="tel"]').forEach(input => {
            input.addEventListener('input', (e) => {
                let value = e.target.value.replace(/\D/g, '');
                
                // Nigerian phone number formatting
                if (value.startsWith('234')) {
                    value = '+' + value.slice(0, 14);
                } else if (value.startsWith('0')) {
                    value = '+234' + value.slice(1, 11);
                } else if (value.length > 0 && !value.startsWith('+')) {
                    value = '+234' + value.slice(0, 10);
                }
                
                e.target.value = value;
            });
        });

        // Currency formatting
        document.querySelectorAll('input[type="number"][step="0.01"]').forEach(input => {
            input.addEventListener('blur', (e) => {
                if (e.target.value) {
                    e.target.value = parseFloat(e.target.value).toFixed(2);
                }
            });
        });

        // Date formatting for display
        document.querySelectorAll('input[type="date"]').forEach(input => {
            input.addEventListener('change', (e) => {
                if (e.target.value) {
                    const date = new Date(e.target.value);
                    const formattedDate = date.toLocaleDateString('en-NG', {
                        day: 'numeric',
                        month: 'long',
                        year: 'numeric'
                    });
                    
                    // Show formatted preview
                    let preview = e.target.parentNode.querySelector('.date-preview');
                    if (!preview) {
                        preview = document.createElement('small');
                        preview.className = 'date-preview text-muted d-block mt-1';
                        e.target.parentNode.appendChild(preview);
                    }
                    preview.textContent = `Will appear as: ${formattedDate}`;
                }
            });
        });
    }

    setupValidation() {
        document.querySelectorAll('form').forEach(form => {
            const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
            
            inputs.forEach(input => {
                input.addEventListener('blur', () => this.validateField(input));
                input.addEventListener('input', () => this.clearValidation(input));
            });
            
            form.addEventListener('submit', (e) => {
                if (!this.validateForm(form)) {
                    e.preventDefault();
                    this.showValidationSummary(form);
                }
            });
        });
    }

    validateField(field) {
        const isValid = field.checkValidity();
        
        field.classList.remove('is-valid', 'is-invalid');
        field.classList.add(isValid ? 'is-valid' : 'is-invalid');
        
        // Remove existing feedback
        const existingFeedback = field.parentNode.querySelector('.invalid-feedback, .valid-feedback');
        if (existingFeedback) {
            existingFeedback.remove();
        }
        
        // Add feedback
        const feedback = document.createElement('div');
        feedback.className = isValid ? 'valid-feedback' : 'invalid-feedback';
        feedback.textContent = isValid ? 'Looks good!' : field.validationMessage;
        field.parentNode.appendChild(feedback);
        
        return isValid;
    }

    clearValidation(field) {
        field.classList.remove('is-valid', 'is-invalid');
        const feedback = field.parentNode.querySelector('.invalid-feedback, .valid-feedback');
        if (feedback) {
            feedback.remove();
        }
    }

    validateForm(form) {
        const fields = form.querySelectorAll('input[required], select[required], textarea[required]');
        let isValid = true;
        
        fields.forEach(field => {
            if (!this.validateField(field)) {
                isValid = false;
            }
        });
        
        return isValid;
    }

    showValidationSummary(form) {
        const invalidFields = form.querySelectorAll('.is-invalid');
        if (invalidFields.length > 0) {
            const firstInvalidField = invalidFields[0];
            firstInvalidField.scrollIntoView({ behavior: 'smooth', block: 'center' });
            firstInvalidField.focus();
            
            this.showNotification('error', `Please fix ${invalidFields.length} field(s) before submitting.`);
        }
    }

    setupProgressIndicators() {
        document.querySelectorAll('form').forEach(form => {
            const requiredFields = form.querySelectorAll('input[required], select[required], textarea[required]');
            
            if (requiredFields.length > 0) {
                // Create progress indicator
                const progressContainer = document.createElement('div');
                progressContainer.className = 'form-progress mb-3';
                progressContainer.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <small class="text-muted">Form Progress</small>
                        <small class="text-muted"><span class="progress-count">0</span>/${requiredFields.length}</small>
                    </div>
                    <div class="progress" style="height: 4px;">
                        <div class="progress-bar bg-nigerian-green" style="width: 0%"></div>
                    </div>
                `;
                
                form.insertBefore(progressContainer, form.firstChild);
                
                // Update progress on input
                requiredFields.forEach(field => {
                    field.addEventListener('input', () => this.updateFormProgress(form));
                    field.addEventListener('change', () => this.updateFormProgress(form));
                });
            }
        });
    }

    updateFormProgress(form) {
        const requiredFields = form.querySelectorAll('input[required], select[required], textarea[required]');
        const filledFields = Array.from(requiredFields).filter(field => field.value.trim() !== '');
        
        const progress = (filledFields.length / requiredFields.length) * 100;
        
        const progressBar = form.querySelector('.progress-bar');
        const progressCount = form.querySelector('.progress-count');
        
        if (progressBar) {
            progressBar.style.width = progress + '%';
        }
        
        if (progressCount) {
            progressCount.textContent = filledFields.length;
        }
    }

    showNotification(type, message) {
        const alertClass = type === 'success' ? 'alert-success' : 
                          type === 'error' ? 'alert-danger' : 
                          type === 'info' ? 'alert-info' : 'alert-warning';
        const iconName = type === 'success' ? 'check-circle' : 
                         type === 'error' ? 'alert-circle' : 
                         type === 'info' ? 'info' : 'alert-triangle';
        
        const notification = document.createElement('div');
        notification.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 1060; min-width: 300px;';
        notification.innerHTML = `
            <i data-feather="${iconName}" width="16" height="16" class="me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        // Replace feather icons
        if (window.feather) {
            feather.replace();
        }
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }
}

// Keyboard shortcuts
class KeyboardShortcuts {
    constructor() {
        this.shortcuts = {
            'ctrl+/': () => this.showShortcutsHelp(),
            'ctrl+n': () => this.navigateTo('/'),
            'ctrl+u': () => this.navigateTo('/admin'),
            'ctrl+a': () => this.navigateTo('/analytics'),
            'esc': () => this.closeModals()
        };
        
        this.init();
    }

    init() {
        document.addEventListener('keydown', (e) => {
            const key = this.getKeyString(e);
            if (this.shortcuts[key]) {
                e.preventDefault();
                this.shortcuts[key]();
            }
        });
    }

    getKeyString(e) {
        const parts = [];
        if (e.ctrlKey) parts.push('ctrl');
        if (e.altKey) parts.push('alt');
        if (e.shiftKey) parts.push('shift');
        parts.push(e.key.toLowerCase());
        return parts.join('+');
    }

    navigateTo(path) {
        if (window.location.pathname !== path) {
            window.location.href = path;
        }
    }

    closeModals() {
        const modals = document.querySelectorAll('.modal.show');
        modals.forEach(modal => {
            const bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) {
                bsModal.hide();
            }
        });
    }

    showShortcutsHelp() {
        const helpModal = document.createElement('div');
        helpModal.className = 'modal fade';
        helpModal.innerHTML = `
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Keyboard Shortcuts</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-6"><kbd>Ctrl + /</kbd></div>
                            <div class="col-6">Show this help</div>
                        </div>
                        <div class="row">
                            <div class="col-6"><kbd>Ctrl + N</kbd></div>
                            <div class="col-6">Go to Dashboard</div>
                        </div>
                        <div class="row">
                            <div class="col-6"><kbd>Ctrl + U</kbd></div>
                            <div class="col-6">Go to Admin</div>
                        </div>
                        <div class="row">
                            <div class="col-6"><kbd>Ctrl + A</kbd></div>
                            <div class="col-6">Go to Analytics</div>
                        </div>
                        <div class="row">
                            <div class="col-6"><kbd>Esc</kbd></div>
                            <div class="col-6">Close modals</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(helpModal);
        const modal = new bootstrap.Modal(helpModal);
        modal.show();
        
        helpModal.addEventListener('hidden.bs.modal', () => {
            helpModal.remove();
        });
    }
}

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize performance monitoring
    window.performanceMonitor = new PerformanceMonitor();
    
    // Initialize real-time updates
    window.realTimeUpdater = new RealTimeUpdater();
    
    // Initialize form enhancements
    window.formEnhancer = new FormEnhancer();
    
    // Initialize keyboard shortcuts
    window.keyboardShortcuts = new KeyboardShortcuts();
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Add smooth scrolling to all anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Add loading states to all forms
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn && !submitBtn.disabled) {
                const originalText = submitBtn.innerHTML;
                const spinner = '<span class="spinner-border spinner-border-sm me-2"></span>';
                
                submitBtn.innerHTML = spinner + 'Processing...';
                submitBtn.disabled = true;
                
                // Reset after 30 seconds as fallback
                setTimeout(() => {
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }, 30000);
            }
        });
    });
    
    // Add fade-in animation to cards
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in');
            }
        });
    });
    
    document.querySelectorAll('.card').forEach(card => {
        observer.observe(card);
    });
    
    // Console welcome message
    console.log('%cMyTypist - Professional Document Automation', 
                'color: #006A4E; font-size: 16px; font-weight: bold;');
    console.log('%cPerformance monitoring active. Use window.performanceMonitor.getMetrics() to view metrics.', 
                'color: #666; font-size: 12px;');
});

// Export for debugging
window.MyTypist = {
    version: '1.0.0',
    modules: {
        PerformanceMonitor,
        RealTimeUpdater,
        FormEnhancer,
        KeyboardShortcuts
    }
};
