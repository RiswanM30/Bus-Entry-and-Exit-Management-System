from getpass import getpass
from werkzeug.security import generate_password_hash
from database import get_db_connection, initialize_database


def create_admin():
    initialize_database()

    username = input("Enter admin username: ").strip()
    password = getpass("Enter admin password: ")
    confirm = getpass("Confirm admin password: ")

    if not username or not password:
        print("Username and password are required.")
        return

    if len(password) < 5:
        print("Password must contain at least 5 characters.")
        return

    if password != confirm:
        print("Passwords do not match.")
        return

    try:
        with get_db_connection() as connection:
            connection.execute("""
                INSERT INTO users (username, password_hash, role)
                VALUES (?, ?, 'admin')
            """, (
                username,
                generate_password_hash(password)
            ))

        print("Admin account created successfully!")

    except Exception as error:
        print("Could not create admin account:", error)


if __name__ == "__main__":
    create_admin()
