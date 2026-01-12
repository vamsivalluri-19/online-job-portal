import os
from datetime import datetime

from flask import (
    Flask, render_template, redirect, url_for,
    request, flash, send_from_directory
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, login_user, logout_user,
    current_user, login_required, UserMixin
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from config import Config, allowed_file

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


# ========== MODELS ==========

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")  # student | recruiter | admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    resumes = db.relationship("Resume", backref="user", lazy=True)
    applications = db.relationship("Application", backref="user", lazy=True)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Job(db.Model):
    __tablename__ = "jobs"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    company = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(150), nullable=False)
    skills_required = db.Column(db.String(255), nullable=False)  # comma-separated skills
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))  # recruiter id

    applications = db.relationship("Application", backref="job", lazy=True)


class Resume(db.Model):
    __tablename__ = "resumes"
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    skills = db.Column(db.String(255))  # extracted/entered skills
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)


class Application(db.Model):
    __tablename__ = "applications"
    id = db.Column(db.Integer, primary_key=True)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    match_score = db.Column(db.Float, default=0.0)  # AI-style matching score
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ========== HELPER FUNCTIONS ==========

def ensure_admin():
    # create a default admin if not exists
    admin_email = "admin@portal.com"
    admin = User.query.filter_by(email=admin_email).first()
    if not admin:
        admin = User(
            full_name="Portal Admin",
            email=admin_email,
            role="admin"
        )
        admin.set_password("admin123")  # change later
        db.session.add(admin)
        db.session.commit()


def calculate_match_score(job_skills: str, resume_skills: str) -> float:
    """
    Very simple skill matching:
    score = (common skills / job skills) * 100
    """
    if not job_skills or not resume_skills:
        return 0.0
    job_set = {s.strip().lower() for s in job_skills.split(",") if s.strip()}
    resume_set = {s.strip().lower() for s in resume_skills.split(",") if s.strip()}
    if not job_set:
        return 0.0
    common = job_set.intersection(resume_set)
    return round(len(common) / len(job_set) * 100, 2)


# ========== AUTH ROUTES ==========

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role", "student")

        if User.query.filter_by(email=email).first():
            flash("Email already registered. Please login.", "warning")
            return redirect(url_for("login"))

        user = User(full_name=full_name, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Registration successful, please login.", "success")
        return redirect(url_for("login"))

    return render_template("auth/register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        selected_role = request.form.get("role")  # 'student' or 'recruiter'

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if selected_role and user.role != selected_role and user.role != "admin":
                flash(f"You are registered as {user.role}, not {selected_role}.", "warning")
                return redirect(url_for("login"))

            login_user(user)
            flash("Logged in successfully.", "success")
            if user.role == "admin":
                return redirect(url_for("admin_dashboard"))
            elif user.role == "recruiter":
                return redirect(url_for("recruiter_dashboard"))
            else:
                return redirect(url_for("student_dashboard"))

        flash("Invalid credentials.", "danger")

    return render_template("auth/login.html")

    return render_template("auth/login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ========== ADMIN ROUTES ==========

@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if current_user.role != "admin":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("login"))

    total_users = User.query.count()
    total_jobs = Job.query.count()
    total_applications = Application.query.count()
    student_count = User.query.filter_by(role="student").count()
    recruiter_count = User.query.filter_by(role="recruiter").count()

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_jobs=total_jobs,
        total_applications=total_applications,
        student_count=student_count,
        recruiter_count=recruiter_count
    )

# ========== RECRUITER ROUTES ==========
@app.route("/recruiter/dashboard")
@login_required
def recruiter_dashboard():
    if current_user.role != "recruiter":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("login"))

    jobs = Job.query.filter_by(created_by=current_user.id).order_by(Job.created_at.desc()).all()
    job_ids = [job.id for job in jobs]
    total_applications = Application.query.filter(Application.job_id.in_(job_ids)).count()

    return render_template(
        "recruiter/dashboard.html",
        jobs=jobs,
        total_applications=total_applications
    )


@app.route("/recruiter/post-job", methods=["GET", "POST"])
@login_required
def recruiter_post_job():
    if current_user.role != "recruiter":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title")
        company = request.form.get("company")
        location = request.form.get("location")
        skills_required = request.form.get("skills_required")
        description = request.form.get("description")

        job = Job(
            title=title,
            company=company,
            location=location,
            skills_required=skills_required,
            description=description,
            created_by=current_user.id
        )
        db.session.add(job)
        db.session.commit()
        flash("Job posted successfully.", "success")
        return redirect(url_for("recruiter_dashboard"))

    return render_template("recruiter/post_job.html")


