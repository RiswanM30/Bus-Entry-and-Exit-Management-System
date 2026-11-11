import os
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import csv
import io
from flask import make_response

from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    session,
    redirect,
    url_for
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from database import initialize_database, get_db_connection


# --------------------------------
# FLASK CONFIGURATION
# --------------------------------

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "development-key-change-before-deployment"
)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

initialize_database()


# --------------------------------
# ROLE PROTECTION
# --------------------------------

def role_required(*allowed_roles):

    def decorator(function):

        @wraps(function)
        def wrapper(*args, **kwargs):

            if "user_id" not in session:
                return redirect(url_for("home"))
            print("CURRENT LOGIN ROLE:", session.get("role"))
            print("ALLOWED ROLES:", allowed_roles)

            if session.get("role") not in allowed_roles:
                return jsonify({
                    "error": "You do not have permission to access this page."
                }), 403
            
            return function(*args, **kwargs)

        return wrapper

    return decorator


# --------------------------------
# LOGIN PAGE
# --------------------------------

@app.route("/")
def home():

    if "user_id" in session:

        role = session.get("role")

        if role == "admin":
            return redirect(url_for("admin_dashboard"))

        if role == "driver":
            return redirect(url_for("driver_dashboard"))

        if role == "student":
            return redirect(url_for("student_dashboard"))

    return render_template("login.html")


# --------------------------------
# LOGIN API
# --------------------------------

