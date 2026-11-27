from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os

app = app = Flask(__name__, template_folder='.')
app.config['SECRET_KEY'] = 'royal-animal-world-secret-change-this-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///royal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PRODUCT_FOLDER'] = 'static/products'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PRODUCT_FOLDER'], exist_ok=True)
os.makedirs('static/css', exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'staff_login'
login_manager.login_message_category = 'info'

# ==================== MODELS ====================

class Staff(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(50), default='Staff')
    password_hash = db.Column(db.String(200), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pet_name = db.Column(db.String(100), nullable=False)
    breed = db.Column(db.String(100))
    owner_name = db.Column(db.String(120), nullable=False)
    owner_phone = db.Column(db.String(40))
    age = db.Column(db.String(40))
    weight = db.Column(db.Float)
    complaint = db.Column(db.String(300))
    clinical_notes = db.Column(db.Text)
    vacc_status = db.Column(db.String(20), default='Unknown')
    next_appt = db.Column(db.String(20))
    created_by = db.Column(db.Integer, db.ForeignKey('staff.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    files = db.relationship('MedicalFile', backref='patient', lazy=True, cascade='all, delete-orphan')


class MedicalFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    original_name = db.Column(db.String(200))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('staff.id'))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    image = db.Column(db.String(200))
    category = db.Column(db.String(80), default='General')
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('staff.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return Staff.query.get(int(user_id))


# ==================== ROUTES ====================

@app.route('/')
def home():
    products = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).limit(8).all()
    return render_template('index.html', products=products)


@app.route('/shop')
def shop():
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    return render_template('shop.html', products=products)


@app.route('/staff/login', methods=['GET', 'POST'])
def staff_login():
    if current_user.is_authenticated:
        return redirect(url_for('staff_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        staff = Staff.query.filter_by(username=username, is_active=True).first()
        if staff and staff.check_password(password):
            login_user(staff)
            flash(f'Welcome back, {staff.full_name}!', 'success')
            return redirect(url_for('staff_dashboard'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('staff_login.html')


@app.route('/staff/logout')
@login_required
def staff_logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))


@app.route('/staff/dashboard')
@login_required
def staff_dashboard():
    patients = Patient.query.order_by(Patient.updated_at.desc()).limit(20).all()
    products = Product.query.order_by(Product.created_at.desc()).limit(10).all()
    return render_template('staff_dashboard.html', patients=patients, products=products)
    
    return render_template('staff_dashboard.html', 
                           patients=patients, 
                           products=products,
                           today_count=today_count)

@app.route('/staff/patients')
@login_required
def staff_patients():
    patients = Patient.query.order_by(Patient.updated_at.desc()).all()
    return render_template('staff_patients.html', patients=patients)


@app.route('/staff/patient/new', methods=['GET', 'POST'])
@login_required
def new_patient():
    if request.method == 'POST':
        patient = Patient(
            pet_name=request.form.get('pet_name'),
            breed=request.form.get('breed'),
            owner_name=request.form.get('owner_name'),
            owner_phone=request.form.get('owner_phone'),
            age=request.form.get('age'),
            weight=float(request.form.get('weight') or 0),
            complaint=request.form.get('complaint'),
            clinical_notes=request.form.get('clinical_notes'),
            vacc_status=request.form.get('vacc_status'),
            next_appt=request.form.get('next_appt'),
            created_by=current_user.id
        )
        db.session.add(patient)
        db.session.commit()

        files = request.files.getlist('medical_files')
        for f in files:
            if f and f.filename:
                filename = secure_filename(f"{patient.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{f.filename}")
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                med_file = MedicalFile(
                    patient_id=patient.id,
                    filename=filename,
                    original_name=f.filename,
                    uploaded_by=current_user.id
                )
                db.session.add(med_file)
        db.session.commit()

        flash('Patient record created successfully.', 'success')
        return redirect(url_for('staff_patients'))

    return render_template('patient_form.html', patient=None)


@app.route('/staff/patient/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_patient(id):
    patient = Patient.query.get_or_404(id)

    if request.method == 'POST':
        patient.pet_name = request.form.get('pet_name')
        patient.breed = request.form.get('breed')
        patient.owner_name = request.form.get('owner_name')
        patient.owner_phone = request.form.get('owner_phone')
        patient.age = request.form.get('age')
        patient.weight = float(request.form.get('weight') or 0)
        patient.complaint = request.form.get('complaint')
        patient.clinical_notes = request.form.get('clinical_notes')
        patient.vacc_status = request.form.get('vacc_status')
        patient.next_appt = request.form.get('next_appt')

        files = request.files.getlist('medical_files')
        for f in files:
            if f and f.filename:
                filename = secure_filename(f"{patient.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{f.filename}")
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                med_file = MedicalFile(
                    patient_id=patient.id,
                    filename=filename,
                    original_name=f.filename,
                    uploaded_by=current_user.id
                )
                db.session.add(med_file)

        db.session.commit()
        flash('Patient record updated.', 'success')
        return redirect(url_for('edit_patient', id=patient.id))

    return render_template('patient_form.html', patient=patient)


@app.route('/staff/products')
@login_required
def staff_products():
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('staff_products.html', products=products)


@app.route('/staff/product/new', methods=['GET', 'POST'])
@login_required
def new_product():
    if request.method == 'POST':
        image_name = None
        if 'image' in request.files:
            img = request.files['image']
            if img and img.filename:
                image_name = secure_filename(f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{img.filename}")
                img.save(os.path.join(app.config['PRODUCT_FOLDER'], image_name))

        product = Product(
            name=request.form.get('name'),
            description=request.form.get('description'),
            price=float(request.form.get('price') or 0),
            stock=int(request.form.get('stock') or 0),
            category=request.form.get('category') or 'General',
            image=image_name,
            created_by=current_user.id
        )
        db.session.add(product)
        db.session.commit()
        flash('Product added successfully.', 'success')
        return redirect(url_for('staff_products'))

    return render_template('product_form.html', product=None)


@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ==================== INIT + 10 STAFF ACCOUNTS ====================

def create_staff_accounts():
    staff_list = [
        {"username": "admin", "full_name": "System Admin", "role": "Admin", "password": "admin2026"},
        {"username": "dr.adeola", "full_name": "Dr. Adeola Okonkwo", "role": "Vet", "password": "vet2026"},
        {"username": "dr.chinedu", "full_name": "Dr. Chinedu Eze", "role": "Vet", "password": "vet2026"},
        {"username": "nurse.funke", "full_name": "Nurse Funke Adebayo", "role": "Nurse", "password": "nurse2026"},
        {"username": "nurse.ibrahim", "full_name": "Nurse Ibrahim Musa", "role": "Nurse", "password": "nurse2026"},
        {"username": "reception1", "full_name": "Amaka Reception", "role": "Reception", "password": "desk2026"},
        {"username": "reception2", "full_name": "Tunde Reception", "role": "Reception", "password": "desk2026"},
        {"username": "pharm.joy", "full_name": "Joy Pharmacy", "role": "Pharmacy", "password": "pharm2026"},
        {"username": "lab.tech", "full_name": "Lab Technician", "role": "Lab", "password": "lab2026"},
        {"username": "manager", "full_name": "Clinic Manager", "role": "Manager", "password": "manager2026"},
    ]

    for s in staff_list:
        existing = Staff.query.filter_by(username=s["username"]).first()
        if not existing:
            staff = Staff(
                username=s["username"],
                full_name=s["full_name"],
                role=s["role"]
            )
            staff.set_password(s["password"])
            db.session.add(staff)
    db.session.commit()
    print("✅ 10 staff accounts ready")

@app.route('/staff/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current = request.form.get('current_password')
        new_pass = request.form.get('new_password')
        confirm = request.form.get('confirm_password')

        if not current_user.check_password(current):
            flash('Current password is wrong', 'danger')
        elif new_pass != confirm:
            flash('New passwords do not match', 'danger')
        elif len(new_pass) < 6:
            flash('Password must be at least 6 characters', 'danger')
        else:
            current_user.set_password(new_pass)
            db.session.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('staff_dashboard'))

    return render_template('change_password.html')


@app.route('/staff/create-staff', methods=['GET', 'POST'])
@login_required
def create_staff():
    if current_user.role != 'Admin':
        flash('Only Admin can create staff accounts', 'danger')
        return redirect(url_for('staff_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username').strip()
        full_name = request.form.get('full_name').strip()
        role = request.form.get('role')
        password = request.form.get('password')

        if Staff.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
        else:
            new_staff = Staff(username=username, full_name=full_name, role=role)
            new_staff.set_password(password)
            db.session.add(new_staff)
            db.session.commit()
            flash(f'Staff account "{username}" created successfully!', 'success')
            return redirect(url_for('staff_dashboard'))

    return render_template('create_staff.html')
# Create tables and staff accounts when the app starts
with app.app_context():
    db.create_all()
    create_staff_accounts()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
