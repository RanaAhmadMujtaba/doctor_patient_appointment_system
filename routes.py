# routes.py (fully rolled-back using flask_mysqldb)
from flask import render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from app import app, mysql
import os

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    next_page = request.args.get('next')

    if request.method == 'POST':
        try:
            email = request.form['email']
            password = request.form['password']

            cur = mysql.connection.cursor()
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            cur.close()

            if user and check_password_hash(user[3], password):
                session['user_id'] = user[0]
                session['user_role'] = user[4]

                flash('Login successful!', 'success')

                if next_page:
                    return redirect(next_page)

                if user[4] == 'admin':
                    return redirect(url_for('admin_dashboard'))
                elif user[4] == 'doctor':
                    return redirect(url_for('doctor_dashboard'))
                else:
                    return redirect(url_for('appointments'))
            else:
                flash('Invalid Email or Password.', 'error')

        except Exception as e:
            flash(f'Error during login: {str(e)}', 'error')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                    (name, email, password, 'patient'))
        mysql.connection.commit()
        cur.close()

        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/appointments', methods=['GET', 'POST'])
def appointments():
    if 'user_id' not in session or session['user_role'] != 'patient':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    # Booking logic
    if request.method == 'POST':
        doctor_id = request.form['doctor_id']
        appointment_date = request.form['appointment_date']
        patient_id = session['user_id']

        cur.execute("INSERT INTO appointments (patient_id, doctor_id, appointment_date) VALUES (%s, %s, %s)",
                    (patient_id, doctor_id, appointment_date))
        mysql.connection.commit()

    # Get list of available doctors
    cur.execute("SELECT id, name FROM users WHERE role = 'doctor'")
    doctors = cur.fetchall()

    # Get patient's own appointments
    cur.execute("""
        SELECT appointments.id, users.name AS doctor_name, appointments.appointment_date, appointments.status
        FROM appointments
        JOIN users ON appointments.doctor_id = users.id
        WHERE appointments.patient_id = %s
    """, (session['user_id'],))
    appointments = cur.fetchall()
    cur.close()

    return render_template('appointments.html', doctors=doctors, appointments=appointments)


@app.route('/doctor_dashboard')
def doctor_dashboard():
    if 'user_id' not in session or session['user_role'] != 'doctor':
        return redirect(url_for('login', next=request.url))

    cur = mysql.connection.cursor()
    cur.execute("SELECT appointments.id, users.name, appointments.appointment_date, appointments.status "
                "FROM appointments JOIN users ON appointments.patient_id = users.id "
                "WHERE appointments.doctor_id = %s", (session['user_id'],))
    doctor_appointments = cur.fetchall()
    cur.close()

    return render_template('doctor_dashboard.html', doctor_appointments=doctor_appointments)

@app.route('/confirm_appointment/<int:appointment_id>')
def confirm_appointment(appointment_id):
    if 'user_id' not in session or session['user_role'] != 'doctor':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("UPDATE appointments SET status = 'confirmed' WHERE id = %s", (appointment_id,))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('doctor_dashboard'))

@app.route('/cancel_appointment/<int:appointment_id>')
def cancel_appointment(appointment_id):
    if 'user_id' not in session or session['user_role'] != 'doctor':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("UPDATE appointments SET status = 'cancelled' WHERE id = %s", (appointment_id,))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('doctor_dashboard'))


@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session or session['user_role'] != 'admin':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) FROM doctors")
    total_doctors = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM users WHERE role = 'patient'")
    total_patients = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM appointments")
    total_appointments = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM appointments WHERE DATE(appointment_date) = CURDATE()")
    todays_appointments = cur.fetchone()[0]

    cur.close()

    return render_template('admin_dashboard.html', 
                           total_doctors=total_doctors, 
                           total_patients=total_patients,
                           total_appointments=total_appointments,
                           todays_appointments=todays_appointments)

@app.route('/add_doctor', methods=['GET', 'POST'])
def add_doctor():
    if 'user_id' not in session or session['user_role'] != 'admin':
        return redirect(url_for('login', next=request.url))

    if request.method == 'POST':
        try:
            name = request.form['name']
            email = request.form['email']
            password = request.form['password']
            specialization = request.form['specialization']
            availability = request.form['availability']

            hashed_password = generate_password_hash(password)

            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO doctors (name, specialization, availability) VALUES (%s, %s, %s)", 
                        (name, specialization, availability))

            cur.execute("INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, 'doctor')",
                        (name, email, hashed_password))

            mysql.connection.commit()
            cur.close()

            flash('Doctor added successfully!', 'success')

        except Exception as e:
            flash(f'Error adding doctor: {str(e)}', 'error')

        return redirect(url_for('admin_dashboard'))

    return render_template('add_doctor.html')

@app.route('/delete_doctor/<int:doctor_id>')
def delete_doctor(doctor_id):
    if 'user_id' not in session or session['user_role'] != 'admin':
        return redirect(url_for('login', next=request.url))

    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT name FROM doctors WHERE id = %s", (doctor_id,))
        doctor = cur.fetchone()

        if doctor:
            doctor_name = doctor[0]

            cur.execute("DELETE FROM appointments WHERE doctor_id = %s", (doctor_id,))
            cur.execute("DELETE FROM doctors WHERE id = %s", (doctor_id,))
            cur.execute("DELETE FROM users WHERE name = %s AND role = 'doctor'", (doctor_name,))

            mysql.connection.commit()
            flash('Doctor and related records deleted.', 'success')
        else:
            flash('Doctor not found.', 'error')

        cur.close()

    except Exception as e:
        flash(f'Error deleting doctor: {str(e)}', 'error')

    return redirect(url_for('admin_dashboard'))

