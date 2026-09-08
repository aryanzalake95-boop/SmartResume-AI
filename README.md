# SmartResume AI

Flask-based Resume Analyzer & Career Advisor with persistent user accounts, password hashing, saved analysis history and admin management.

## Persistent login and production database
- User/admin sessions are permanent for 30 days.
- Keep the same SECRET_KEY after deployment so session cookies remain valid across restarts.
- Use PostgreSQL in production via DATABASE_URL; SQLite is only the local fallback.
- Passwords are stored as hashes.
- Resume analysis results are saved in the database.

## Run locally
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py

Open http://127.0.0.1:5000.

Default local admin: admin / admin123. Change it for production.

## Deploy
Set SECRET_KEY, DATABASE_URL, ADMIN_PASSWORD, SESSION_COOKIE_SECURE=1 and SESSION_COOKIE_SAMESITE=Lax on your hosting service.
Install with pip install -r requirements.txt and start with gunicorn app:app.

## Routes
Home, registration/login, dashboard, resume analyzer, career advisor, admin login/dashboard and logout are included.

## Note
The local SQLite database and uploaded resume files are intentionally ignored by Git. For cloud deployment, use persistent PostgreSQL and persistent object storage/disk if original uploaded resume files must survive redeployments.