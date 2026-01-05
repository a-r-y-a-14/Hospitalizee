from flask import Flask, render_template, request, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import Date
import math
import json
from firebase_admin import credentials, auth
import firebase_admin
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
cred_path = os.path.join(BASE_DIR, "firebase_key.json")

cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)

app = Flask(__name__)
app.secret_key = "dont_look_at_my_key" 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hospitalizee.db'
db = SQLAlchemy(app)

today = date.today() #hello
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
    depts = db.Column(JSON, nullable=True)
    cur_emergency_availability = db.Column(db.Integer, nullable=False)
    cur_emergency_doctors = db.Column(JSON, nullable = True)

class Departments(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    qualification = db.Column(db.String(200), nullable=False)
    experience = db.Column(db.Integer, nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)
    slots = db.Column(JSON, nullable=False, default=list)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    fname = db.Column(db.String(100), nullable=False)
    lname = db.Column(db.String(100), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)
    appointment_date = db.Column(Date, nullable=False)
    appointment_slot = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False)

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

def init_db(app):
    with app.app_context():
        db.create_all()
        default_departments = ["Cardiology", "Orthopaedics", "Neurology", "Paediatrics", "General Medicine", "Emergency", "Pulmonology", "Gastroenterology", "ENT", "Opthalmology", "Dematology", "Psychiatry"]
        for name in default_departments:
            exists = Departments.query.filter_by(name=name).first()
            if not exists:
                db.session.add(Departments(name=name))
        db.session.commit()


DEPARTMENT_RULES = {
    "Cardiology": [
        "chest pain", "heart", "palpitation", "cardiac", "bp", "blood pressure"
    ],
    "Neurology": [
        "headache", "seizure", "faint", "numb", "paralysis", "dizziness", "stroke"
    ],
    "Orthopedics": [
        "fracture", "bone", "leg pain", "arm pain", "fall", "injury", "joint"
    ],
    "Pulmonology": [
        "breath", "asthma", "cough", "lungs", "respiratory", "breathing"
    ],
    "Gastroenterology": [
        "stomach", "vomit", "abdominal", "diarrhea", "acid"
    ],
    "ENT": [
        "ear", "nose", "throat", "sinus"
    ],
    "Ophthalmology": [
        "eye", "vision", "blurred", "red eye"
    ],
    "Dermatology": [
        "skin", "rash", "itching", "allergy"
    ],
    "Psychiatry": [
        "anxiety", "panic", "depression", "stress", "hallucination"
    ]
}
def classify_emergency(text):
    text = text.lower()
    scores = {}
    for dept, keywords in DEPARTMENT_RULES.items():
        score = sum(1 for kw in keywords if re.search(rf"\b{kw}\b", text))
        if score > 0:
            scores[dept] = score
    if not scores:
        return "General Medicine", 0.55
    best_dept = max(scores, key=scores.get)
    confidence = min(0.95, 0.6 + scores[best_dept] * 0.1)
    return best_dept, round(confidence, 2)


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

@app.route("/patient/verify-login", methods=["POST"])
def patient_verify_login():
    token = request.json.get("token")

    try:
        decoded = auth.verify_id_token(token)
        email = decoded["email"]
        user = db.session.query(Patient.id).filter(Patient.email == email).first()
        if not user:
            session['user_email'] = email
            return jsonify({"status": "register", "email": email})
        session['user_id'] = user.id
        return jsonify({
            "status": "success",
        })
    except:
        return jsonify({"status": "invalid"}), 401

@app.route('/patient/dashboard')
def patient_dashboard():
    if 'user_id' not in session:
        return render_template(
            'alert.html', 
            message="You are not logged in.",
            redirect_url="/patient/login"
        )
    user = Patient.query.get(session['user_id'])
    u_app = db.session.query(Appointment.appointment_date.label('date'), Appointment.appointment_slot.label('slot'), Doctor.name.label('doctor_name'), Hospital.name.label('hospital_name')).join(Doctor, Appointment.doctor_id == Doctor.id).join(Hospital, Appointment.hospital_id == Hospital.id).filter(Appointment.patient_id == user.id, Appointment.appointment_date >= today).all()
    p_app = db.session.query(Appointment.appointment_date.label('date'), Appointment.appointment_slot.label('slot'), Doctor.name.label('doctor_name'), Hospital.name.label('hospital_name')).join(Doctor, Appointment.doctor_id == Doctor.id).join(Hospital, Appointment.hospital_id == Hospital.id).filter(Appointment.patient_id == user.id, Appointment.appointment_date < today).all()
    session['patient_id'] = user.id
    return render_template('patient_dashboard.html', user=user, u_app=u_app, p_app=p_app)

