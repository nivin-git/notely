from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from datetime import datetime
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"

BASE_DIR = "users"
UPLOAD_DIR = "uploads/users"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf"}
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------- Helpers ----------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def user_dir(username):
    return os.path.join(BASE_DIR, username)

def subject_file(username, subject):
    return os.path.join(user_dir(username), f"{subject}.txt")

def upload_dir(username, subject):
    path = os.path.join(UPLOAD_DIR, username, subject)
    os.makedirs(path, exist_ok=True)
    return path

def role_file(username):
    return os.path.join(user_dir(username), "role.txt")

def get_role(username):
    rf = role_file(username)
    if os.path.exists(rf):
        with open(rf, "r") as f:
            return f.read().strip()
    return "user"


# ---------- Login ----------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        udir = user_dir(username)
        os.makedirs(udir, exist_ok=True)
        pwd_file = os.path.join(udir, "password.txt")

        if not os.path.exists(pwd_file):
            with open(pwd_file, "w") as f:
                f.write(password)

            role = "admin" if username.lower() == "admin" else "user"
            with open(role_file(username), "w") as rf:
                rf.write(role)
        else:
            with open(pwd_file, "r") as f:
                if f.read() != password:
                    return "❌ Wrong Password"

        session["user"] = username
        return redirect(url_for("notes"))

    return render_template("login.html")


# ---------- Notes ----------
@app.route("/notes", methods=["GET", "POST"])
def notes():
    if "user" not in session:
        return redirect(url_for("login"))

    username = session["user"]
    subject = request.args.get("subject")

    udir = user_dir(username)
    subjects = []
    subject_alerts = {}

    if os.path.exists(udir):
        for f in os.listdir(udir):
            if f.endswith(".txt") and f not in ("password.txt", "role.txt"):
                sub = f.replace(".txt", "")
                subjects.append(sub)

                # 🔔 Check reminder presence
                has_reminder = False
                sf_path = subject_file(username, sub)
                if os.path.exists(sf_path):
                    with open(sf_path, "r", encoding="utf-8") as sf:
                        for line in sf:
                            if "⏰" in line:
                                has_reminder = True
                                break

                subject_alerts[sub] = has_reminder

    notes_list = []
    files = []

    if subject:
        sf = subject_file(username, subject)
        if os.path.exists(sf):
            with open(sf, "r", encoding="utf-8") as f:
                notes_list = f.readlines()

        up = upload_dir(username, subject)
        if os.path.exists(up):
            files = os.listdir(up)

    # ---------- Add Note / Upload ----------
    if request.method == "POST":
        subject = request.args.get("subject")
        if not subject:
            return redirect(url_for("notes"))

        note = request.form.get("note")

        if note:
            time = datetime.now().strftime("%d-%m-%Y %I:%M %p")
            with open(subject_file(username, subject), "a", encoding="utf-8") as f:
                f.write(f"{time} | {note}\n")

        if "file" in request.files:
            file = request.files["file"]
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(upload_dir(username, subject), filename))

        return redirect(url_for("notes", subject=subject))

    return render_template(
        "index.html",
        user=username,
        subject=subject,
        subjects=subjects,
        subject_alerts=subject_alerts,
        notes=notes_list,
        files=files
    )


# ---------- Create Subject ----------
@app.route("/add_subject", methods=["POST"])
def add_subject():
    if "user" not in session:
        return redirect(url_for("login"))

    username = session["user"]
    subject = request.form["subject"].strip()

    if subject:
        path = subject_file(username, subject)
        if not os.path.exists(path):
            open(path, "w", encoding="utf-8").close()

    return redirect(url_for("notes", subject=subject))


# ---------- Delete Subject ----------
@app.route("/delete_subject", methods=["POST"])
def delete_subject():
    if "user" not in session:
        return redirect(url_for("login"))

    username = session["user"]
    subject = request.form["subject"]

    sf = subject_file(username, subject)
    if os.path.exists(sf):
        os.remove(sf)

    up = upload_dir(username, subject)
    if os.path.exists(up):
        for f in os.listdir(up):
            os.remove(os.path.join(up, f))
        os.rmdir(up)

    return redirect(url_for("notes"))


# ---------- Files ----------
@app.route("/uploads/<username>/<subject>/<filename>")
def uploaded_file(username, subject, filename):
    return send_from_directory(upload_dir(username, subject), filename)


# ---------- Edit Note ----------
@app.route("/edit", methods=["POST"])
def edit_note():
    username = session["user"]
    subject = request.form["subject"]
    index = int(request.form["index"])
    new_text = request.form["new_note"]

    file_path = subject_file(username, subject)
    with open(file_path, "r", encoding="utf-8") as f:
        notes = f.readlines()

    time = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    notes[index] = f"{time} | {new_text}\n"

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(notes)

    return redirect(url_for("notes", subject=subject))


# ---------- Delete Note ----------
@app.route("/delete", methods=["POST"])
def delete_note():
    username = session["user"]
    subject = request.form["subject"]
    index = int(request.form["index"])

    file_path = subject_file(username, subject)
    with open(file_path, "r", encoding="utf-8") as f:
        notes = f.readlines()

    if 0 <= index < len(notes):
        notes.pop(index)

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(notes)

    return redirect(url_for("notes", subject=subject))


# ---------- Delete File ----------
@app.route("/delete_file", methods=["POST"])
def delete_file():
    username = session["user"]
    subject = request.form["subject"]
    filename = request.form["filename"]

    file_path = os.path.join(upload_dir(username, subject), filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    return redirect(url_for("notes", subject=subject))


# ---------- Logout ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
