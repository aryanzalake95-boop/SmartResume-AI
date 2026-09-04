from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3, os, json, uuid
from utils.resume_parser import extract_resume_text
from utils.analyzer import analyze_resume
from utils.career_advisor import career_recommendations

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "smartresume.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-this-secret")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
ALLOWED = {"pdf", "docx", "txt"}

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        score INTEGER NOT NULL,
        result_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    admin = con.execute("SELECT id FROM users WHERE username=?", ("admin",)).fetchone()
    if not admin:
        con.execute("INSERT INTO users(name,username,password,role) VALUES(?,?,?,?)", ("Administrator", "admin", generate_password_hash("admin123"), "admin"))
    con.commit(); con.close()

def current_user():
    if "admin_id" in session:
        con = db(); u = con.execute("SELECT * FROM users WHERE id=? AND role='admin'", (session["admin_id"],)).fetchone(); con.close()
        if u: return u
    if "user_id" not in session: return None
    con = db(); u = con.execute("SELECT * FROM users WHERE id=? AND role='user'", (session["user_id"],)).fetchone(); con.close()
    return u

@app.context_processor
def inject_user(): return {"current_user": current_user()}

@app.route("/")
def home(): return render_template("index.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip(); username = request.form.get("username", "").strip().lower(); password = request.form.get("password", "")
        if not name or not username or len(password) < 6:
            flash("Enter all fields. Password must be at least 6 characters.", "danger"); return redirect(url_for("register"))
        con = db()
        try:
            con.execute("INSERT INTO users(name,username,password) VALUES(?,?,?)", (name, username, generate_password_hash(password))); con.commit()
            flash("Registration successful. Please login.", "success"); return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username already exists.", "danger"); return redirect(url_for("register"))
        finally: con.close()
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower(); password = request.form.get("password", "")
        con = db(); u = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone(); con.close()
        if u and check_password_hash(u["password"], password):
            if u["role"] == "admin": flash("This is an admin account. Please use the separate Admin Login.", "warning"); return redirect(url_for("admin_login"))
            session.clear(); session["user_id"] = u["id"]; return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower(); password = request.form.get("password", "")
        con = db(); admin = con.execute("SELECT * FROM users WHERE username=? AND role='admin'", (username,)).fetchone(); con.close()
        if admin and check_password_hash(admin["password"], password): session.clear(); session["admin_id"] = admin["id"]; return redirect(url_for("admin_dashboard"))
        flash("Invalid admin username or password.", "danger")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout(): session.pop("admin_id", None); return redirect(url_for("home"))

@app.route("/logout")
def logout(): session.pop("user_id", None); return redirect(url_for("home"))

@app.route("/dashboard")
def dashboard():
    if not current_user(): return redirect(url_for("login"))
    con = db(); rows = con.execute("SELECT * FROM analyses WHERE user_id=? ORDER BY id DESC", (session["user_id"],)).fetchall(); con.close()
    return render_template("dashboard.html", analyses=rows)

@app.route("/analyzer")
def analyzer():
    if not current_user(): return redirect(url_for("login"))
    return render_template("analyzer.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    if not current_user(): return jsonify({"error":"Login required"}), 401
    f = request.files.get("resume")
    if not f or not f.filename: return jsonify({"error":"Please select a resume."}), 400
    ext = f.filename.rsplit(".",1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED: return jsonify({"error":"Only PDF, DOCX and TXT files are allowed."}), 400
    safe = f"{uuid.uuid4().hex[:10]}_{secure_filename(f.filename)}"; path = os.path.join(UPLOAD_DIR, safe); f.save(path)
    try:
        text = extract_resume_text(path, ext); result = analyze_resume(text); result["file_type"] = ext.upper(); result["text_extracted"] = True; result["career_recommendations"] = career_recommendations(result["skills"], text)
        con = db(); cur = con.execute("INSERT INTO analyses(user_id,filename,score,result_json) VALUES(?,?,?,?)", (session["user_id"], safe, result["score"], json.dumps(result))); con.commit(); analysis_id = cur.lastrowid; con.close()
        return jsonify({"ok":True, "id":analysis_id, "result":result})
    except Exception as e: return jsonify({"error": str(e) or "Could not analyze the resume."}), 422

@app.route("/result/<int:analysis_id>")
def result(analysis_id):
    if not current_user(): return redirect(url_for("login"))
    con = db(); row = con.execute("SELECT * FROM analyses WHERE id=? AND user_id=?", (analysis_id, session["user_id"])).fetchone(); con.close()
    if not row: flash("Analysis not found.", "danger"); return redirect(url_for("dashboard"))
    return render_template("result.html", analysis=row, result=json.loads(row["result_json"]))

@app.route("/career")
def career():
    if not current_user(): return redirect(url_for("login"))
    return render_template("career.html")

@app.route("/api/career", methods=["POST"])
def api_career():
    if not current_user(): return jsonify({"error":"Login required"}), 401
    data = request.get_json(silent=True) or {}; skills = [s.strip().lower() for s in data.get("skills", []) if isinstance(s, str) and s.strip()]
    return jsonify({"recommendations": career_recommendations(skills, "")})

def admin_required():
    if "admin_id" not in session: return False
    con = db(); admin = con.execute("SELECT id FROM users WHERE id=? AND role='admin'", (session["admin_id"],)).fetchone(); con.close(); return admin is not None

@app.route("/admin")
def admin_dashboard():
    if not admin_required(): return redirect(url_for("admin_login"))
    con = db(); users = con.execute("SELECT id,name,username,role,created_at FROM users ORDER BY id DESC").fetchall(); analyses = con.execute("SELECT a.id,a.filename,a.score,a.created_at,u.name,u.username FROM analyses a JOIN users u ON u.id=a.user_id ORDER BY a.id DESC").fetchall()
    stats = {"users": con.execute("SELECT COUNT(*) FROM users WHERE role='user'").fetchone()[0], "analyses": con.execute("SELECT COUNT(*) FROM analyses").fetchone()[0], "avg": round(con.execute("SELECT COALESCE(AVG(score),0) FROM analyses").fetchone()[0], 1)}; con.close()
    return render_template("admin.html", users=users, analyses=analyses, stats=stats)

@app.route("/admin/delete-user/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    if not admin_required(): return jsonify({"error":"Forbidden"}), 403
    if user_id == session.get("admin_id"): flash("You cannot delete the current admin account.", "danger"); return redirect(url_for("admin_dashboard"))
    con = db(); con.execute("DELETE FROM analyses WHERE user_id=?", (user_id,)); con.execute("DELETE FROM users WHERE id=? AND role='user'", (user_id,)); con.commit(); con.close(); flash("User deleted.", "success"); return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete-analysis/<int:analysis_id>", methods=["POST"])
def delete_analysis(analysis_id):
    if not admin_required(): return jsonify({"error":"Forbidden"}), 403
    con = db(); con.execute("DELETE FROM analyses WHERE id=?", (analysis_id,)); con.commit(); con.close(); flash("Analysis deleted.", "success"); return redirect(url_for("admin_dashboard"))

@app.errorhandler(413)
def too_large(_): return jsonify({"error":"File is too large. Maximum size is 8 MB."}), 413

init_db()

if __name__ == "__main__": app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
