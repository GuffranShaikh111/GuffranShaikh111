from flask import Flask, render_template, request, redirect, session
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)

app.secret_key = 'secretkey'

# Upload Folder
app.config['UPLOAD_FOLDER'] = 'uploads'

# MySQL Connection
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'smart_job'

mysql = MySQL(app)

# Home Page
@app.route('/')
def home():
    return render_template('index.html')


# Register
@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()

        cur.execute(
        "INSERT INTO users(name,email,password) VALUES(%s,%s,%s)",
        (name,email,password)
        )

        mysql.connection.commit()

        return '''
        <script>
        alert("Registration Successful");
        window.location="/login";
        </script>
        '''

    return render_template('register.html')


# Login
@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()

        cur.execute(
        "SELECT * FROM users WHERE email=%s AND password=%s",
        (email,password)
        )

        user = cur.fetchone()

        if user:

            session['user_id'] = user[0]
            session['user_name'] = user[1]

            return redirect('/dashboard')

        else:

            return '''
            <script>
            alert("Invalid Email or Password");
            window.location="/login";
            </script>
            '''

    return render_template('login.html')


# Dashboard
@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect('/login')

    return render_template(
    'dashboard.html',
    username=session['user_name']
    )


# Jobs Page
@app.route('/jobs', methods=['GET', 'POST'])
def jobs():

    if 'user_id' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()

    # Apply Job
    if request.method == 'POST':

        job_id = request.form['job_id']

        resume = request.files['resume']

        filename = secure_filename(resume.filename)

        resume.save(
        os.path.join(app.config['UPLOAD_FOLDER'], filename)
        )

        user_id = session['user_id']

        cur.execute(
        "INSERT INTO applications(user_id,job_id,resume) VALUES(%s,%s,%s)",
        (user_id,job_id,filename)
        )

        mysql.connection.commit()

        return '''
        <script>
        alert("Application Submitted Successfully");
        window.location="/jobs";
        </script>
        '''

    # Fetch Jobs
    cur.execute("SELECT * FROM jobs")

    jobs = cur.fetchall()

    return render_template('jobs.html', jobs=jobs)


# Logout
@app.route('/logout')
def logout():

    session.clear()

    return redirect('/')


# Run Server
if __name__ == '__main__':
    app.run(debug=True)