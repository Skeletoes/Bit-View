"""Simple Flask application demonstrating file upload, login,
file viewing, and an SQLite database helper.

Routes
------
* ``/``               - redirects to login
* ``/login``          - login form and authentication
* ``/home``           - lists files and folders for the logged-in user
* ``/upload``         - file upload form and handler
* ``/create_folder``  - new folder creation handler
* ``/download``       - download a selected file
* ``/view``           - view a selected image in the browser
* ``/files/<path>``   - securely serve a file by URL (used by /view)

Database helpers use ``g`` for connection caching and support being
packaged with PyInstaller.
"""

# ============================================================================
# Standard library imports
# ============================================================================
import os
import sys
import sqlite3

# ============================================================================
# Third-party imports
# ============================================================================
from flask import (
    Flask, abort, flash, g, redirect, render_template,
    request, send_file, url_for
)
from flaskwebgui import FlaskUI
from werkzeug.utils import secure_filename

# ============================================================================
# Configuration constants
# ============================================================================

# File extensions permitted for upload
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'exe'}

# Subset of extensions that can be viewed in-browser
VIEWABLE_FILES = {'png', 'jpg', 'jpeg'}

# Resolve database path; works for both normal execution and PyInstaller bundles
if getattr(sys, 'frozen', False):
    # PyInstaller extracts bundled files to sys._MEIPASS at runtime
    database_dir = sys._MEIPASS
else:
    # Normal execution: database lives alongside this script
    database_dir = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(database_dir, 'database.db')

# ============================================================================
# Application setup
# ============================================================================

app = Flask(__name__)
app.secret_key = "qa567-KLu8T-ZgD45-9sdfg-1234"  # Required for flash messages

# Global that holds the current logged-in user's database row.
# NOTE: this is not session-safe for multi-user deployments.
user = None

# ============================================================================
# Helper functions
# ============================================================================

def allowed_file(filename):
    """Return True if *filename* has a permitted upload extension.

    Checks that the name contains a '.' and that everything after the
    last '.' is in ALLOWED_EXTENSIONS (case-insensitive).
    """
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )


# ============================================================================
# Database helpers
# ============================================================================

def get_db():
    """Return a cached SQLite connection for the current request.

    The connection is stored on Flask's ``g`` object so it is reused within
    a single request and automatically closed at teardown.
    """
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db


@app.teardown_appcontext
def close_connection(exception):
    """Close the SQLite connection when the application context tears down."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    """Execute *query* with *args* and return results.

    :param query: SQL query string.
    :param args:  Positional parameters bound to the query (prevents SQL injection).
    :param one:   If True, return only the first row (or None). Otherwise a list.
    """
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


# ============================================================================
# Route handlers
# ============================================================================

# --- Authentication ----------------------------------------------------------

@app.route('/')
def index():
    """Redirect the root URL to the login page."""
    return redirect(url_for('user_login'))


@app.route('/login', methods=['GET', 'POST'])
def user_login():
    """Render and handle the login form.

    GET  → show the login page.
    POST → validate credentials against the database; on success store the
           user row globally and redirect to /home.
    """
    global user

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Parameterised query prevents SQL injection
        user = query_db(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, password),
            one=True,
        )

        if user is not None:
            # Store the user's upload folder in Flask config for easy access
            app.config['UPLOAD_FOLDER'] = user[5]
            return redirect(url_for('home'))
        else:
            flash("Invalid credentials!", "error")

    return render_template('login.html')


# --- Home / file listing -----------------------------------------------------

@app.route('/home')
def home():
    """List all files and folders in the logged-in user's main directory."""
    mainDirectory = user[6]
    userObjects = os.listdir(mainDirectory)
    return render_template('home.html', objects=userObjects)


# --- Folder management -------------------------------------------------------

@app.route('/create_folder', methods=['GET', 'POST'])
def create_folder():
    """Handle creation of a new sub-folder inside the user's upload directory.

    POST → validate the folder name, create the directory, redirect to /home.
    GET  → show the create-folder form.
    """
    if request.method == 'POST':
        user_input = request.form['folder_name'].strip()

        if not user_input:
            flash("Enter a name for folder!", "error")
        else:
            new_folder_path = os.path.join(app.config['UPLOAD_FOLDER'], user_input)
            try:
                # exist_ok=True avoids an error if the folder already exists
                os.makedirs(new_folder_path, exist_ok=True)
            except Exception as e:
                flash(f"Error creating folder: {e}", "error")

            return redirect(url_for('home'))

    return render_template('create_folder.html')


# --- File upload -------------------------------------------------------------

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    """Handle file upload via multipart/form-data.

    POST → validate the uploaded file (presence, name, extension), save it,
           then redirect to /home.
    GET  → render the upload form.
    """
    if request.method == 'POST':
        # Ensure the 'file' field exists in the request
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)

        file = request.files['file']

        # An empty filename means the user submitted without choosing a file
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            # secure_filename strips dangerous characters from the name
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return redirect(url_for('home'))

    return render_template('upload_file.html')


# --- File download -----------------------------------------------------------

@app.route('/download', methods=['POST'])
def download():
    """Send the selected file as a download attachment.

    Expects 'objectSelection' in the POST body (the filename relative to the
    user's main directory).
    """
    mainDirectory = user[6]
    objectSelection = request.form.get('objectSelection')
    objectPath = os.path.join(mainDirectory, objectSelection)

    if os.path.isfile(objectPath):
        # as_attachment=True triggers a Save-As dialog in the browser
        return send_file(objectPath, as_attachment=True)

    # If the selection was a folder (or missing), fall back to home
    return render_template('home.html')


# --- File serving (used internally by /view) ---------------------------------

@app.route('/files/<path:filename>')
def serve_file(filename):
    """Serve a user file by URL so the browser can display it.

    This route is used by the /view endpoint to convert a server-side path
    into a browser-accessible URL.

    A path-traversal guard ensures that 'filename' cannot escape the user's
    main directory (e.g. via '../../etc/passwd').
    """
    mainDirectory = user[6]
    safe_path = os.path.join(mainDirectory, filename)

    # Resolve symlinks / '..' segments and confirm we're still inside mainDirectory
    if not os.path.abspath(safe_path).startswith(os.path.abspath(mainDirectory)):
        abort(403)  # Forbidden – attempted directory traversal

    return send_file(safe_path)


# --- File viewer -------------------------------------------------------------

@app.route('/view', methods=['POST'])
def view():
    """Render a viewable file (image) in the browser.

    Only files whose extension is in VIEWABLE_FILES are served; everything
    else is silently ignored and falls back to /home.
    """
    mainDirectory = user[6]
    objectSelection = request.form.get('objectSelection')
    objectPath = os.path.join(mainDirectory, objectSelection)

    if os.path.isfile(objectPath):
        extension = objectPath.rsplit('.', 1)[1].lower()

        if extension in VIEWABLE_FILES:
            # Build a proper URL via serve_file so the browser can fetch it
            file_url = url_for('serve_file', filename=objectSelection)
            return render_template('view.html', objectView=file_url)

    # Not a viewable file – redirect back to home
    return redirect(url_for('home'))


# ============================================================================
# Entry point
# ============================================================================

if __name__ == '__main__':
    # FlaskUI wraps the app in a lightweight desktop window via webview
    FlaskUI(app=app, server="flask", width=800, height=480, port=8000).run()