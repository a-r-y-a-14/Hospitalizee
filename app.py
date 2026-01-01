from flask import Flask, render_template, request, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from sqlalchemy.dialects.postgresql import JSON
import math

app = Flask(__name__)
app.secret_key = "dont_look_at_my_key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hospitalizee.db'
db = SQLAlchemy(app)

today = date.today()
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in KM
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + \
        math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


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
    gid = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    telephone = db.Column(db.String(15), nullable=False)
    pincode = db.Column(db.Integer, nullable=False)
    lat = db.Column(db.Float, nullable=True)
    lon = db.Column(db.Float, nullable=True)
    emergency_capacity = db.Column(db.Integer, nullable=False)
    cur_emergency_availability = db.Column(db.Integer, nullable=False, default=emergency_capacity)

class Departments(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), db.ForeignKey('departments.id'), nullable=False)
    qualification = db.Column(db.String(200), nullable=False)
    experience = db.Column(db.Integer, nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)
    slots = db.Column(JSON, nullable=False)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    appointment_slot = db.Column(db.String(50), nullable=False)

class EmergencyBooking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(100), nullable=False)
    patient_id = db.Column(db.Integer, nullable=True)
    dob = db.Column(db.Date, nullable=True)
    phone = db.Column(db.String(15), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    pincode = db.Column(db.Integer, nullable=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)
    booking_time = db.Column(db.DateTime, default=datetime.now)
    reason = db.Column(db.String(300), nullable=False)

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
    u_app = db.session.query(Appointment, Doctor.name.label('doctor_name'), Hospital.name.label('hospital_name')).join(Doctor, Appointment.doctor_id == Doctor.id).join(Hospital, Appointment.hospital_id == Hospital.id).filter(Appointment.patient_id == user.id, Appointment.appointment_date >= today).all()
    p_app = db.session.query(Appointment, Doctor.name.label('doctor_name'), Hospital.name.label('hospital_name')).join(Doctor, Appointment.doctor_id == Doctor.id).join(Hospital, Appointment.hospital_id == Hospital.id).filter(Appointment.patient_id == user.id, Appointment.appointment_date < today).all()
    return render_template('patient_dashboard.html', user=user, u_app=u_app, p_app=p_app)

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

@app.route('/hospital/login', methods=['GET', 'POST'])
def hospital_login():
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')

        user = Hospital.query.filter_by(email=email).first()
        if not user:
            return render_template(
                'alert.html',
                message="User doesn't exist! Please register.",
                redirect_url="/hospital/register"
            )
        if user.password == password:
            session['user_id'] = user.id
            return redirect('/hospital/dashboard')
        else:
            return render_template(
                'alert.html',
                message="Incorrect password! Please try again.",
                redirect_url="/hospital/login"
            )

    return render_template('hospital_login.html')

@app.route('/hospital/dashboard')
def hospital_dashboard():
    if 'user_id' not in session:
        return redirect('/hospital/login')
    user = Hospital.query.get(session['user_id'])
    return render_template('hospital_dashboard.html', user=user)

@app.route('/hospital/logout')
def hospital_logout():
    return render_template(
        'alert.html',
        message="You have been logged out successfully.",
        redirect_url="/hospital/login"
    )

@app.route('/hospital/register', methods=['GET', 'POST'])
def hospital_register():
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        pincode = request.form.get('pincode')
        address = request.form.get('address')
        gid = request.form.get('gid')
        tel = request.form.get('phone')

        lat = request.form.get('lat')
        lon = request.form.get('long')

        emergency_capacity = request.form.get('emergency_capacity')


        if Hospital.query.filter_by(email=email).first():
            return render_template(
                "alert.html",
                message="Hospital already exists! Please login.",
                redirect_url="/hospital/login"
            )

        new_user = Hospital(gid=gid, email=email, password=password, name=name, telephone=tel, pincode=pincode, address=address, lat=lat, lon=lon, emergency_capacity=emergency_capacity)
        db.session.add(new_user)
        db.session.commit()

        return render_template(
            "alert.html",
            message="Registration successful! Please login.",
            redirect_url="/hospital/login"
        )

    return render_template('hospital_registration.html')

@app.route('/emergency')
def emergency():
    return render_template('emergency.html')

@app.route('/emergency_hosp', methods=['POST'])
def emergency_hosp():
    fname = request.form.get('fname')
    lname = request.form.get('lname')
    dob = request.form.get('dob')
    phone = request.form.get('phone')
    email = request.form.get('email')
    address = request.form.get('address')
    pincode = request.form.get('pincode')
    reason = request.form.get('emergency_reason')

    lat = request.form.get('lat')
    lon = request.form.get('long')

    if lat and lon:
        all_hospitals = Hospital.query.all()
        sorted_hospitals = sorted(all_hospitals, key=lambda h: haversine(float(lat), float(lon), h.lat, h.lon))
        hospitals = [h for h in sorted_hospitals if h.cur_emergency_availability > 0][:3]
    else:
        hospitals = Hospital.query.filter_by(pincode=pincode).limit(3).all()

    return render_template('emergency_rec.html', fname=fname, lname=lname, dob=dob, phone=phone, email=email, address=address, pincode=pincode, reason=reason, hospitals=hospitals)

@app.route('/emergency/book-emergency', methods=['POST'])
def book_emergency():
    hospital_id = request.form.get('hospital_id')
    fname = request.form.get('fname')
    lname = request.form.get('lname')
    dob = request.form.get('dob')
    phone = request.form.get('phone')
    email = request.form.get('email')
    address = request.form.get('address')
    pincode = request.form.get('pincode')
    reason = request.form.get('reason')
    patient_name = f"{fname} {lname}"

    new_booking = EmergencyBooking(patient_name=patient_name, dob=dob, phone=phone, email=email, address=address, pincode=pincode, hospital_id=hospital_id, booking_time=datetime.now(), reason=reason)
    db.session.add(new_booking)
    db.session.commit()

    hospital = Hospital.query.get(hospital_id)

    return render_template(
        'alert.html',
        message=f"Emergency booking successful at {hospital.name}. Please proceed to the hospital.",
        redirect_url="/"
    )


if __name__ == '__main__':
    app.run(debug=True)