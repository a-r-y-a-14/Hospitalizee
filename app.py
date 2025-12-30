from flask import Flask, render_template, request, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSON

app = Flask(__name__)
app.secret_key = "this_is_a_secret_key_change_it"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hospitalizee.db'
db = SQLAlchemy(app)

#db_models
class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    fname = db.Column(db.String(100), nullable=False)
    lname = db.Column(db.String(100), nullable=False)
    dob = db.Column(db.Date, nullable=False)
    phone = db.Column(db.String(15), nullable=True)
    password = db.Column(db.String(200), nullable=False)
    pincode = db.Column(db.Integer, nullable=False)
    lat = db.Column(db.Float, nullable=True)
    lon = db.Column(db.Float, nullable=True)

class Hospital(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    telephone = db.Column(db.String(15), nullable=False)
    pincode = db.Column(db.Integer, nullable=False)
    lat = db.Column(db.Float, nullable=True)
    lon = db.Column(db.Float, nullable=True)
    emergency_capacity = db.Column(db.Integer, nullable=False)

class Departments(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), db.ForeignKey('departments.id'), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)
    slots = db.Column(JSON, nullable=False)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    appointment_slot = db.Column(db.String(50), nullable=False)

with app.app_context():
    db.create_all()

#routes
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/patient/login', methods=['GET', 'POST'])
def patient_login():
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')

        user = Patient.query.filter_by(email=email).first()
        if not user:
            return render_template(
                'alert.html',
                message="User doesn,t exist! Please register.",
                redirect_url="/patient/register"
            )
        if user.password == password:
            session['user_id'] = user.id
            return redirect('/patient/dashboard')
        else:
            return render_template(
                'alert.html',
                message="Incorrect password! Please try again.",
                redirect_url="/patient/login"
            )

    return render_template('patient_login.html')

@app.route('/patient/dashboard')
def patient_dashboard():
    if 'user_id' not in session:
        return redirect('/patient/login')
    user = Patient.query.get(session['user_id'])
    return render_template('patient_dashboard.html', user=user)

@app.route('/patient/logout')
def logout():
    return render_template(
        'alert.html',
        message="You have been logged out successfully.",
        redirect_url="/patient/login"
    )

@app.route('/patient/register', methods=['GET', 'POST'])
def new_patient():
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        fname = request.form.get('fname')
        lname = request.form.get('lname')
        phone = request.form.get('phone')
        pincode = request.form.get('pincode')
        dob = datetime.strptime(request.form.get('dob'), "%Y-%m-%d").date()

        lat = request.form.get('lat')
        lon = request.form.get('long')


        if Patient.query.filter_by(email=email).first():
            return render_template(
                "alert.html",
                message="Patient already exists! Please login.",
                redirect_url="/patient/login"
            )

        new_user = Patient(email=email, password=password, fname=fname, lname=lname, phone=phone, pincode=pincode, dob=dob, lat=lat, lon=lon)
        db.session.add(new_user)
        db.session.commit()

        return render_template(
            "alert.html",
            message="Registration successful! Please login.",
            redirect_url="/patient/login"
        )
    
    return render_template('patient_registration.html')

@app.route('/patient/new-appointment')
def patient_new_appointment():
    depts = Departments.query.all()
    return render_template('patient_new_appointment.html', depts=depts)

@app.route('/get-doctors/<int:dept_id>')
def get_doctors(dept_id):
    doctors = Doctor.query.filter_by(department_id=dept_id).all()
    hospitals = Hospital.query.all()

    return jsonify([
        {"id": d.id, "name": d.name, "hname" : h.name}
        for d in doctors for h in hospitals if d.hospital_id == h.id
    ])

@app.route('/hospital/login')
def hospital():
    return render_template('hospital_login.html')

@app.route('/hospital/dashboard')

@app.route('/hospital/logout')

@app.route('/hospital/register')



@app.route('/emergency')
def emergency():
    return render_template('emergency.html')

if __name__ == '__main__':
    app.run(debug=True)