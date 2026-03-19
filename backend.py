"""Simple Flask application demonstrating file upload, login
page, and an SQLite database helper.

Routes
------
* ``/`` - redirects to login
* ``/login`` - login form
* ``/upload`` - file upload form and handler
* ``/download/<name>`` - mock download endpoint

Database helpers use ``g`` for connection caching and support being
packaged with PyInstaller.
"""

# Standard library imports
import os
import sys
import sqlite3

# Third-party imports
from flask import Flask, flash, request, redirect, url_for, render_template, g
from werkzeug.utils import secure_filename
from flaskwebgui import FlaskUI

# ----------------------------------------------------------------------------
# Configuration constants
# ----------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'exe'}

# Determine path to database; supports normal script and PyInstaller bundle
if getattr(sys, 'frozen', False):
    # Running as a bundled PyInstaller executable
    database_dir = sys._MEIPASS
else:
    # Running as a normal Python script
    database_dir = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(database_dir, 'database.db')

# ----------------------------------------------------------------------------
# Application setup
# ----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = "qa567-KLu8T-ZgD45-9sdfg-1234"  # Needed for flashing messages


def allowed_file(filename):
    """Return True if the filename has an allowed extension.

    This is used by the upload handler to validate incoming files before
    saving them to disk. It checks that the filename contains a period and
    that the extension (after the last '.') is in the global
    ``ALLOWED_EXTENSIONS`` set.
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------------------------------------------------------------------------
# Database helper functions
# ---------------------------------------------------------------------------

def get_db():
    """Get a connection to the SQLite database stored in ``DATABASE``.

    The connection is stored on Flask's ``g`` object so that the same
    connection can be reused throughout a request and closed automatically
    at teardown.
    """
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
# automatic cleanup of the database connection at the end of each request

def close_connection(exception):
    """Close the database connection when the app context tears down."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    """Execute a database query and return results.

    :param query: SQL query string
    :param args: parameters for the SQL query
    :param one: if True, return a single row (or None). Otherwise return a
        list of rows.
    """
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    """Handle file upload via multipart/form-data.

    GET requests simply render the upload form. POST requests perform several
    checks:
      * ensure the ``file`` field is present
      * make sure a filename was provided
      * verify the file extension is allowed
    If everything passes the file is saved into ``UPLOAD_FOLDER`` and the
    user is redirected to a mock download page.
    """
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return redirect(url_for('home'))
    return render_template('upload_file.html')

# ----------------------------------------------------------------------------
# Route handlers
# ----------------------------------------------------------------------------

@app.route('/')
def index():
    """Root URL redirects to the login page."""
    # Using `url_for` keeps the URL generation in sync, even if endpoint
    # names change later.
    return redirect(url_for('user_login'))


@app.route('/login', methods=['GET', 'POST'])
def user_login():
    """Render the login template.

    In a real application, you'd handle form submission here and authenticate
    the user. For now this simply serves the login HTML page.
    """

    if request.method == 'POST':
        # Here you would normally validate the username and password
        username = request.form['username']
        password = request.form['password']
        query = """SELECT * FROM users WHERE username = ? AND password = ?"""
        user = query_db(query, (username, password), one=True)
        if user is not None:
            print(f"User '{username}' logged in successfully!")
            USER_FOLDER = user[6]
            app.config['UPLOAD_FOLDER'] = USER_FOLDER
            return redirect(url_for('home'))
        else:
            flash("Invalid credentials!", "error")
    return render_template('login.html')

@app.route('/home')
def home():
    return render_template('home.html')



if __name__ == '__main__':
    FlaskUI(app=app, server="flask", width=800, height=480, port=8000).run()
    app.run(debug=True)