@app.route('/upload_prescription/<int:appointment_id>', methods=['GET', 'POST'])
def upload_prescription(appointment_id):
    if 'user_id' not in session or session['user_role'] != 'doctor':
        return redirect(url_for('login'))

    if request.method == 'POST':
        file = request.files['prescription']
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO prescriptions (appointment_id, file_path)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE file_path = VALUES(file_path)
            """, (appointment_id, filepath))
            mysql.connection.commit()
            cur.close()

            flash('Prescription uploaded successfully.', 'success')
            return redirect(url_for('doctor_dashboard'))

    return render_template('upload_prescription.html', appointment_id=appointment_id)


@app.route('/medical_history')
def medical_history():
    if 'user_id' not in session or session['user_role'] != 'patient':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT appointments.id, 
               users.name AS doctor_name,
               appointments.appointment_date,
               appointments.status,
               prescriptions.file_path
        FROM appointments
        JOIN users ON appointments.doctor_id = users.id
        LEFT JOIN prescriptions ON appointments.id = prescriptions.appointment_id
        WHERE appointments.patient_id = %s
    """, (session['user_id'],))
    history = cur.fetchall()
    cur.close()

    return render_template('medical_history.html', history=history)

    return render_template('medical_history.html', history=history)

@app.route('/preview/<filename>')
def preview_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)



@app.route('/search_doctors', methods=['GET', 'POST'])
def search_doctors():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    query = "SELECT * FROM doctors"
    filters = []

    if request.method == 'POST':
        specialization = request.form.get('specialization')
        time = request.form.get('availability')

        if specialization:
            query += " WHERE specialization LIKE %s"
            filters.append('%' + specialization + '%')

        if time:
            if 'WHERE' in query:
                query += " AND availability = %s"
            else:
                query += " WHERE availability = %s"
            filters.append(time)

    cur.execute(query, tuple(filters))
    results = cur.fetchall()
    cur.close()

    return render_template('search_doctors.html', results=results)

@app.route('/contact_us')
def contact_us():
    return render_template('contact_us.html')

@app.route('/manage_doctors')
def manage_doctors():
    if 'user_id' not in session or session['user_role'] != 'admin':
        return redirect(url_for('login', next=request.url))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM doctors")
    doctors = cur.fetchall()

    cur.execute("SELECT appointments.id, users.name, doctors.name, appointments.appointment_date, appointments.status "
                "FROM appointments JOIN users ON appointments.patient_id = users.id "
                "JOIN doctors ON appointments.doctor_id = doctors.id")
    all_appointments = cur.fetchall()
    cur.close()

    return render_template('manage_doctors.html', doctors=doctors, appointments=all_appointments)

@app.route('/manage_patients')
def manage_patients():
    if 'user_id' not in session or session['user_role'] != 'admin':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    # Get all patients
    cur.execute("SELECT * FROM users WHERE role = 'patient'")
    patients = cur.fetchall()

    # Get all appointments
    cur.execute("""SELECT appointments.id, users.name, doctors.name, appointments.appointment_date, appointments.status
                   FROM appointments
                   JOIN users ON appointments.patient_id = users.id
                   JOIN doctors ON appointments.doctor_id = doctors.id""")
    all_appointments = cur.fetchall()

    cur.close()

    return render_template('manage_patients.html', appointments=all_appointments, patients=patients)



@app.route('/cancel_my_appointment/<int:appointment_id>')
def cancel_my_appointment(appointment_id):
    if 'user_id' not in session or session['user_role'] != 'patient':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE appointments 
        SET status = 'cancelled' 
        WHERE id = %s AND patient_id = %s
    """, (appointment_id, session['user_id']))
    mysql.connection.commit()
    cur.close()

    flash('Appointment cancelled successfully.', 'success')
    return redirect(url_for('appointments'))



@app.route('/admin_cancel_appointment/<int:appointment_id>')
def admin_cancel_appointment(appointment_id):
    if 'user_id' not in session or session['user_role'] != 'admin':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE appointments 
        SET status = 'cancelled' 
        WHERE id = %s
    """, (appointment_id,))
    mysql.connection.commit()
    cur.close()

    flash('Appointment cancelled by admin.', 'success')
    return redirect(url_for('manage_patients'))

@app.route('/delete_patient/<int:patient_id>')
def delete_patient(patient_id):
    if 'user_id' not in session or session['user_role'] != 'admin':
        return redirect(url_for('login'))

    try:
        cur = mysql.connection.cursor()

        cur.execute("SELECT * FROM users WHERE id = %s AND role = 'patient'", (patient_id,))
        patient = cur.fetchone()

        if patient:
            cur.execute("DELETE FROM users WHERE id = %s", (patient_id,))
            mysql.connection.commit()
            flash("Patient and related data deleted successfully.", "success")
        else:
            flash("Patient not found.", "error")

        cur.close()
    except Exception as e:
        flash(f"Error deleting patient: {str(e)}", "error")

    return redirect(url_for('manage_patients'))






@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