@app.route("/recruiter/job/<int:job_id>/applications")
@login_required
def recruiter_view_applications(job_id):
    if current_user.role != "recruiter":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("login"))

    job = Job.query.get_or_404(job_id)
    if job.created_by != current_user.id:
        flash("You can only view applications for your jobs.", "danger")
        return redirect(url_for("recruiter_dashboard"))

    applications = Application.query.filter_by(job_id=job.id).order_by(Application.applied_at.desc()).all()
    return render_template("recruiter/application.html", job=job, applications=applications)


# ========== STUDENT ROUTES ==========

@app.route("/")
@login_required
def home():
    if current_user.role == "admin":
        return redirect(url_for("admin_dashboard"))
    elif current_user.role == "recruiter":
        return redirect(url_for("recruiter_dashboard"))
    return redirect(url_for("student_dashboard"))


@app.route("/student/dashboard")
@login_required
def student_dashboard():
    if current_user.role != "student":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("login"))

    jobs = Job.query.order_by(Job.created_at.desc()).all()
    # show last uploaded resume (if any)
    resume = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.uploaded_at.desc()).first()
    return render_template("student/dashboard.html", jobs=jobs, resume=resume)


@app.route("/student/job/<int:job_id>")
@login_required
def student_job_detail(job_id):
    if current_user.role != "student":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("login"))

    job = Job.query.get_or_404(job_id)
    # find latest resume for match score display
    resume = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.uploaded_at.desc()).first()
    score = None
    if resume and resume.skills:
        score = calculate_match_score(job.skills_required, resume.skills)

    return render_template("student/job.html", job=job, resume=resume, score=score)


@app.route("/student/apply/<int:job_id>", methods=["POST"])
@login_required
def student_apply(job_id):
    if current_user.role != "student":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("login"))

    job = Job.query.get_or_404(job_id)
    resume = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.uploaded_at.desc()).first()
    if not resume:
        flash("Upload a resume before applying.", "warning")
        return redirect(url_for("student_dashboard"))

    # basic duplicate check
    existing = Application.query.filter_by(user_id=current_user.id, job_id=job.id).first()
    if existing:
        flash("You have already applied for this job.", "info")
        return redirect(url_for("student_job_detail", job_id=job.id))

    score = calculate_match_score(job.skills_required, resume.skills or "")
    application = Application(user_id=current_user.id, job_id=job.id, match_score=score)
    db.session.add(application)
    db.session.commit()
    flash(f"Applied successfully! Match score: {score}%", "success")
    return redirect(url_for("student_job_detail", job_id=job.id))


@app.route("/student/upload-resume", methods=["GET", "POST"])
@login_required
def upload_resume():
    if current_user.role != "student":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        skills = request.form.get("skills")
        file = request.files.get("resume")

        if not file or file.filename == "":
            flash("No file selected.", "warning")
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash("Invalid file type. Upload pdf/doc/docx.", "danger")
            return redirect(request.url)

        filename = secure_filename(file.filename)
        # ensure upload dir exists
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(save_path)

        resume = Resume(
            filename=filename,
            original_name=file.filename,
            skills=skills,
            user_id=current_user.id
        )
        db.session.add(resume)
        db.session.commit()
        flash("Resume uploaded successfully.", "success")
        return redirect(url_for("student_dashboard"))

    return render_template("student/upload_resume.html")