@app.route('/patient/logout')
def logout():
    session.clear()
    return render_template(
        'alert.html',
        message="You have been logged out successfully.",
        redirect_url="/patient/login"
    )

@app.route('/patient/register', methods=['GET', 'POST'])
def new_patient():
    user_email = session.get('user_email')
    if request.method == "POST":
        password = request.form.get('password')
        fname = request.form.get('fname')
        lname = request.form.get('lname')
        phone = request.form.get('phone')
        pincode = request.form.get('pincode')
        dob = datetime.strptime(request.form.get('dob'), "%Y-%m-%d").date()

        lat = request.form.get('lat')
        lon = request.form.get('long')

        if user_email:
            email = user_email
        else:
            email = request.form.get('email')


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
    
    return render_template('patient_registration.html', email=user_email)

@app.route('/patient/new-appointment', methods=['GET', 'POST'])
def patient_new_appointment():
    depts = Departments.query.all()
    return render_template('patient_new_appointment.html', depts=depts)

@app.route('/get-doctors/<int:dept_id>')
def get_doctors(dept_id):
    doctors = Doctor.query.filter_by(department=dept_id).all()
    hospitals = Hospital.query.all()
    return jsonify([
        {"id": f"{d.id},{h.id}", "name": d.name, "hname" : h.name}
        for d in doctors for h in hospitals if d.hospital_id == h.id
    ])

@app.route('/get-slots/<doctor_id>')
def get_slots(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id.split(',')[0])
    return jsonify(doctor.slots)


@app.route('/patient/confirm-appointment', methods=['POST'])
def confirm_appointment():
    fname = request.form.get('fname')
    lname = request.form.get('lname')
    date = datetime.strptime(request.form.get('date'), "%Y-%m-%d").date()
    patient_id = session['patient_id']
    doct_id = request.form.get('doct_id').split(',')[0]
    hosp_id = request.form.get('doct_id').split(',')[1]
    slot = request.form.get('slot')

    new_app = Appointment(fname=fname, lname=lname, appointment_date=date, patient_id=patient_id, doctor_id=doct_id, hospital_id=hosp_id, appointment_slot=slot, status="Pending")
    db.session.add(new_app)
    db.session.commit()

    return render_template(
        'alert.html',
        message="Appointment registered successfully!",
        redirect_url="/patient/dashboard"
    )

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

@app.route("/hospital/verify-login", methods=["POST"])
def hospital_verify_login():
    token = request.json.get("token")

    try:
        decoded = auth.verify_id_token(token)
        email = decoded["email"]
        user = db.session.query(Hospital.id).filter(Hospital.email == email).first()
        if not user:
            session['user_email'] = email
            return jsonify({"status": "register", "email": email})
        session['user_id'] = user.id
        return jsonify({
            "status": "success",
        })
    except:
        return jsonify({"status": "invalid"}), 401

@app.route('/hospital/dashboard')
def hospital_dashboard():
    if 'user_id' not in session:
        return render_template(
            'alert.html',
            message="You are not logged in.",
            redirect_url="/hospital/login"
        )
    user = Hospital.query.get(session['user_id'])
    depts = []
    if user.depts:
        dept_ids = [dept_id for dept_id in user.depts]
        for id in dept_ids:
            dept = Departments.query.get(int(id))
            if dept:
                depts.append(dept.name)
    session['hospital_id'] = user.id
    
    doctors = (
        db.session.query(
            Doctor.name,
            Departments.name.label("dept_name")
        )
        .join(Departments, Doctor.department_id == Departments.id)
        .filter(Doctor.hospital_id == user.id)
        .all()
    )
    
    total_beds = user.emergency_capacity
    available_beds = user.cur_emergency_availability
    occupied_beds = total_beds - available_beds

    return render_template(
        'hospital_dashboard.html',
        user=user,
        depts=depts,
        doctors=doctors,
        total_beds=total_beds,
        available_beds=available_beds,
        occupied_beds=occupied_beds
    )

