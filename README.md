# College Bus Entry and Exit Management System

## Project Overview

The College Bus Entry and Exit Management System is a web-based application developed to manage student boarding and exit activities in college buses.

The system helps administrators manage buses, drivers, students and bus stops. Drivers can record student boarding and exit details, while students can view their assigned bus information and travel history.

## Problem Statement

Manual recording of student bus entry and exit details can be time-consuming and difficult to monitor. It may also lead to errors in maintaining travel records.

This project provides a digital solution to manage student boarding and exit information efficiently and maintain accurate travel records.

## Objectives

- To maintain student, driver and bus details.
- To manage bus routes and stops.
- To record student boarding and exit activities.
- To allow students to view their travel history.
- To generate daily travel reports.
- To improve the monitoring of college bus activities.

## Modules

### 1. Admin Module
- Admin login
- Student management
- Bus management
- Driver management
- Bus stop management
- Stop-wise student tracking
- Travel records
- Reports and CSV export

### 2. Driver Module
- Driver login
- View assigned bus details
- Record student boarding
- Record student exit
- View active boarding records

### 3. Student Module
- Student login
- View personal details
- View assigned bus information
- View bus route and stops
- View travel history

## Technologies Used

| Component | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python Flask |
| Database | SQLite |
| Code Editor | Visual Studio Code |
| Version Control | Git and GitHub |

## Database

The application uses SQLite to store student details, bus information, driver details, stops, user accounts, boarding entries and exit entries.

## How to Run the Project

1. Clone or download this repository.
2. Open the project folder in Visual Studio Code.
3. Install the required packages:

```bash
py -m pip install -r requirements.txt
```

4. Initialize the database:

```bash
py database.py
```

5. Create the admin account:

```bash
py create_admin.py
```

6. Start the Flask application:

```bash
py app.py
```

7. Open the application in your browser:

```text
http://127.0.0.1:5000
```

## Project Status

The project includes Admin, Driver and Student modules with bus management, boarding and exit recording, travel history and report generation.

## Repository

GitHub: https://github.com/RiswanM30/Bus-Entry-and-Exit-Management-System
