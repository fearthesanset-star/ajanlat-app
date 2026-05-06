import os
import sqlite3

DB_NAME = "app.db"
DATABASE_URL = os.getenv("DATABASE_URL")


def is_postgres():
    return DATABASE_URL is not None and DATABASE_URL.strip() != ""


def get_connection():
    if is_postgres():
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    if is_postgres():
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE,
                password TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                unit TEXT NOT NULL,
                price REAL NOT NULL,
                description TEXT NOT NULL,
                user_id INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                valid_until TEXT,
                user_id INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_items (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                quantity REAL NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                user_id INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS template_items (
                id SERIAL PRIMARY KEY,
                template_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                default_quantity REAL NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                id SERIAL PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                accepted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE,
                company_name TEXT DEFAULT '',
                company_email TEXT DEFAULT '',
                company_phone TEXT DEFAULT ''
            )
        """)

    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                password TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                unit TEXT NOT NULL,
                price REAL NOT NULL,
                description TEXT NOT NULL,
                user_id INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                valid_until TEXT,
                user_id INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                quantity REAL NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (item_id) REFERENCES items(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                user_id INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS template_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                default_quantity REAL NOT NULL,
                FOREIGN KEY (template_id) REFERENCES templates(id),
                FOREIGN KEY (item_id) REFERENCES items(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                accepted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                company_name TEXT DEFAULT '',
                company_email TEXT DEFAULT '',
                company_phone TEXT DEFAULT ''
            )
        """)

        migrations = [
            "ALTER TABLE items ADD COLUMN user_id INTEGER",
            "ALTER TABLE projects ADD COLUMN user_id INTEGER",
            "ALTER TABLE projects ADD COLUMN valid_until TEXT",
            "ALTER TABLE templates ADD COLUMN user_id INTEGER",
            "ALTER TABLE subscribers ADD COLUMN accepted INTEGER DEFAULT 0",
        ]

        for migration in migrations:
            try:
                cursor.execute(migration)
            except sqlite3.OperationalError:
                pass

    conn.commit()
    conn.close()