@app.route('/hospital/logout')
def hospital_logout():
    session.clear()
    return render_template(
        'alert.html',
        message="You have been logged out successfully.",
        redirect_url="/hospital/login"
    )

@app.route('/hospital/new-doctor', methods=['GET', 'POST'])
def hospital_new_doctor():
    if 'hospital_id' not in session:
        return redirect('/hospital/login')
    if request.method == "POST":
        fname = request.form.get('fname')
        lname = request.form.get('lname')
        name = f"{fname} {lname}"
        department = request.form.get('department')
        qualification = request.form.get('qualification')
        experience = request.form.get('experience')
        slots = json.loads(request.form['slots'])
        hospital_id = session['hospital_id']

        new_doctor = Doctor(name=name, department_id=department, qualification=qualification, experience=experience, hospital_id=hospital_id, slots=slots)
        db.session.add(new_doctor)
        db.session.commit()

        session['user_id'] = hospital_id
        return render_template(
            'alert.html',
            message="Doctor added successfully!",
            redirect_url="/hospital/dashboard?"
        )
    hos = Hospital.query.filter(Hospital.id==session['hospital_id']).first()
    hos_depts = hos.depts
    depts = Departments.query.filter(Departments.id.in_(hos_depts))
    return render_template('hospital_new_doctor.html', depts=depts)

@app.route('/hospital/new-department', methods=['GET', 'POST'])
def hospital_new_department():
    if 'hospital_id' not in session:
        return redirect('/hospital/login')
    if request.method == "POST":
        name = request.form.get('name')

        dept = Departments.query.filter_by(name=name).first()
        if dept:
            dept_id = dept.id
            hosp = Hospital.query.get(session['hospital_id'])
            if not hosp.depts:
                hosp.depts = []
            if dept_id in hosp.depts:
                return render_template(
                    'alert.html',
                    message="Department already exists in your hospital!",
                    redirect_url="/hospital/dashboard"
                )
            hosp.depts.append(dept_id)
            flag_modified(hosp, "depts")
            db.session.commit()
        else:
            new_dept = Departments(name=name)
            db.session.add(new_dept)
            db.session.commit()
            dept_id = db.session.query(Departments.id).filter(Departments.name == name).first()
            hosp = Hospital.query.get(session['hospital_id'])
            hosp.depts.append(dept_id)
            db.session.commit()

        return render_template(
            'alert.html',
            message="Department added successfully!",
            redirect_url="/hospital/dashboard"
        )
    return render_template('hospital_new_department.html')

@app.route('/hospital/update-beds/occupied',methods=['GET','POST'])
def update_occupied_beds():
    if 'user_id' not in session:
        return redirect('/hospital/login')
    hospital=Hospital.query.get(session['user_id'])
    if request.method=='POST':
        occupied=int(request.form.get('occupied'))
        hospital.cur_emergency_availability=hospital.emergency_capacity-occupied
        db.session.commit()
        return redirect('/hospital/dashboard')
    return render_template(
        'emergency_occupied_beds.html', 
        max_value=hospital.emergency_capacity
    )
    
@app.route('/hospital/update-beds/total',methods=['GET','POST'])
def update_total_beds():
    if 'user_id' not in session:
        return redirect('/hospital/login')
    hospital=Hospital.query.get(session['user_id'])
    if request.method=='POST':
        total=int(request.form.get('total'))
        hospital.emergency_capacity=total
        db.session.commit()
        return redirect('/hospital/dashboard')
    return render_template(
        'emergency_total_beds.html', 
        max_value=200
    )

