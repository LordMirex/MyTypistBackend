"""
Database configuration and session management
"""

import os
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config import settings

# Create database engine with optimizations
if "sqlite" in settings.DATABASE_URL.lower():
    # SQLite optimizations
    engine = create_engine(
        settings.DATABASE_URL,
        poolclass=StaticPool,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={
            "check_same_thread": False,
            "timeout": 20,
        },
        echo=settings.DEBUG
    )
    
    # Enable WAL mode for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Set SQLite optimizations"""
        cursor = dbapi_connection.cursor()
        # Enable WAL mode for better concurrency
        cursor.execute("PRAGMA journal_mode=WAL")
        # Increase cache size
        cursor.execute("PRAGMA cache_size=10000")
        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys=ON")
        # Optimize synchronous mode
        cursor.execute("PRAGMA synchronous=NORMAL")
        # Set busy timeout
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()
else:
    # PostgreSQL or other database
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=20,
        max_overflow=0,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=settings.DEBUG
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DatabaseManager:
    """Database management utilities"""
    
    @staticmethod
    def create_all_tables():
        """Create all database tables"""
        Base.metadata.create_all(bind=engine)
    
    @staticmethod
    def drop_all_tables():
        """Drop all database tables (use with caution)"""
        Base.metadata.drop_all(bind=engine)
    
    @staticmethod
    def get_session():
        """Get a new database session"""
        return SessionLocal()
    
    @staticmethod
    def close_session(session):
        """Close database session"""
        session.close()