@app.route("/uploads/resumes/<filename>")
@login_required
def download_resume(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)
def seed_sample_jobs():
    """Create sample recruiter and 20 demo jobs if none exist."""
    # check if jobs already exist
    if Job.query.count() > 0:
        return

    # ensure at least one recruiter
    recruiter = User.query.filter_by(role="recruiter").first()
    if not recruiter:
        recruiter = User(
            full_name="Demo Recruiter",
            email="recruiter@demo.com",
            role="recruiter"
        )
        recruiter.set_password("recruiter123")
        db.session.add(recruiter)
        db.session.commit()

    sample_jobs = [
        {
            "title": "Java Backend Developer",
            "company": "TechWave Solutions",
            "location": "Hyderabad, India",
            "skills": "Java, Spring Boot, REST API, MySQL",
            "description": "Build and maintain RESTful services using Java and Spring Boot for large scale web applications."
        },
        {
            "title": "Full Stack Developer (MERN)",
            "company": "InnovateX Labs",
            "location": "Bengaluru, India",
            "skills": "React, Node.js, MongoDB, Express",
            "description": "Develop end-to-end features on a modern MERN stack platform used by thousands of students."
        },
        {
            "title": "Python Developer (Flask)",
            "company": "CloudBridge Pvt Ltd",
            "location": "Pune, India",
            "skills": "Python, Flask, SQLAlchemy, HTML, CSS",
            "description": "Design APIs and dashboards using Flask and integrate with front-end components."
        },
        {
            "title": "Junior Java Developer",
            "company": "NextGen Soft",
            "location": "Surat, India",
            "skills": "Java, OOP, Git, SQL",
            "description": "Work with senior engineers to implement new features and fix bugs in Java-based systems."
        },
        {
            "title": "Android Developer (Java)",
            "company": "MobileCraft",
            "location": "Mumbai, India",
            "skills": "Java, Android SDK, REST API, Firebase",
            "description": "Build Android applications and integrate them with RESTful backend services."
        },
        {
            "title": "Software Engineer Trainee",
            "company": "FutureTech Systems",
            "location": "Chennai, India",
            "skills": "Java, Data Structures, Algorithms, SQL",
            "description": "Learn software engineering best practices and contribute to core product modules."
        },
        {
            "title": "Back-End Engineer (Java)",
            "company": "ScaleUp Digital",
            "location": "Gurugram, India",
            "skills": "Java, Spring, Microservices, Docker",
            "description": "Develop microservices and improve performance of existing back-end systems."
        },
        {
            "title": "Junior Data Engineer",
            "company": "DataCraft Analytics",
            "location": "Noida, India",
            "skills": "Python, SQL, ETL, Pandas",
            "description": "Build data pipelines and support analytics dashboards used by business teams."
        },
        {
            "title": "Web Developer (HTML/CSS/JS)",
            "company": "PixelWorks Studio",
            "location": "Remote",
            "skills": "HTML, CSS, JavaScript, Responsive Design",
            "description": "Convert UI/UX designs into responsive and accessible web pages."
        },
        {
            "title": "DevOps Intern",
            "company": "CloudOps Hub",
            "location": "Hyderabad, India",
            "skills": "Linux, Git, CI/CD, Docker",
            "description": "Assist in maintaining CI/CD pipelines and containerized deployments."
        },
        {
            "title": "QA Engineer (Manual & Automation)",
            "company": "QualityFirst Tech",
            "location": "Bengaluru, India",
            "skills": "Testing, Selenium, Java, Test Cases",
            "description": "Design and execute test cases, automate regression test suites using Selenium."
        },
        {
            "title": "Frontend Developer (React)",
            "company": "UIFlow Labs",
            "location": "Pune, India",
            "skills": "React, JavaScript, HTML, CSS",
            "description": "Implement reusable UI components and optimize front-end performance."
        },
        {
            "title": "Backend Developer (Node.js)",
            "company": "APIForge",
            "location": "Mumbai, India",
            "skills": "Node.js, Express, MongoDB, REST",
            "description": "Develop scalable APIs and integrate third-party services."
        },
        {
            "title": "Associate Software Engineer",
            "company": "PrimeLogic",
            "location": "Ahmedabad, India",
            "skills": "Java, Spring, SQL, Git",
            "description": "Contribute to enterprise applications with guidance from senior engineers."
        },
        {
            "title": "AI/ML Intern",
            "company": "SmartSense AI",
            "location": "Bengaluru, India",
            "skills": "Python, ML, Pandas, Scikit-learn",
            "description": "Prototype machine learning models and help with data preparation."
        },
        {
            "title": "Database Developer",
            "company": "DataMatrix",
            "location": "Hyderabad, India",
            "skills": "SQL, PL/SQL, Performance Tuning",
            "description": "Design and optimize database schemas and queries for high performance."
        },
        {
            "title": "Support Engineer (L1)",
            "company": "HelpDesk Corp",
            "location": "Remote",
            "skills": "Troubleshooting, Linux, Networking Basics",
            "description": "Handle first-level support tickets and escalate complex issues."
        },
        {
            "title": "Cloud Engineer Trainee",
            "company": "SkyCloud Systems",
            "location": "Chennai, India",
            "skills": "AWS, Linux, Scripting, Networking",
            "description": "Assist in deploying and monitoring workloads on cloud platforms."
        },
        {
            "title": "Business Analyst Intern",
            "company": "InsightWorks",
            "location": "Noida, India",
            "skills": "Requirements Gathering, SQL, Excel",
            "description": "Work with stakeholders to capture requirements and support reporting."
        },
        {
            "title": "Junior Cybersecurity Analyst",
            "company": "SecureShield",
            "location": "Pune, India",
            "skills": "Networking, Security Basics, SIEM",
            "description": "Monitor security alerts and assist in vulnerability assessments."
        },
    ]

    for job in sample_jobs:
        new_job = Job(
            title=job["title"],
            company=job["company"],
            location=job["location"],
            skills_required=job["skills"],
            description=job["description"],
            created_by=recruiter.id
        )
        db.session.add(new_job)

    db.session.commit()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        ensure_admin()
        seed_sample_jobs()
    app.run(debug=True)
