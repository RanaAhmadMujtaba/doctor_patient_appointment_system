# app.py (Flask main app file using flask_mysqldb and original SQL setup)
from flask import Flask, render_template
from flask_mysqldb import MySQL
import os

app = Flask(__name__)
app.config.from_pyfile('config.py')
app.secret_key = app.config['SECRET_KEY']
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Initialize MySQL
mysql = MySQL(app)

app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


from routes import *  # Import routes after app and mysql are created

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True)
