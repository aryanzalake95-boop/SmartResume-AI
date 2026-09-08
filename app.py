from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import IntegrityError
from utils.resume_parser import extract_resume_text
from utils.analyzer import analyze_resume
from utils.career_advisor import career_recommendations
import os, json, uuid
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-this-secret-key")
app.config.update(
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    SESSION_PERMANENT=True,
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE=os.environ.get("SESSION_COOKIE_SAMESITE", "Lax"),
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
)

database_url = os.environ.get("DATABASE_URL", "").strip()
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

if not database_url:
    database_url = "sqlite:///" + os.path.join(BASE_DIR, "smartresume.db")

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
)
DbSession = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()

def db():
    return DbSession()

def init_db():
    with engine.begin() as con:
        if database_url.startswith("sqlite"):
            con.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            con.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                score INTEGER NOT NULL,
                result_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )""")
        else:
            con.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            con.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS analyses (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                filename TEXT NOT NULL,
                score INTEGER NOT NULL,
                result_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
    with engine.begin() as con:
        row = con.execute(text("SELECT id FROM users WHERE username=:u"), {"u": "admin"}).first()
        if not row:
            con.execute(text(
                "INSERT INTO users(name,username,password,role) VALUES(:n,:u,:p,'admin')"
            ), {"n": "Administrator", "u": "admin",
                "p": generate_password_hash(os.environ.get("ADMIN_PASSWORD", "admin123"))})

def get_user(user_id, role=None):
    with engine.connect() as con:
        q = "SELECT * FROM users WHERE id=:id"
        params = {"id": user_id}
        if role:
            q += " AND role=:role"
            params["role"] = role
        return con.execute(text(q), params).mappings().first()

def current_user():
    if "admin_id" in session:
        u = get_user(session["admin_id"], "admin")
        if u:
            return u
        session.pop("admin_id", None)
    if "user_id" in session:
        u = get_user(session["user_id"], "user")
        if u:
            return u
        session.pop("user_id", None)
    return None

@app.context_processor
def inject_user():
    return {"current_user": current_user()}

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not username or len(password) < 6:
            flash("Enter all fields. Password must be at least 6 characters.", "danger")
            return redirect(url_for("register"))
        try:
            with engine.begin() as con:
                con.execute(text(
                    "INSERT INTO users(name,username,password,role) VALUES(:n,:u,:p,'user')"
                ), {"n": name, "u": username, "p": generate_password_hash(password)})
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except IntegrityError:
            flash("Username already exists.", "danger")
            return redirect(url_for("register"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        with engine.connect() as con:
            u = con.execute(text("SELECT * FROM users WHERE username=:u"), {"u": username}).mappings().first()
        if u and check_password_hash(u["password"], password):
            if u["role"] == "admin":
                flash("This is an admin account. Please use the separate Admin Login.", "warning")
                return redirect(url_for("admin_login"))
            session.clear()
            session.permanent = True
            session["user_id"] = u["id"]
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        with engine.connect() as con:
            admin = con.execute(text(
                "SELECT * FROM users WHERE username=:u AND role='admin'"
            ), {"u": username}).mappings().first()
        if admin and check_password_hash(admin["password"], password):
            session.clear()
            session.permanent = True
            session["admin_id"] = admin["id"]
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin username or password.", "danger")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    session.permanent = True
    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.permanent = True
    return redirect(url_for("home"))

@app.route("/dashboard")
def dashboard():
    if not current_user():
        return redirect(url_for("login"))
    with engine.connect() as con:
        rows = con.execute(text(
            "SELECT * FROM analyses WHERE user_id=:uid ORDER BY id DESC"
        ), {"uid": session["user_id"]}).mappings().all()
    return render_template("dashboard.html", analyses=rows)

@app.route("/analyzer")
def analyzer():
    if not current_user():
        return redirect(url_for("login"))
    return render_template("analyzer.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    if not current_user():
        return jsonify({"error": "Login required"}), 401
    f = request.files.get("resume")
    if not f or not f.filename:
        return jsonify({"error": "Please select a resume."}), 400
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in {"pdf", "docx", "txt"}:
        return jsonify({"error": "Only PDF, DOCX and TXT files are allowed."}), 400

    original_name = secure_filename(f.filename)
    safe = f"{uuid.uuid4().hex[:10]}_{original_name}"
    path = os.path.join(UPLOAD_DIR, safe)
    f.save(path)
    try:
        text_content = extract_resume_text(path, ext)
        result = analyze_resume(text_content)
        result["file_type"] = ext.upper()
        result["text_extracted"] = True
        result["career_recommendations"] = career_recommendations(result["skills"], text_content)
        with engine.begin() as con:
            row = con.execute(text("""
                INSERT INTO analyses(user_id,filename,score,result_json)
                VALUES(:uid,:fn,:score,:result)
                RETURNING id
            """), {
                "uid": session["user_id"], "fn": safe, "score": result["score"],
                "result": json.dumps(result)
            }).first()
            analysis_id = row[0]
        return jsonify({"ok": True, "id": analysis_id, "result": result})
    except Exception as e:
        try:
            os.remove(path)
        except OSError:
            pass
        return jsonify({"error": str(e) or "Could not analyze the resume."}), 422

@app.route("/result/<int:analysis_id>")
def result(analysis_id):
    if not current_user():
        return redirect(url_for("login"))
    with engine.connect() as con:
        row = con.execute(text(
            "SELECT * FROM analyses WHERE id=:id AND user_id=:uid"
        ), {"id": analysis_id, "uid": session["user_id"]}).mappings().first()
    if not row:
        flash("Analysis not found.", "danger")
        return redirect(url_for("dashboard"))
    return render_template("result.html", analysis=row, result=json.loads(row["result_json"]))

@app.route("/career")
def career():
    if not current_user():
        return redirect(url_for("login"))
    return render_template("career.html")

@app.route("/api/career", methods=["POST"])
def api_career():
    if not current_user():
        return jsonify({"error": "Login required"}), 401
    data = request.get_json(silent=True) or {}
    skills = [s.strip().lower() for s in data.get("skills", []) if isinstance(s, str) and s.strip()]
    return jsonify({"recommendations": career_recommendations(skills, "")})

def admin_required():
    if "admin_id" not in session:
        return False
    return get_user(session["admin_id"], "admin") is not None

@app.route("/admin")
def admin_dashboard():
    if not admin_required():
        return redirect(url_for("admin_login"))
    with engine.connect() as con:
        users = con.execute(text(
            "SELECT id,name,username,role,created_at FROM users ORDER BY id DESC"
        )).mappings().all()
        analyses = con.execute(text("""
            SELECT a.id,a.filename,a.score,a.created_at,u.name,u.username
            FROM analyses a JOIN users u ON u.id=a.user_id
            ORDER BY a.id DESC
        """)).mappings().all()
        stats = {
            "users": con.execute(text("SELECT COUNT(*) FROM users WHERE role='user'")).scalar_one(),
            "analyses": con.execute(text("SELECT COUNT(*) FROM analyses")).scalar_one(),
            "avg": round(float(con.execute(text(
                "SELECT COALESCE(AVG(score),0) FROM analyses"
            )).scalar_one()), 1)
        }
    return render_template("admin.html", users=users, analyses=analyses, stats=stats)

@app.route("/admin/delete-user/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    if not admin_required():
        return jsonify({"error": "Forbidden"}), 403
    if user_id == session.get("admin_id"):
        flash("You cannot delete the current admin account.", "danger")
        return redirect(url_for("admin_dashboard"))
    with engine.begin() as con:
        con.execute(text("DELETE FROM analyses WHERE user_id=:id"), {"id": user_id})
        con.execute(text("DELETE FROM users WHERE id=:id AND role='user'"), {"id": user_id})
    flash("User deleted.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete-analysis/<int:analysis_id>", methods=["POST"])
def delete_analysis(analysis_id):
    if not admin_required():
        return jsonify({"error": "Forbidden"}), 403
    with engine.begin() as con:
        con.execute(text("DELETE FROM analyses WHERE id=:id"), {"id": analysis_id})
    flash("Analysis deleted.", "success")
    return redirect(url_for("admin_dashboard"))

@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "File is too large. Maximum size is 8 MB."}), 413

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
