
import sqlite3
from pathlib import Path

# Database configuration
BASE_DIR = Path(__file__).resolve().parent
DATABASE_DIR = BASE_DIR / "database"
DATABASE_DIR.mkdir(exist_ok=True)

DB_PATH = DATABASE_DIR / "college_bus.db"


# Connect to database
def get_db_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


# Initialize all database tables
def initialize_database():

    with get_db_connection() as connection:

        # 1. BUS TABLE
        connection.execute("""
            CREATE TABLE IF NOT EXISTS buses (
                bus_id INTEGER PRIMARY KEY AUTOINCREMENT,
                bus_number TEXT NOT NULL UNIQUE,
                registration_number TEXT NOT NULL UNIQUE,
                capacity INTEGER NOT NULL CHECK(capacity > 0)
            )
        """)

        # 2. STUDENT TABLE
        connection.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id INTEGER PRIMARY KEY AUTOINCREMENT,
                roll_number TEXT NOT NULL UNIQUE,
                student_name TEXT NOT NULL,
                department TEXT NOT NULL,
                phone TEXT NOT NULL,
                bus_id INTEGER NOT NULL,
                FOREIGN KEY (bus_id)
                    REFERENCES buses(bus_id)
                    ON DELETE RESTRICT
            )
        """)

        # 3. DRIVER TABLE
        # UNIQUE bus_id means one driver per bus.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS drivers (
                driver_id INTEGER PRIMARY KEY AUTOINCREMENT,
                driver_name TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE,
                license_number TEXT NOT NULL UNIQUE,
                bus_id INTEGER NOT NULL UNIQUE,
                FOREIGN KEY (bus_id)
                    REFERENCES buses(bus_id)
                    ON DELETE RESTRICT
            )
        """)

        # 4. STOP TABLE
        connection.execute("""
            CREATE TABLE IF NOT EXISTS stops (
                stop_id INTEGER PRIMARY KEY AUTOINCREMENT,
                bus_id INTEGER NOT NULL,
                stop_name TEXT NOT NULL,
                stop_order INTEGER NOT NULL CHECK(stop_order > 0),

                FOREIGN KEY (bus_id)
                    REFERENCES buses(bus_id)
                    ON DELETE RESTRICT,

                UNIQUE(bus_id, stop_order),
                UNIQUE(bus_id, stop_name)
            )
        """)

        # 5. USER LOGIN TABLE
        # Admin: student_id and driver_id are NULL.
        # Student: student_id is set.
        # Driver: driver_id is set.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
                    CHECK(role IN ('admin', 'driver', 'student')),

                student_id INTEGER UNIQUE,
                driver_id INTEGER UNIQUE,

                FOREIGN KEY (student_id)
                    REFERENCES students(student_id)
                    ON DELETE RESTRICT,

                FOREIGN KEY (driver_id)
                    REFERENCES drivers(driver_id)
                    ON DELETE RESTRICT,

                CHECK (
                    (role = 'admin'
                        AND student_id IS NULL
                        AND driver_id IS NULL)
                    OR
                    (role = 'student'
                        AND student_id IS NOT NULL
                        AND driver_id IS NULL)
                    OR
                    (role = 'driver'
                        AND driver_id IS NOT NULL
                        AND student_id IS NULL)
                )
            )
        """)

        # 6. BOARDING ENTRY TABLE
        connection.execute("""
            CREATE TABLE IF NOT EXISTS boarding_entries (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                bus_id INTEGER NOT NULL,
                stop_id INTEGER NOT NULL,
                driver_id INTEGER NOT NULL,

                entry_time TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),

                FOREIGN KEY (student_id)
                    REFERENCES students(student_id)
                    ON DELETE RESTRICT,

                FOREIGN KEY (bus_id)
                    REFERENCES buses(bus_id)
                    ON DELETE RESTRICT,

                FOREIGN KEY (stop_id)
                    REFERENCES stops(stop_id)
                    ON DELETE RESTRICT,

                FOREIGN KEY (driver_id)
                    REFERENCES drivers(driver_id)
                    ON DELETE RESTRICT
            )
        """)

        # 7. EXIT ENTRY TABLE
        connection.execute("""
            CREATE TABLE IF NOT EXISTS exit_entries (
                exit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id INTEGER NOT NULL UNIQUE,
                exit_stop_id INTEGER NOT NULL,

                exit_time TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),

                FOREIGN KEY (entry_id)
                    REFERENCES boarding_entries(entry_id)
                    ON DELETE RESTRICT,

                FOREIGN KEY (exit_stop_id)
                    REFERENCES stops(stop_id)
                    ON DELETE RESTRICT
            )
        """)

        # INDEXES FOR FASTER SEARCHING
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_students_name
            ON students(student_name)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_students_bus
            ON students(bus_id)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_stops_bus
            ON stops(bus_id, stop_order)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_boarding_student
            ON boarding_entries(student_id)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_boarding_bus
            ON boarding_entries(bus_id, entry_time)
        """)

        print("Final database created successfully!")
        print("All seven tables are ready.")


if __name__ == "__main__":
    initialize_database()