@app.route('/hospital/register', methods=['GET', 'POST'])
def hospital_register():
    user_email = session.get('user_email')
    if request.method == "POST":
        password = request.form.get('password')
        name = request.form.get('name')
        pincode = request.form.get('pincode')
        address = request.form.get('address')
        gid = request.form.get('gid')
        tel = request.form.get('phone')

        lat = request.form.get('lat')
        lon = request.form.get('long')

        if user_email:
            email = user_email
        else:
            email = request.form.get('email')

        emergency_capacity = request.form.get('emergency_capacity')


        if Hospital.query.filter_by(email=email).first():
            return render_template(
                "alert.html",
                message="Hospital already exists! Please login.",
                redirect_url="/hospital/login"
            )

        new_user = Hospital(gid=gid, email=email, password=password, name=name, telephone=tel, pincode=pincode, address=address, lat=lat, lon=lon, emergency_capacity=emergency_capacity, cur_emergency_availability=emergency_capacity, cur_emergency_doctors = [], depts=[])
        db.session.add(new_user)
        db.session.commit()

        return render_template(
            "alert.html",
            message="Registration successful! Please login.",
            redirect_url="/hospital/login"
        )

    return render_template('hospital_registration.html', email=user_email)

@app.route('/emergency')
def emergency():
    fname = request.args.get('fname')
    lname = request.args.get('lname')
    dob = request.args.get('dob')
    phone = request.args.get('phone')
    email = request.args.get('email')
    address = request.args.get('address')
    pincode = request.args.get('pincode')
    reason = request.args.get('reason')

    if not all([fname, lname, dob, phone, email, address, pincode, reason]):
        return render_template('emergency.html')
    
    return render_template('emergency.html', fname=fname, lname=lname, dob=dob, phone=phone, email=email, address=address, pincode=pincode, reason=reason)

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

    dept, conf = classify_emergency(reason)

    if conf <= 0.55:
        if lat and lon:
            all_hospitals = Hospital.query.all()
            sorted_hospitals = sorted(all_hospitals, key=lambda h: haversine(float(lat), float(lon), h.lat, h.lon))
            hospitals = [h for h in sorted_hospitals if h.cur_emergency_availability > 0][:3]
        else:
            hospitals = Hospital.query.filter_by(pincode=pincode).limit(3).all()
    else:
        dept_id = Departments.query.filter_by(name=dept).first()
        hosp = Hospital.query.all()
        all_hosp = []
        for h in hosp:
            cur_depts = []
            cur_docs = h.cur_emergency_doctors
            for doc in cur_docs:
                doct = Doctor.query.filter_by(id=doc).first()
                cur_depts.append(doct.department_id)
            if dept_id in cur_depts:
                all_hosp.append(h.id)
        if lat and lon:
            all_hospitals = Hospital.query.filter(Hospital.id.in_(all_hosp)).all()
            sorted_hospitals = sorted(all_hospitals, key=lambda h: haversine(float(lat), float(lon), h.lat, h.lon))
            hospitals = [h for h in sorted_hospitals if h.cur_emergency_availability > 0] + [h for h in sorted(Hospital.query.all(), key=lambda h: haversine(float(lat), float(lon), h.lat, h.lon)) if h.cur_emergency_availability > 0]
            hospitals = hospitals[:3]
        else:
            hospitals = Hospital.query.filter(Hospital.id.in_(all_hosp), Hospital.pincode==pincode).all() + Hospital.query.filter_by(pincode=pincode).limit(3).all()
            hospitals = hospitals[:3]


    return render_template('emergency_rec.html', fname=fname, lname=lname, dob=dob, phone=phone, email=email, address=address, pincode=pincode, reason=reason, hospitals=hospitals, dept=dept)

@app.route('/emergency/book-emergency', methods=['POST'])
def book_emergency():
    hospital_id = request.form.get('hospital_id')
    fname = request.args.get('fname')
    lname = request.args.get('lname')
    dob = datetime.strptime(request.args.get('dob'), "%Y-%m-%d").date()
    phone = request.args.get('phone')
    email = request.args.get('email')
    address = request.args.get('address')
    pincode = request.args.get('pincode')
    reason = request.args.get('reason')
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
    init_db(app)
    app.run(debug=True)