@app.route("/api/login", methods=["POST"])
def login():

    data = request.get_json(silent=True) or {}

    username = str(data.get("username", "")).strip()
    password = data.get("password", "")
    selected_role = data.get("role", "")

    if selected_role not in ("admin", "driver", "student"):
        return jsonify({
            "error": "Select a valid login role."
        }), 400

    if not username or not password:
        return jsonify({
            "error": "Enter username and password."
        }), 400

    with get_db_connection() as connection:

        user = connection.execute("""
            SELECT user_id, username, password_hash,
                   role, student_id, driver_id
            FROM users
            WHERE username = ?
        """, (username,)).fetchone()

    if (
        not user
        or user["role"] != selected_role
        or not check_password_hash(user["password_hash"], password)
    ):
        return jsonify({
            "error": "Invalid username, password or login role."
        }), 401

    session.clear()

    session["user_id"] = user["user_id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    session["student_id"] = user["student_id"]
    session["driver_id"] = user["driver_id"]

    return jsonify({
        "message": "Login successful.",
        "role": user["role"]
    })


# --------------------------------
# ADMIN DASHBOARD
# --------------------------------

@app.route("/admin/dashboard")
@role_required("admin")
def admin_dashboard():
    return render_template("admin_dashboard.html")


# --------------------------------
# DRIVER DASHBOARD
# --------------------------------

@app.route("/driver/dashboard")
@role_required("driver")
def driver_dashboard():
    return render_template("driver_dashboard.html")


# --------------------------------
# STUDENT DASHBOARD
# --------------------------------

@app.route("/student/dashboard")
@role_required("student")
def student_dashboard():
    return render_template("student_dashboard.html")


# --------------------------------
# LOGOUT
# --------------------------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))


# --------------------------------
# DATABASE TEST
# --------------------------------

@app.route("/api/test")
def test_database():

    with get_db_connection() as connection:

        tables = connection.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
        """).fetchall()

    return jsonify({
        "status": "success",
        "message": "Flask connected to the database.",
        "tables": [row["name"] for row in tables]
    })


# --------------------------------
# ADMIN DASHBOARD STATISTICS
# --------------------------------

@app.route("/api/admin/stats")
@role_required("admin")
def admin_stats():

    with get_db_connection() as connection:

        total_students = connection.execute("""
            SELECT COUNT(*) AS total FROM students
        """).fetchone()["total"]

        total_buses = connection.execute("""
            SELECT COUNT(*) AS total FROM buses
        """).fetchone()["total"]

        total_drivers = connection.execute("""
            SELECT COUNT(*) AS total FROM drivers
        """).fetchone()["total"]

        today_boardings = connection.execute("""
            SELECT COUNT(*) AS total
            FROM boarding_entries
            WHERE date(entry_time) = date('now', 'localtime')
        """).fetchone()["total"]

        today_exits = connection.execute("""
            SELECT COUNT(*) AS total
            FROM exit_entries
            WHERE date(exit_time) = date('now', 'localtime')
        """).fetchone()["total"]

        currently_on_bus = connection.execute("""
            SELECT COUNT(*) AS total
            FROM boarding_entries be
            LEFT JOIN exit_entries ee
                ON ee.entry_id = be.entry_id
            WHERE date(be.entry_time) = date('now', 'localtime')
              AND ee.exit_id IS NULL
        """).fetchone()["total"]

    return jsonify({
        "total_students": total_students,
        "total_buses": total_buses,
        "total_drivers": total_drivers,
        "today_boardings": today_boardings,
        "today_exits": today_exits,
        "currently_on_bus": currently_on_bus
    })


# ================================================
# BUS MANAGEMENT
# ================================================

@app.route("/admin/buses")
@role_required("admin")
def admin_buses():
    return render_template("buses.html")


@app.route("/api/admin/buses", methods=["GET", "POST"])
@role_required("admin")
def manage_buses():

    # VIEW BUSES

    if request.method == "GET":

        with get_db_connection() as connection:

            buses = connection.execute("""
                SELECT bus_id, bus_number,
                       registration_number, capacity
                FROM buses
                ORDER BY bus_number
            """).fetchall()

        return jsonify([dict(bus) for bus in buses])

    # ADD BUS

    data = request.get_json(silent=True) or {}

    bus_number = str(data.get("bus_number", "")).strip()
    registration_number = str(
        data.get("registration_number", "")
    ).strip()

    capacity = data.get("capacity")

    if not bus_number or not registration_number or capacity is None:
        return jsonify({
            "message": "Please fill all fields."
        }), 400

    try:
        capacity = int(capacity)

        if capacity <= 0:
            return jsonify({
                "message": "Capacity must be greater than zero."
            }), 400

    except (ValueError, TypeError):

        return jsonify({
            "message": "Enter a valid bus capacity."
        }), 400

    try:

        with get_db_connection() as connection:

            connection.execute("""
                INSERT INTO buses
                (bus_number, registration_number, capacity)
                VALUES (?, ?, ?)
            """, (
                bus_number,
                registration_number,
                capacity
            ))

        return jsonify({
            "message": "Bus added successfully!"
        }), 201

    except sqlite3.IntegrityError:

        return jsonify({
            "message": "Bus number or registration number already exists."
        }), 409


# ================================================
# DELETE BUS
# ================================================

@app.route("/api/admin/buses/<int:bus_id>", methods=["DELETE"])
@role_required("admin")
def delete_bus(bus_id):

    try:
        with get_db_connection() as connection:

            # Check whether bus exists
            bus = connection.execute("""
                SELECT bus_id, bus_number
                FROM buses
                WHERE bus_id = ?
            """, (bus_id,)).fetchone()

            if not bus:
                return jsonify({
                    "error": "Bus not found."
                }), 404

            # Check students assigned to this bus
            student_count = connection.execute("""
                SELECT COUNT(*) AS total
                FROM students
                WHERE bus_id = ?
            """, (bus_id,)).fetchone()["total"]

            # Check drivers assigned to this bus
            driver_count = connection.execute("""
                SELECT COUNT(*) AS total
                FROM drivers
                WHERE bus_id = ?
            """, (bus_id,)).fetchone()["total"]

            # Check stops registered for this bus
            stop_count = connection.execute("""
                SELECT COUNT(*) AS total
                FROM stops
                WHERE bus_id = ?
            """, (bus_id,)).fetchone()["total"]

            if student_count > 0 or driver_count > 0 or stop_count > 0:
                return jsonify({
                    "error": (
                        "Cannot delete this bus because it has "
                        "students, drivers, or stops linked to it. "
                        "Remove or reassign those records first."
                    )
                }), 409

            # Delete bus only when no linked records exist
            connection.execute("""
                DELETE FROM buses
                WHERE bus_id = ?
            """, (bus_id,))

        return jsonify({
            "message": (
                f"Bus '{bus['bus_number']}' deleted successfully."
            )
        }), 200

    except sqlite3.IntegrityError:
        return jsonify({
            "error": (
                "This bus is linked to existing records "
                "and cannot be deleted. Existing travel history "
                "has been protected."
            )
        }), 409

    except sqlite3.Error:
        app.logger.exception("Bus deletion failed")

        return jsonify({
            "error": "Database error while deleting bus."
        }), 500

# ================================================
# STOP MANAGEMENT
# ================================================

@app.route("/admin/stops")
@role_required("admin")
def admin_stops():
    return render_template("stops.html")


@app.route("/api/admin/stops", methods=["GET", "POST"])
@role_required("admin")
def manage_stops():

    # VIEW STOPS

    if request.method == "GET":

        bus_id = request.args.get("bus_id")

        if not bus_id:
            return jsonify({
                "message": "Please select a bus."
            }), 400

        with get_db_connection() as connection:

            stops = connection.execute("""
                SELECT stop_id, bus_id, stop_name, stop_order
                FROM stops
                WHERE bus_id = ?
                ORDER BY stop_order
            """, (bus_id,)).fetchall()

        return jsonify([dict(stop) for stop in stops])

    # ADD STOP

    data = request.get_json(silent=True) or {}

    bus_id = data.get("bus_id")
    stop_name = str(data.get("stop_name", "")).strip()
    stop_order = data.get("stop_order")

    if bus_id is None or not stop_name or stop_order is None:
        return jsonify({
            "message": "Please fill all fields."
        }), 400

    try:

        bus_id = int(bus_id)
        stop_order = int(stop_order)

        if bus_id <= 0 or stop_order <= 0:
            return jsonify({
                "message": "Select a valid bus and stop order."
            }), 400

    except (ValueError, TypeError):

        return jsonify({
            "message": "Enter valid bus and stop order values."
        }), 400

    try:

        with get_db_connection() as connection:

            bus = connection.execute(
                "SELECT bus_id FROM buses WHERE bus_id = ?",
                (bus_id,)
            ).fetchone()

            if not bus:
                return jsonify({
                    "message": "Selected bus does not exist."
                }), 400

            connection.execute("""
                INSERT INTO stops
                (bus_id, stop_name, stop_order)
                VALUES (?, ?, ?)
            """, (
                bus_id,
                stop_name,
                stop_order
            ))

        return jsonify({
            "message": "Stop added successfully!"
        }), 201

    except sqlite3.IntegrityError:

        return jsonify({
            "message": "This stop name or stop order already exists for this bus."
        }), 409

# ================================================
# DELETE BUS STOP
# ================================================

@app.route("/api/admin/stops/<int:stop_id>", methods=["DELETE"])
@role_required("admin")
def delete_stop(stop_id):

    try:
        with get_db_connection() as connection:

            # Check whether stop exists
            stop = connection.execute("""
                SELECT stop_id, stop_name
                FROM stops
                WHERE stop_id = ?
            """, (stop_id,)).fetchone()

            if not stop:
                return jsonify({
                    "error": "Stop not found."
                }), 404

            # Check boarding records using this stop
            boarding_history = connection.execute("""
                SELECT COUNT(*) AS total
                FROM boarding_entries
                WHERE stop_id = ?
            """, (stop_id,)).fetchone()["total"]

            # Check exit records using this stop
            exit_history = connection.execute("""
                SELECT COUNT(*) AS total
                FROM exit_entries
                WHERE exit_stop_id = ?
            """, (stop_id,)).fetchone()["total"]

            if boarding_history > 0 or exit_history > 0:
                return jsonify({
                    "error": (
                        "Cannot delete this stop because "
                        "it is linked to existing boarding or "
                        "exit records. Travel history must be preserved."
                    )
                }), 409

            # Delete stop
            connection.execute("""
                DELETE FROM stops
                WHERE stop_id = ?
            """, (stop_id,))

        return jsonify({
            "message": (
                f"Stop '{stop['stop_name']}' deleted successfully."
            )
        }), 200

    except sqlite3.IntegrityError:
        return jsonify({
            "error": (
                "This stop is linked to another record "
                "and cannot be deleted."
            )
        }), 409

    except sqlite3.Error:
        app.logger.exception("Stop deletion failed")

        return jsonify({
            "error": "Database error while deleting stop."
        }), 500


# ================================================
# STUDENT MANAGEMENT
# ================================================

@app.route("/admin/students")
@role_required("admin")
def admin_students():
    return render_template("students.html")


@app.route("/api/admin/students", methods=["GET", "POST"])
@role_required("admin")
def manage_students():

    # VIEW STUDENTS
    

    if request.method == "GET":

        with get_db_connection() as connection:

            students = connection.execute("""
                SELECT s.student_id, s.roll_number,
                       s.student_name, s.department,
                       s.phone, s.bus_id, b.bus_number
                FROM students s
                LEFT JOIN buses b ON s.bus_id = b.bus_id
                ORDER BY s.student_name
            """).fetchall()

        return jsonify([dict(student) for student in students])

    # ADD STUDENT

    data = request.get_json(silent=True) or {}

    roll_number = str(data.get("roll_number", "")).strip()
    student_name = str(data.get("student_name", "")).strip()
    department = str(data.get("department", "")).strip()
    phone = str(data.get("phone", "")).strip()
    bus_id = data.get("bus_id")
    username = str(data.get("username", "")).strip()
    password = data.get("password", "")

    if not all([
        roll_number,
        student_name,
        department,
        phone,
        bus_id,
        username,
        password
    ]):
        return jsonify({
            "message": "Please fill all fields."
        }), 400

    if len(password) < 5:
        return jsonify({
            "message": "Password must contain at least 5 characters."
        }), 400

    try:
        bus_id = int(bus_id)
    except (ValueError, TypeError):
        return jsonify({
            "message": "Invalid bus selection."
        }), 400

    try:

        with get_db_connection() as connection:

            bus = connection.execute(
                "SELECT bus_id FROM buses WHERE bus_id = ?",
                (bus_id,)
            ).fetchone()

            if not bus:
                return jsonify({
                    "message": "Selected bus does not exist."
                }), 400

            cursor = connection.execute("""
                INSERT INTO students
                (roll_number, student_name, department, phone, bus_id)
                VALUES (?, ?, ?, ?, ?)
            """, (
                roll_number,
                student_name,
                department,
                phone,
                bus_id
            ))

            student_id = cursor.lastrowid

            connection.execute("""
                INSERT INTO users
                (username, password_hash, role, student_id)
                VALUES (?, ?, 'student', ?)
            """, (
                username,
                generate_password_hash(password),
                student_id
            ))

        return jsonify({
            "message": "Student account created successfully!"
        }), 201

    except sqlite3.IntegrityError:

        return jsonify({
            "message": "Roll number or username already exists."
        }), 409
    except sqlite3.IntegrityError:

        return jsonify({
            "message": "Roll number or username already exists."
        }), 409
    
# ================================================
# DELETE STUDENT
# ================================================

@app.route("/api/admin/students/<int:student_id>", methods=["DELETE"])
@role_required("admin")
def delete_student(student_id):

    try:
        with get_db_connection() as connection:

            # Check whether student exists
            student = connection.execute("""
                SELECT student_id, student_name
                FROM students
                WHERE student_id = ?
            """, (student_id,)).fetchone()

            if not student:
                return jsonify({
                    "error": "Student not found."
                }), 404

            # Protect existing boarding and exit history
            history = connection.execute("""
                SELECT COUNT(*) AS total
                FROM boarding_entries
                WHERE student_id = ?
            """, (student_id,)).fetchone()["total"]

            if history > 0:
                return jsonify({
                    "error": (
                        "Cannot delete this student because "
                        "travel records already exist. "
                        "Existing travel history must be preserved."
                    )
                }), 409

            # Delete linked student login account first
            connection.execute("""
                DELETE FROM users
                WHERE student_id = ?
                  AND role = 'student'
            """, (student_id,))

            # Delete student record
            connection.execute("""
                DELETE FROM students
                WHERE student_id = ?
            """, (student_id,))

        return jsonify({
            "message": (
                f"Student {student['student_name']} "
                "deleted successfully."
            )
        }), 200

    except sqlite3.IntegrityError:
        return jsonify({
            "error": (
                "Student cannot be deleted because "
                "related records exist."
            )
        }), 409

    except sqlite3.Error:
        app.logger.exception("Student deletion failed")

        return jsonify({
            "error": "Database error while deleting student."
        }), 500


# ================================================
# DRIVER MANAGEMENT
# ================================================

@app.route("/admin/drivers")
@role_required("admin")
def admin_drivers():
    return render_template("drivers.html")


@app.route("/api/admin/drivers", methods=["GET", "POST"])
@role_required("admin")
def manage_drivers():

    # VIEW DRIVERS

    if request.method == "GET":

        with get_db_connection() as connection:

            drivers = connection.execute("""
                SELECT d.driver_id, d.driver_name,
                       d.phone, d.license_number,
                       d.bus_id, b.bus_number
                FROM drivers d
                JOIN buses b ON d.bus_id = b.bus_id
                ORDER BY d.driver_name
            """).fetchall()

        return jsonify([dict(driver) for driver in drivers])

    # ADD DRIVER

    data = request.get_json(silent=True) or {}

    driver_name = str(data.get("driver_name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    license_number = str(data.get("license_number", "")).strip()
    bus_id = data.get("bus_id")
    username = str(data.get("username", "")).strip()
    password = data.get("password", "")

    if not all([
        driver_name,
        phone,
        license_number,
        bus_id,
        username,
        password
    ]):
        return jsonify({
            "message": "Please fill all fields."
        }), 400

    if len(password) < 5:
        return jsonify({
            "message": "Password must contain at least 5 characters."
        }), 400

    try:
        bus_id = int(bus_id)
    except (ValueError, TypeError):
        return jsonify({
            "message": "Invalid bus selection."
        }), 400

    try:

        with get_db_connection() as connection:

            bus = connection.execute(
                "SELECT bus_id FROM buses WHERE bus_id = ?",
                (bus_id,)
            ).fetchone()

            if not bus:
                return jsonify({
                    "message": "Selected bus does not exist."
                }), 400

            cursor = connection.execute("""
                INSERT INTO drivers
                (driver_name, phone, license_number, bus_id)
                VALUES (?, ?, ?, ?)
            """, (
                driver_name,
                phone,
                license_number,
                bus_id
            ))

            driver_id = cursor.lastrowid

            connection.execute("""
                INSERT INTO users
                (username, password_hash, role, driver_id)
                VALUES (?, ?, 'driver', ?)
            """, (
                username,
                generate_password_hash(password),
                driver_id
            ))

        return jsonify({
            "message": "Driver account created successfully!"
        }), 201

    except sqlite3.IntegrityError:

        return jsonify({
            "message": "Username, phone, license number or bus assignment already exists."
        }), 409

# ================================================
# DELETE DRIVER
# ================================================

@app.route("/api/admin/drivers/<int:driver_id>", methods=["DELETE"])
@role_required("admin")
def delete_driver(driver_id):

    try:
        with get_db_connection() as connection:

            # Check driver exists
            driver = connection.execute("""
                SELECT driver_id, driver_name
                FROM drivers
                WHERE driver_id = ?
            """, (driver_id,)).fetchone()

            if not driver:
                return jsonify({
                    "error": "Driver not found."
                }), 404

            # Check existing travel records
            history = connection.execute("""
                SELECT COUNT(*) AS total
                FROM boarding_entries
                WHERE driver_id = ?
            """, (driver_id,)).fetchone()["total"]

            if history > 0:
                return jsonify({
                    "error": (
                        "Cannot delete this driver because "
                        "travel records are linked to this driver. "
                        "Existing records must be preserved."
                    )
                }), 409

            # Delete linked driver login account
            connection.execute("""
                DELETE FROM users
                WHERE driver_id = ?
                  AND role = 'driver'
            """, (driver_id,))

            # Delete driver
            connection.execute("""
                DELETE FROM drivers
                WHERE driver_id = ?
            """, (driver_id,))

        return jsonify({
            "message": (
                f"Driver {driver['driver_name']} "
                "deleted successfully."
            )
        }), 200

    except sqlite3.IntegrityError:
        return jsonify({
            "error": (
                "Driver cannot be deleted because "
                "related records exist."
            )
        }), 409

    except sqlite3.Error:
        app.logger.exception("Driver deletion failed")

        return jsonify({
            "error": "Database error while deleting driver."
        }), 500


# ================================================
# DRIVER DASHBOARD DATA
# ================================================

@app.route("/api/driver/dashboard")
@role_required("driver")
def driver_dashboard_data():

    driver_id = session.get("driver_id")

    with get_db_connection() as connection:

        driver = connection.execute("""
            SELECT d.driver_id, d.driver_name,
                   d.bus_id, b.bus_number
            FROM drivers d
            JOIN buses b ON b.bus_id = d.bus_id
            WHERE d.driver_id = ?
        """, (driver_id,)).fetchone()

        if not driver:
            return jsonify({
                "message": "Driver account or bus assignment not found."
            }), 404

        students = connection.execute("""
            SELECT student_id, roll_number, student_name, department
            FROM students
            WHERE bus_id = ?
            ORDER BY student_name
        """, (driver["bus_id"],)).fetchall()

        stops = connection.execute("""
            SELECT stop_id, stop_name, stop_order
            FROM stops
            WHERE bus_id = ?
            ORDER BY stop_order
        """, (driver["bus_id"],)).fetchall()

    return jsonify({
        "driver": dict(driver),
        "students": [dict(student) for student in students],
        "stops": [dict(stop) for stop in stops]
    })


# ================================================
# STUDENT BOARDING ENTRY
# ================================================

@app.route("/api/driver/boarding", methods=["POST"])
@role_required("driver")
def record_boarding():

    driver_id = session.get("driver_id")

    data = request.get_json(silent=True) or {}

    student_id = data.get("student_id")
    stop_id = data.get("stop_id")

    if not student_id or not stop_id:
        return jsonify({
            "message": "Please select a student and boarding stop."
        }), 400

    try:
        student_id = int(student_id)
        stop_id = int(stop_id)
    except (ValueError, TypeError):
        return jsonify({
            "message": "Invalid student or stop selection."
        }), 400

    with get_db_connection() as connection:

        driver = connection.execute("""
            SELECT driver_id, bus_id
            FROM drivers
            WHERE driver_id = ?
        """, (driver_id,)).fetchone()

        if not driver:
            return jsonify({
                "message": "Driver account not found."
            }), 404

        bus_id = driver["bus_id"]

        student = connection.execute("""
            SELECT student_id
            FROM students
            WHERE student_id = ? AND bus_id = ?
        """, (student_id, bus_id)).fetchone()

        if not student:
            return jsonify({
                "message": "This student is not assigned to your bus."
            }), 403

        stop = connection.execute("""
            SELECT stop_id
            FROM stops
            WHERE stop_id = ? AND bus_id = ?
        """, (stop_id, bus_id)).fetchone()

        if not stop:
            return jsonify({
                "message": "This stop does not belong to your bus."
            }), 400

        active_entry = connection.execute("""
            SELECT be.entry_id
            FROM boarding_entries be
            LEFT JOIN exit_entries ee
                ON ee.entry_id = be.entry_id
            WHERE be.student_id = ?
              AND ee.exit_id IS NULL
            LIMIT 1
        """, (student_id,)).fetchone()

        if active_entry:
            return jsonify({
                "message": "This student already has an active boarding entry. Record the exit first."
            }), 409

        connection.execute("""
            INSERT INTO boarding_entries
            (student_id, bus_id, stop_id, driver_id)
            VALUES (?, ?, ?, ?)
        """, (student_id, bus_id, stop_id, driver_id))

    return jsonify({
        "message": "Student boarding recorded successfully!"
    }), 201


# ================================================
# DRIVER EXIT PAGE
# ================================================

@app.route("/driver/exit")
@role_required("driver")
def driver_exit():
    return render_template("exit.html")


# ================================================
# ACTIVE BOARDING RECORDS
# ================================================

@app.route("/api/driver/active-boardings")
@role_required("driver")
def active_boardings():

    driver_id = session.get("driver_id")

    with get_db_connection() as connection:

        driver = connection.execute("""
            SELECT bus_id
            FROM drivers
            WHERE driver_id = ?
        """, (driver_id,)).fetchone()

        if not driver:
            return jsonify({"message": "Driver not found."}), 404

        records = connection.execute("""
            SELECT
                be.entry_id,
                s.student_id,
                s.roll_number,
                s.student_name,
                boarding_stop.stop_name AS boarding_stop,
                be.entry_time
            FROM boarding_entries be
            JOIN students s
                ON s.student_id = be.student_id
            JOIN stops boarding_stop
                ON boarding_stop.stop_id = be.stop_id
            LEFT JOIN exit_entries ee
                ON ee.entry_id = be.entry_id
            WHERE be.bus_id = ?
              AND ee.exit_id IS NULL
            ORDER BY be.entry_time
        """, (driver["bus_id"],)).fetchall()

    return jsonify([dict(record) for record in records])


# ================================================
# RECORD STUDENT EXIT
# ================================================

@app.route("/api/driver/exit", methods=["POST"])
@role_required("driver")
def record_exit():

    driver_id = session.get("driver_id")

    data = request.get_json(silent=True) or {}

    entry_id = data.get("entry_id")
    exit_stop_id = data.get("exit_stop_id")

    if not entry_id or not exit_stop_id:
        return jsonify({
            "message": "Please select a student and exit stop."
        }), 400

    try:
        entry_id = int(entry_id)
        exit_stop_id = int(exit_stop_id)
    except (ValueError, TypeError):
        return jsonify({
            "message": "Invalid boarding or stop selection."
        }), 400

    try:
        with get_db_connection() as connection:

            driver = connection.execute("""
                SELECT bus_id
                FROM drivers
                WHERE driver_id = ?
            """, (driver_id,)).fetchone()

            if not driver:
                return jsonify({
                    "message": "Driver account not found."
                }), 404

            bus_id = driver["bus_id"]

            boarding = connection.execute("""
                SELECT be.entry_id
                FROM boarding_entries be
                LEFT JOIN exit_entries ee
                    ON ee.entry_id = be.entry_id
                WHERE be.entry_id = ?
                  AND be.bus_id = ?
                  AND be.driver_id = ?
                  AND ee.exit_id IS NULL
            """, (entry_id, bus_id, driver_id)).fetchone()

            if not boarding:
                return jsonify({
                    "message": "Active boarding record not found."
                }), 404

            stop = connection.execute("""
                SELECT stop_id
                FROM stops
                WHERE stop_id = ? AND bus_id = ?
            """, (exit_stop_id, bus_id)).fetchone()

            if not stop:
                return jsonify({
                    "message": "Selected exit stop does not belong to your bus."
                }), 400

            connection.execute("""
                INSERT INTO exit_entries
                (entry_id, exit_stop_id)
                VALUES (?, ?)
            """, (entry_id, exit_stop_id))

        return jsonify({
            "message": "Student exit recorded successfully!"
        }), 201

    except sqlite3.IntegrityError:
        return jsonify({
            "message": "Exit has already been recorded for this boarding."
        }), 409


# ================================================
# STUDENT DASHBOARD DATA
# ================================================

@app.route("/api/student/dashboard")
@role_required("student")
def student_dashboard_data():

    student_id = session.get("student_id")

    with get_db_connection() as connection:

        student = connection.execute("""
            SELECT
                s.student_id,
                s.roll_number,
                s.student_name,
                s.department,
                s.phone,
                s.bus_id,
                b.bus_number,
                b.registration_number
            FROM students s
            LEFT JOIN buses b ON b.bus_id = s.bus_id
            WHERE s.student_id = ?
        """, (student_id,)).fetchone()

        if not student:
            return jsonify({
                "message": "Student account not found."
            }), 404

        stops = connection.execute("""
            SELECT stop_name, stop_order
            FROM stops
            WHERE bus_id = ?
            ORDER BY stop_order
        """, (student["bus_id"],)).fetchall()

        history = connection.execute("""
            SELECT
                be.entry_id,
                be.entry_time,
                boarding_stop.stop_name AS boarding_stop,
                ee.exit_time,
                exit_stop.stop_name AS exit_stop
            FROM boarding_entries be
            JOIN stops boarding_stop
                ON boarding_stop.stop_id = be.stop_id
            LEFT JOIN exit_entries ee
                ON ee.entry_id = be.entry_id
            LEFT JOIN stops exit_stop
                ON exit_stop.stop_id = ee.exit_stop_id
            WHERE be.student_id = ?
            ORDER BY be.entry_time DESC
        """, (student_id,)).fetchall()

    return jsonify({
        "student": dict(student),
        "stops": [dict(stop) for stop in stops],
        "history": [dict(record) for record in history]
    })

@app.route("/admin/travel-records")
@role_required("admin")
def admin_travel_records():
    print("ADMIN TRAVEL RECORDS PAGE ROUTE REACHED")
    return render_template("travel_records.html")


@app.route("/api/admin/travel-records")
@role_required("admin")
def get_admin_travel_records():
    connection = get_db_connection()

    bus_id = request.args.get("bus_id", "").strip()
    search = request.args.get("search", "").strip()
    travel_date = request.args.get("date", "").strip()

    query = """
        SELECT
            be.entry_id,
            s.roll_number,
            s.student_name,
            b.bus_number,
            d.driver_name,
            boarding_stop.stop_name AS boarding_stop,
            be.entry_time,
            exit_stop.stop_name AS exit_stop,
            ee.exit_time,
            CASE
                WHEN ee.exit_id IS NULL THEN 'On Bus'
                ELSE 'Completed'
            END AS travel_status
        FROM boarding_entries be
        JOIN students s
            ON be.student_id = s.student_id
        JOIN buses b
            ON be.bus_id = b.bus_id
        JOIN drivers d
            ON be.driver_id = d.driver_id
        JOIN stops boarding_stop
            ON be.stop_id = boarding_stop.stop_id
        LEFT JOIN exit_entries ee
            ON be.entry_id = ee.entry_id
        LEFT JOIN stops exit_stop
            ON ee.exit_stop_id = exit_stop.stop_id
        WHERE 1 = 1
    """

    params = []

    if bus_id:
        query += " AND be.bus_id = ?"
        params.append(bus_id)

    if search:
        query += """
            AND (
                s.student_name LIKE ?
                OR s.roll_number LIKE ?
            )
        """
        params.extend([f"%{search}%", f"%{search}%"])

    if travel_date:
        query += " AND date(be.entry_time) = date(?)"
        params.append(travel_date)

    query += " ORDER BY be.entry_time DESC"

    records = connection.execute(query, params).fetchall()

    buses = connection.execute("""
        SELECT bus_id, bus_number
        FROM buses
        ORDER BY bus_number
    """).fetchall()

    connection.close()

    return jsonify({
        "records": [dict(record) for record in records],
        "buses": [dict(bus) for bus in buses]
    })

@app.route("/admin/stop-wise")
@role_required("admin")
def admin_stop_wise():
    return render_template("stop_wise.html")


@app.route("/api/admin/stop-wise")
@role_required("admin")
def get_stop_wise_students():

    bus_id = request.args.get("bus_id", "").strip()
    stop_id = request.args.get("stop_id", "").strip()

    with get_db_connection() as connection:

        buses = connection.execute("""
            SELECT bus_id, bus_number
            FROM buses
            ORDER BY bus_number
        """).fetchall()

        if not bus_id:
            return jsonify({
                "buses": [dict(bus) for bus in buses],
                "stops": [],
                "students": []
            })

        stops = connection.execute("""
            SELECT stop_id, stop_name, stop_order
            FROM stops
            WHERE bus_id = ?
            ORDER BY stop_order
        """, (bus_id,)).fetchall()

        query = """
            SELECT
                s.student_id,
                s.roll_number,
                s.student_name,
                boarding_stop.stop_name AS boarding_stop,
                be.entry_time,
                CASE
                    WHEN be.entry_id IS NULL THEN 'Not Boarded'
                    WHEN ee.exit_id IS NULL THEN 'Boarded'
                    ELSE 'Exited'
                END AS boarding_status
            FROM students s

            LEFT JOIN boarding_entries be
                ON be.student_id = s.student_id
                AND be.bus_id = s.bus_id
                AND date(be.entry_time) = date('now', 'localtime')

            LEFT JOIN exit_entries ee
                ON ee.entry_id = be.entry_id

            LEFT JOIN stops boarding_stop
                ON boarding_stop.stop_id = be.stop_id

            WHERE s.bus_id = ?
        """

        params = [bus_id]

        if stop_id:
            query += """
                AND s.student_id IN (
                    SELECT student_id
                    FROM boarding_entries
                    WHERE stop_id = ?
                    AND date(entry_time) = date('now', 'localtime')
                )
            """
            params.append(stop_id)

        query += " ORDER BY s.student_name"

        students = connection.execute(
            query, params
        ).fetchall()

    return jsonify({
        "buses": [dict(bus) for bus in buses],
        "stops": [dict(stop) for stop in stops],
        "students": [dict(student) for student in students]
    })

@app.route("/admin/reports")
@role_required("admin")
def admin_reports():
    return render_template("reports.html")


@app.route("/api/admin/reports")
@role_required("admin")
def get_admin_reports():

    report_date = request.args.get("date", "").strip()

    if not report_date:
        report_date = __import__("datetime").date.today().isoformat()

    with get_db_connection() as connection:

        total_boardings = connection.execute("""
            SELECT COUNT(*) AS total
            FROM boarding_entries
            WHERE date(entry_time) = date(?)
        """, (report_date,)).fetchone()["total"]

        total_exits = connection.execute("""
            SELECT COUNT(*) AS total
            FROM exit_entries
            WHERE date(exit_time) = date(?)
        """, (report_date,)).fetchone()["total"]

        currently_on_bus = connection.execute("""
            SELECT COUNT(*) AS total
            FROM boarding_entries be
            LEFT JOIN exit_entries ee
                ON ee.entry_id = be.entry_id
            WHERE date(be.entry_time) = date(?)
              AND ee.exit_id IS NULL
        """, (report_date,)).fetchone()["total"]

        bus_reports = connection.execute("""
            SELECT
                b.bus_number,
                COUNT(be.entry_id) AS total_boardings,
                COUNT(ee.exit_id) AS total_exits,
                SUM(
                    CASE
                        WHEN be.entry_id IS NOT NULL
                         AND ee.exit_id IS NULL THEN 1
                        ELSE 0
                    END
                ) AS currently_on_bus
            FROM buses b
            LEFT JOIN boarding_entries be
                ON be.bus_id = b.bus_id
                AND date(be.entry_time) = date(?)
            LEFT JOIN exit_entries ee
                ON ee.entry_id = be.entry_id
            GROUP BY b.bus_id, b.bus_number
            ORDER BY b.bus_number
        """, (report_date,)).fetchall()

    return jsonify({
        "date": report_date,
        "total_boardings": total_boardings,
        "total_exits": total_exits,
        "currently_on_bus": currently_on_bus,
        "bus_reports": [dict(row) for row in bus_reports]
    })


@app.route("/admin/reports/export")
@role_required("admin")
def export_admin_report():

    report_date = request.args.get("date", "").strip()

    if not report_date:
        report_date = __import__("datetime").date.today().isoformat()

    with get_db_connection() as connection:

        records = connection.execute("""
            SELECT
                s.roll_number,
                s.student_name,
                b.bus_number,
                d.driver_name,
                boarding_stop.stop_name AS boarding_stop,
                be.entry_time,
                exit_stop.stop_name AS exit_stop,
                ee.exit_time,
                CASE
                    WHEN ee.exit_id IS NULL THEN 'On Bus'
                    ELSE 'Completed'
                END AS status
            FROM boarding_entries be
            JOIN students s
                ON s.student_id = be.student_id
            JOIN buses b
                ON b.bus_id = be.bus_id
            JOIN drivers d
                ON d.driver_id = be.driver_id
            JOIN stops boarding_stop
                ON boarding_stop.stop_id = be.stop_id
            LEFT JOIN exit_entries ee
                ON ee.entry_id = be.entry_id
            LEFT JOIN stops exit_stop
                ON exit_stop.stop_id = ee.exit_stop_id
            WHERE date(be.entry_time) = date(?)
            ORDER BY be.entry_time
        """, (report_date,)).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Roll Number",
        "Student Name",
        "Bus Number",
        "Driver",
        "Boarding Stop",
        "Boarding Time",
        "Exit Stop",
        "Exit Time",
        "Status"
    ])

    for record in records:
        writer.writerow([
            record["roll_number"],
            record["student_name"],
            record["bus_number"],
            record["driver_name"],
            record["boarding_stop"],
            record["entry_time"],
            record["exit_stop"] or "-",
            record["exit_time"] or "-",
            record["status"]
        ])

    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = (
        f"attachment; filename=bus_report_{report_date}.csv"
    )

    return response

# --------------------------------
# RUN APPLICATION
# --------------------------------

if __name__ == "__main__":
    app.run(debug=True)
