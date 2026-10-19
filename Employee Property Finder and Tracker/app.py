from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import json
from config import Config
from models import User, Employee, Asset, Assignment
from forms import LoginForm, EmployeeForm, AssetForm, AssignmentForm, ApprovalForm, ReturnForm
from utils import login_required, get_asset_stats, get_department_stats
from flask_wtf.csrf import CSRFProtect
from wtforms.validators import Optional, Length, EqualTo

def create_admin_account():
    """Create admin account if it doesn't exist"""
    admin_email = 'admin@IT.com'
    admin_password = 'admin123'
    admin_name = 'System Administrator'

    # Check if admin user already exists
    existing_admin = mongo.db.users.find_one({'username': admin_email})
    if not existing_admin:
        # Create admin user account
        admin_user = User(
            username=admin_email,
            email=admin_email,
            password=admin_password,
            full_name=admin_name,
            role='admin'
        )
        mongo.db.users.insert_one(admin_user.to_dict())
        print(f"Admin account created: {admin_email}")
    else:
        print("Admin account already exists")

app = Flask(__name__)
app.config.from_object(Config)

# Additional configuration for Windows compatibility
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# Initialize extensions
mongo = PyMongo(app)
csrf = CSRFProtect(app)

# Custom JSON Encoder for MongoDB ObjectId
class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)

app.json_encoder = JSONEncoder

def generate_employee_id(department):
    """Generate employee ID based on department (e.g., IT001, HR001)"""
    # Department code mapping
    dept_codes = {
        'IT': 'IT',
        'HR': 'HR',
        'Marketing': 'MK',
        'Finance': 'FN',
        'Operations': 'OP',
        'Sales': 'SL',
        'Engineering': 'EN',
        'Administration': 'AD'
    }
    
    dept_code = dept_codes.get(department, 'XX')
    
    # Find the highest existing employee ID for this department
    pattern = f"^{dept_code}\\d+$"
    existing_ids = list(mongo.db.employees.find(
        {'employee_id': {'$regex': pattern}},
        {'employee_id': 1}
    ).sort('employee_id', -1).limit(1))
    
    if existing_ids:
        # Extract the number from the last ID and increment
        last_id = existing_ids[0]['employee_id']
        last_number = int(last_id[len(dept_code):])
        new_number = last_number + 1
    else:
        # Start with 001
        new_number = 1
    
    # Format as 3-digit number
    return f"{dept_code}{new_number:03d}"


# ==================== HOME & AUTH ROUTES ====================

@app.route('/')
def home():
    return render_template('home.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = mongo.db.users.find_one({'username': form.username.data})
        
        if user and User.verify_password(user['password_hash'], form.password.data):
            # Ensure user has a role (for backward compatibility)
            if 'role' not in user:
                # Set default role based on whether they exist in employees collection
                employee_check = mongo.db.employees.find_one({'email': user['username']})
                default_role = 'employee' if employee_check else 'admin'
                mongo.db.users.update_one(
                    {'_id': user['_id']},
                    {'$set': {'role': default_role}}
                )
                user['role'] = default_role
            
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            session.permanent = True
            flash(f'Welcome back, {user["full_name"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password!', 'danger')
    
    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('home'))


# ==================== DASHBOARD ====================

@app.route('/dashboard')
@login_required
def dashboard():
    user_role = session.get('role', 'employee')
    
    if user_role == 'admin':
        # Admin dashboard - shows all system statistics
        total_employees = mongo.db.employees.count_documents({'is_active': True})
        total_assets = mongo.db.assets.count_documents({})
        assigned_assets = mongo.db.assets.count_documents({'status': 'Assigned'})
        available_assets = mongo.db.assets.count_documents({'status': 'Available'})
        pending_approvals = mongo.db.assignments.count_documents({'approval_status': 'Pending'})
        
        # Get recent assignments
        recent_assignments = list(mongo.db.assignments.find({'status': 'Active', 'approval_status': 'Approved'}).sort('assigned_date', -1).limit(5))
        
        # Enrich with employee and asset details
        for assignment in recent_assignments:
            employee = mongo.db.employees.find_one({'_id': ObjectId(assignment['employee_id'])})
            asset = mongo.db.assets.find_one({'_id': ObjectId(assignment['asset_id'])})
            assignment['employee_name'] = employee['name'] if employee else 'Unknown'
            assignment['asset_details'] = f"{asset['brand']} {asset['model']}" if asset else 'Unknown'
        
        # Get asset distribution and department stats
        asset_stats = get_asset_stats(mongo)
        department_stats = get_department_stats(mongo)
        
        # Get employees and assets for quick assignment modal
        employees_list = list(mongo.db.employees.find({'is_active': True}).sort('name', 1))
        assets_list = list(mongo.db.assets.find({'status': 'Available'}).sort('asset_type', 1))
        
        return render_template('admin_dashboard.html',
                             total_employees=total_employees,
                             total_assets=total_assets,
                             assigned_assets=assigned_assets,
                             available_assets=available_assets,
                             pending_approvals=pending_approvals,
                             recent_assignments=recent_assignments,
                             asset_stats=asset_stats,
                             department_stats=department_stats,
                             employees_list=employees_list,
                             assets_list=assets_list)
    
    else:
        # Employee dashboard - shows only their assets and requests
        employee = mongo.db.employees.find_one({'email': session.get('username')})
        
        if not employee:
            flash('Employee profile not found!', 'danger')
            return redirect(url_for('logout'))
        
        # Get employee's pending approvals
        pending_approvals = list(mongo.db.assignments.find({
            'employee_id': str(employee['_id']),
            'approval_status': 'Pending'
        }).sort('assigned_date', -1))
        
        # Enrich pending approvals
        for assignment in pending_approvals:
            asset = mongo.db.assets.find_one({'_id': ObjectId(assignment['asset_id'])})
            assignment['asset'] = asset
        
        # Get employee's active assignments
        my_assignments = list(mongo.db.assignments.find({
            'employee_id': str(employee['_id']),
            'status': 'Active',
            'approval_status': 'Approved'
        }).sort('assigned_date', -1))
        
        # Enrich my assignments
        for assignment in my_assignments:
            asset = mongo.db.assets.find_one({'_id': ObjectId(assignment['asset_id'])})
            assignment['asset'] = asset
        
        # Get available assets for requesting
        available_assets = list(mongo.db.assets.find({}).sort('asset_type', 1).limit(10))
        
        return render_template('employee_dashboard.html',
                             employee=employee,
                             pending_approvals=pending_approvals,
                             my_assignments=my_assignments,
                             available_assets=available_assets)


# ==================== EMPLOYEE ROUTES ====================

@app.route('/employees')
@login_required
def employees():
    user_role = session.get('role', 'employee')
    if user_role != 'admin':
        flash('Access denied! Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    search_query = request.args.get('search', '')
    department_filter = request.args.get('department', '')
    
    query = {'is_active': True}
    if search_query:
        query['$or'] = [
            {'name': {'$regex': search_query, '$options': 'i'}},
            {'employee_id': {'$regex': search_query, '$options': 'i'}},
            {'email': {'$regex': search_query, '$options': 'i'}}
        ]
    if department_filter:
        query['department'] = department_filter
    
    employees_list = list(mongo.db.employees.find(query).sort('name', 1))
    
    # Get asset count for each employee
    for emp in employees_list:
        emp['asset_count'] = mongo.db.assignments.count_documents({
            'employee_id': str(emp['_id']),
            'status': 'Active'
        })
    
    return render_template('employees.html', employees=employees_list, 
                         search_query=search_query, department_filter=department_filter)


@app.route('/employees/add', methods=['GET', 'POST'])
@login_required
def add_employee():
    user_role = session.get('role', 'employee')
    if user_role != 'admin':
        flash('Access denied! Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    form = EmployeeForm()
    if form.validate_on_submit():
        # Generate employee ID automatically based on department
        employee_id = generate_employee_id(form.department.data)
        
        # Check if email already exists in users collection
        existing_user = mongo.db.users.find_one({'username': form.email.data})
        if existing_user:
            flash('Email already exists as a user!', 'danger')
            return render_template('employees.html', form=form, edit_mode=False)
        
        # Create employee record
        employee = Employee(
            employee_id=employee_id,
            name=form.name.data,
            email=form.email.data,
            department=form.department.data,
            phone=form.phone.data
        )
        
        employee_result = mongo.db.employees.insert_one(employee.to_dict())
        
        # Create user account for the employee
        user = User(
            username=form.email.data,  # Use email as username
            email=form.email.data,
            password=form.password.data,
            full_name=form.name.data,
            role='employee'
        )
        mongo.db.users.insert_one(user.to_dict())
        
        flash(f'Employee and login credentials created successfully! Employee ID: {employee_id}', 'success')
        return redirect(url_for('employees'))
    
    return render_template('employees.html', form=form, edit_mode=False)


@app.route('/employees/edit/<employee_id>', methods=['GET', 'POST'])
@login_required
def edit_employee(employee_id):
    user_role = session.get('role', 'employee')
    if user_role != 'admin':
        flash('Access denied! Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    employee = mongo.db.employees.find_one({'_id': ObjectId(employee_id)})
    if not employee:
        flash('Employee not found!', 'danger')
        return redirect(url_for('employees'))
    
    # Get the associated user account
    user = mongo.db.users.find_one({'username': employee['email']})
    
    form = EmployeeForm(data=employee)
    # Remove password validation for editing (make it optional)
    form.password.validators = [Optional(), Length(min=6)]
    form.confirm_password.validators = [Optional(), EqualTo('password')]
    
    if form.validate_on_submit():
        # Check if new employee ID conflicts with another employee
        if form.employee_id.data:
            existing_employee = mongo.db.employees.find_one({
                'employee_id': form.employee_id.data,
                '_id': {'$ne': ObjectId(employee_id)}
            })
            if existing_employee:
                flash('Employee ID already exists!', 'danger')
                return render_template('employees.html', form=form, edit_mode=True, employee_id=employee_id)
        
        # Check if email change conflicts with existing user
        if form.email.data != employee['email']:
            existing_user = mongo.db.users.find_one({'username': form.email.data})
            if existing_user:
                flash('New email already exists as a user!', 'danger')
                return render_template('employees.html', form=form, edit_mode=True, employee_id=employee_id)
        
        # Update employee record
        mongo.db.employees.update_one(
            {'_id': ObjectId(employee_id)},
            {'$set': {
                'employee_id': form.employee_id.data,
                'name': form.name.data,
                'email': form.email.data,
                'department': form.department.data,
                'phone': form.phone.data
            }}
        )
        
        # Update user account if email changed or password provided
        update_data = {}
        if form.email.data != employee['email']:
            update_data['username'] = form.email.data
            update_data['email'] = form.email.data
        if form.name.data != employee['name']:
            update_data['full_name'] = form.name.data
        if form.password.data:
            update_data['password_hash'] = User(form.email.data, form.email.data, form.password.data, form.name.data).password_hash
        
        if update_data:
            mongo.db.users.update_one(
                {'username': employee['email']},
                {'$set': update_data}
            )
        
        flash('Employee updated successfully!', 'success')
        return redirect(url_for('employees'))
    
    return render_template('employees.html', form=form, edit_mode=True, employee_id=employee_id)


@app.route('/employees/delete/<employee_id>', methods=['POST'])
@login_required
def delete_employee(employee_id):
    user_role = session.get('role', 'employee')
    if user_role != 'admin':
        flash('Access denied! Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    employee = mongo.db.employees.find_one({'_id': ObjectId(employee_id)})
    if not employee:
        flash('Employee not found!', 'danger')
        return redirect(url_for('employees'))
    
    # Check if employee has active assignments
    active_assignments = mongo.db.assignments.count_documents({
        'employee_id': employee_id,
        'status': 'Active'
    })
    
    if active_assignments > 0:
        flash('Cannot delete employee with active asset assignments!', 'danger')
    else:
        # Delete the user account first
        mongo.db.users.delete_one({'username': employee['email']})
        
        # Then delete the employee record
        mongo.db.employees.update_one(
            {'_id': ObjectId(employee_id)},
            {'$set': {'is_active': False}}
        )
        flash('Employee and login credentials deleted successfully!', 'success')
    
    return redirect(url_for('employees'))


# ==================== ASSET ROUTES ====================

@app.route('/assets')
@login_required
def assets():
    user_role = session.get('role', 'employee')
    if user_role != 'admin':
        flash('Access denied! Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    search_query = request.args.get('search', '')
    asset_type_filter = request.args.get('asset_type', '')
    status_filter = request.args.get('status', '')
    
    query = {}
    if search_query:
        query['$or'] = [
            {'brand': {'$regex': search_query, '$options': 'i'}},
            {'model': {'$regex': search_query, '$options': 'i'}},
            {'serial_number': {'$regex': search_query, '$options': 'i'}}
        ]
    if asset_type_filter:
        query['asset_type'] = asset_type_filter
    if status_filter:
        query['status'] = status_filter
    
    assets_list = list(mongo.db.assets.find(query).sort('created_at', -1))
    
    return render_template('assets.html', assets=assets_list,
                         search_query=search_query,
                         asset_type_filter=asset_type_filter,
                         status_filter=status_filter)


@app.route('/assets/add', methods=['GET', 'POST'])
@login_required
def add_asset():
    user_role = session.get('role', 'employee')
    if user_role != 'admin':
        flash('Access denied! Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    form = AssetForm()
    if form.validate_on_submit():
        # Check if serial number already exists
        existing = mongo.db.assets.find_one({'serial_number': form.serial_number.data})
        if existing:
            flash('Serial number already exists!', 'danger')
            return render_template('assets.html', form=form, edit_mode=False)
        
        asset = Asset(
            asset_type=form.asset_type.data,
            brand=form.brand.data,
            model=form.model.data,
            serial_number=form.serial_number.data,
            condition=form.condition.data,
            description=form.description.data
        )
        
        mongo.db.assets.insert_one(asset.to_dict())
        flash('Asset added successfully!', 'success')
        return redirect(url_for('assets'))
    
    return render_template('assets.html', form=form, edit_mode=False)


@app.route('/assets/edit/<asset_id>', methods=['GET', 'POST'])
@login_required
def edit_asset(asset_id):
    user_role = session.get('role', 'employee')
    if user_role != 'admin':
        flash('Access denied! Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    asset = mongo.db.assets.find_one({'_id': ObjectId(asset_id)})
    if not asset:
        flash('Asset not found!', 'danger')
        return redirect(url_for('assets'))
    
    form = AssetForm(data=asset)
    
    if form.validate_on_submit():
        # Check if new serial number conflicts with another asset
        existing = mongo.db.assets.find_one({
            'serial_number': form.serial_number.data,
            '_id': {'$ne': ObjectId(asset_id)}
        })
        if existing:
            flash('Serial number already exists!', 'danger')
            return render_template('assets.html', form=form, edit_mode=True, asset_id=asset_id)
        
        mongo.db.assets.update_one(
            {'_id': ObjectId(asset_id)},
            {'$set': {
                'asset_type': form.asset_type.data,
                'brand': form.brand.data,
                'model': form.model.data,
                'serial_number': form.serial_number.data,
                'condition': form.condition.data,
                'description': form.description.data
            }}
        )
        flash('Asset updated successfully!', 'success')
        return redirect(url_for('assets'))
    
    return render_template('assets.html', form=form, edit_mode=True, asset_id=asset_id)


@app.route('/assets/delete/<asset_id>', methods=['POST'])
@login_required
def delete_asset(asset_id):
    user_role = session.get('role', 'employee')
    if user_role != 'admin':
        flash('Access denied! Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    asset = mongo.db.assets.find_one({'_id': ObjectId(asset_id)})
    
    if asset and asset['status'] == 'Assigned':
        flash('Cannot delete an assigned asset!', 'danger')
    else:
        mongo.db.assets.delete_one({'_id': ObjectId(asset_id)})
        flash('Asset deleted successfully!', 'success')
    
    return redirect(url_for('assets'))


@app.route('/request-asset', methods=['POST'])
@login_required
def request_asset():
    user_role = session.get('role', 'employee')
    if user_role != 'employee':
        flash('Only employees can request assets!', 'danger')
        return redirect(url_for('dashboard'))
    
    # Get current employee
    employee = mongo.db.employees.find_one({'email': session.get('username')})
    if not employee:
        flash('Employee profile not found!', 'danger')
        return redirect(url_for('dashboard'))
    
    asset_id = request.form.get('asset_id')
    expected_return_date = request.form.get('expected_return_date')
    notes = request.form.get('notes')
    
    if not asset_id:
        flash('Asset ID is required!', 'danger')
        return redirect(url_for('dashboard'))
    
    # Check if asset exists
    asset = mongo.db.assets.find_one({'_id': ObjectId(asset_id)})
    if not asset:
        flash('Asset not found!', 'danger')
        return redirect(url_for('dashboard'))
    
    # Check if employee already has a pending request for this asset
    existing_request = mongo.db.assignments.find_one({
        'employee_id': str(employee['_id']),
        'asset_id': asset_id,
        'approval_status': 'Pending'
    })
    
    if existing_request:
        flash('You already have a pending request for this asset!', 'warning')
        return redirect(url_for('dashboard'))
    
    # Create assignment request
    assignment = Assignment(
        employee_id=str(employee['_id']),
        asset_id=asset_id,
        assigned_by=session['username']
    )
    
    assignment_dict = assignment.to_dict()
    if expected_return_date:
        # Convert date string to datetime object for MongoDB
        assignment_dict['expected_return_date'] = datetime.strptime(expected_return_date, '%Y-%m-%d')
    if notes:
        assignment_dict['notes'] = notes
    
    mongo.db.assignments.insert_one(assignment_dict)
    
    flash('Asset request submitted successfully! It will be reviewed by an administrator.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/search-assets')
@login_required
def search_assets():
    user_role = session.get('role', 'employee')
    if user_role != 'employee':
        flash('Access denied! This feature is for employees only.', 'danger')
        return redirect(url_for('dashboard'))
    
    search_query = request.args.get('query', '').strip()
    
    if not search_query:
        flash('Please enter a search term.', 'warning')
        return redirect(url_for('dashboard'))
    
    # Search for assets that match the query
    query = {
        '$or': [
            {'brand': {'$regex': search_query, '$options': 'i'}},
            {'model': {'$regex': search_query, '$options': 'i'}},
            {'serial_number': {'$regex': search_query, '$options': 'i'}},
            {'asset_type': {'$regex': search_query, '$options': 'i'}}
        ]
    }
    
    assets_list = list(mongo.db.assets.find(query).sort('asset_type', 1))
    
    # Get current employee to check for existing requests
    employee = mongo.db.employees.find_one({'email': session.get('username')})
    employee_id = str(employee['_id']) if employee else None
    
    # Mark assets that employee already has pending requests for
    if employee_id:
        for asset in assets_list:
            existing_request = mongo.db.assignments.find_one({
                'employee_id': employee_id,
                'asset_id': str(asset['_id']),
                'approval_status': 'Pending'
            })
            asset['has_pending_request'] = bool(existing_request)
    
    return render_template('search_assets.html', 
                         assets=assets_list, 
                         search_query=search_query,
                         employee=employee)

@app.route('/assignments')
@login_required
def assignments():
    user_role = session.get('role', 'employee')
    if user_role != 'admin':
        flash('Access denied! Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    status_filter = request.args.get('status', 'Active')
    
    query = {}
    if status_filter == 'Active':
        query = {'status': 'Active', 'approval_status': 'Approved'}
    elif status_filter == 'Pending':
        query = {'approval_status': 'Pending'}
    elif status_filter == 'Returned':
        query = {'status': 'Returned'}
    elif status_filter == 'Rejected':
        query = {'approval_status': 'Rejected'}
    
    assignments_list = list(mongo.db.assignments.find(query).sort('assigned_date', -1))
    
    # Enrich with employee and asset details
    for assignment in assignments_list:
        employee = mongo.db.employees.find_one({'_id': ObjectId(assignment['employee_id'])})
        asset = mongo.db.assets.find_one({'_id': ObjectId(assignment['asset_id'])})
        assignment['employee'] = employee
        assignment['asset'] = asset
    
    # Create form for the add modal
    form = AssignmentForm()
    
    # Populate employee choices
    employees_list = list(mongo.db.employees.find({'is_active': True}).sort('name', 1))
    form.employee_id.choices = [(str(emp['_id']), f"{emp['employee_id']} - {emp['name']}") for emp in employees_list]
    
    # Populate asset choices (only available assets)
    assets_list = list(mongo.db.assets.find({'status': 'Available'}).sort('asset_type', 1))
    form.asset_id.choices = [(str(asset['_id']), f"{asset['asset_type']} - {asset['brand']} {asset['model']} ({asset['serial_number']})") for asset in assets_list]
    
    return render_template('assignments.html', assignments=assignments_list, status_filter=status_filter, form=form)


@app.route('/assignments/add', methods=['GET', 'POST'])
@login_required
def add_assignment():
    user_role = session.get('role', 'employee')
    if user_role != 'admin':
        flash('Access denied! Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    form = AssignmentForm()
    
    # Populate employee choices
    employees_list = list(mongo.db.employees.find({'is_active': True}).sort('name', 1))
    form.employee_id.choices = [(str(emp['_id']), f"{emp['employee_id']} - {emp['name']}") for emp in employees_list]
    
    # Populate asset choices (only available assets)
    assets_list = list(mongo.db.assets.find({'status': 'Available'}).sort('asset_type', 1))
    form.asset_id.choices = [(str(asset['_id']), f"{asset['asset_type']} - {asset['brand']} {asset['model']} ({asset['serial_number']})") for asset in assets_list]
    
    if form.validate_on_submit():
        assignment = Assignment(
            employee_id=form.employee_id.data,
            asset_id=form.asset_id.data,
            assigned_by=session['username']
        )
        
        assignment_dict = assignment.to_dict()
        # Admin assignments are automatically approved
        assignment_dict['approval_status'] = 'Approved'
        assignment_dict['status'] = 'Active'
        assignment_dict['approved_date'] = datetime.utcnow()
        assignment_dict['approved_by'] = session['username']
        
        if form.expected_return_date.data:
            assignment_dict['expected_return_date'] = datetime.combine(form.expected_return_date.data, datetime.min.time())
        if form.notes.data:
            assignment_dict['notes'] = form.notes.data
        
        mongo.db.assignments.insert_one(assignment_dict)
        
        # Update asset status to Assigned
        mongo.db.assets.update_one(
            {'_id': ObjectId(form.asset_id.data)},
            {'$set': {'status': 'Assigned'}}
        )
        
        flash('Asset assigned successfully!', 'success')
        return redirect(url_for('assignments'))
    
    return render_template('assignments.html', form=form, add_mode=True)


@app.route('/assignments/admin-approve/<assignment_id>', methods=['POST'])
@login_required
def admin_approve_assignment(assignment_id):
    user_role = session.get('role', 'employee')
    if user_role != 'admin':
        return jsonify({'success': False, 'message': 'Admin privileges required!'}), 403
    
    assignment = mongo.db.assignments.find_one({'_id': ObjectId(assignment_id)})
    if not assignment:
        return jsonify({'success': False, 'message': 'Assignment not found!'}), 404
    
    data = request.get_json()
    action = data.get('action')
    
    if action == 'approve':
        # Check if asset is currently assigned to someone else
        asset = mongo.db.assets.find_one({'_id': ObjectId(assignment['asset_id'])})
        
        if asset['status'] == 'Assigned':
            # Find the current active assignment for this asset
            current_assignment = mongo.db.assignments.find_one({
                'asset_id': assignment['asset_id'],
                'status': 'Active',
                'approval_status': 'Approved'
            })
            
            if current_assignment:
                # Get the new employee's details for the note
                new_employee = mongo.db.employees.find_one({'_id': ObjectId(assignment['employee_id'])})
                new_employee_id = new_employee['employee_id'] if new_employee else assignment['employee_id']
                
                # Mark the current assignment as returned due to reassignment
                mongo.db.assignments.update_one(
                    {'_id': current_assignment['_id']},
                    {'$set': {
                        'status': 'Returned',
                        'actual_return_date': datetime.utcnow(),
                        'return_condition': asset.get('condition', 'Unknown'),
                        'notes': f'Automatically returned due to reassignment to employee {new_employee_id}'
                    }}
                )
        
        # Update assignment to approved
        mongo.db.assignments.update_one(
            {'_id': ObjectId(assignment_id)},
            {'$set': {
                'approval_status': 'Approved',
                'status': 'Active',
                'approved_date': datetime.utcnow(),
                'approved_by': session['username']
            }}
        )
        
        # Update asset status to Assigned
        mongo.db.assets.update_one(
            {'_id': ObjectId(assignment['asset_id'])},
            {'$set': {'status': 'Assigned'}}
        )
        
        flash('Assignment approved successfully!', 'success')
        return jsonify({'success': True, 'message': 'Assignment approved successfully!'})
    
    elif action == 'reject':
        rejection_reason = data.get('rejection_reason', 'No reason provided')
        
        # Update assignment to rejected
        mongo.db.assignments.update_one(
            {'_id': ObjectId(assignment_id)},
            {'$set': {
                'approval_status': 'Rejected',
                'status': 'Rejected',
                'rejected_date': datetime.utcnow(),
                'rejection_reason': rejection_reason,
                'rejected_by': session['username']
            }}
        )
        
        # Make asset available again
        mongo.db.assets.update_one(
            {'_id': ObjectId(assignment['asset_id'])},
            {'$set': {'status': 'Available'}}
        )
        
        flash('Assignment rejected!', 'warning')
        return jsonify({'success': True, 'message': 'Assignment rejected!'})
    
    return jsonify({'success': False, 'message': 'Invalid action!'}), 400


@app.route('/assignments/approve/<assignment_id>', methods=['GET', 'POST'])
@login_required
def approve_assignment(assignment_id):
    assignment = mongo.db.assignments.find_one({'_id': ObjectId(assignment_id)})
    if not assignment:
        flash('Assignment not found!', 'danger')
        return redirect(url_for('assignments'))
    
    # Check if current user is the assigned employee
    employee = mongo.db.employees.find_one({'_id': ObjectId(assignment['employee_id'])})
    if not employee or employee.get('email') != session.get('username'):
        flash('You can only approve assignments for yourself!', 'danger')
        return redirect(url_for('dashboard'))
    
    # Enrich assignment with employee and asset details
    asset = mongo.db.assets.find_one({'_id': ObjectId(assignment['asset_id'])})
    assignment['employee'] = employee
    assignment['asset'] = asset
    
    form = ApprovalForm()
    if form.validate_on_submit():
        if form.action.data == 'approve':
            mongo.db.assignments.update_one(
                {'_id': ObjectId(assignment_id)},
                {'$set': {
                    'approval_status': 'Approved',
                    'status': 'Active',
                    'approved_date': datetime.utcnow()
                }}
            )
            flash('Assignment approved successfully!', 'success')
        else:
            mongo.db.assignments.update_one(
                {'_id': ObjectId(assignment_id)},
                {'$set': {
                    'approval_status': 'Rejected',
                    'status': 'Rejected',
                    'rejected_date': datetime.utcnow(),
                    'rejection_reason': form.rejection_reason.data
                }}
            )
            # Make asset available again
            mongo.db.assets.update_one(
                {'_id': ObjectId(assignment['asset_id'])},
                {'$set': {'status': 'Available'}}
            )
            flash('Assignment rejected!', 'warning')
        
        return redirect(url_for('dashboard'))
    
    return render_template('approve_assignment.html', assignment=assignment, form=form)


@app.route('/assignments/return/<assignment_id>', methods=['GET', 'POST'])
@login_required
def return_assignment(assignment_id):
    assignment = mongo.db.assignments.find_one({'_id': ObjectId(assignment_id)})
    if not assignment:
        flash('Assignment not found!', 'danger')
        return redirect(url_for('assignments'))
    
    # Check if current user is admin or the assigned employee
    is_admin = True  # For now, assume all logged-in users can return (admin functionality)
    employee = mongo.db.employees.find_one({'_id': ObjectId(assignment['employee_id'])})
    is_employee = employee and employee.get('email') == session.get('username')
    
    if not is_admin and not is_employee:
        flash('You can only return your own assignments!', 'danger')
        return redirect(url_for('dashboard'))
    
    # Enrich assignment with employee and asset details
    employee = mongo.db.employees.find_one({'_id': ObjectId(assignment['employee_id'])})
    asset = mongo.db.assets.find_one({'_id': ObjectId(assignment['asset_id'])})
    assignment['employee'] = employee
    assignment['asset'] = asset
    
    form = ReturnForm()
    if form.validate_on_submit():
        return_condition = form.return_condition.data
        notes = form.notes.data
        
        # Update assignment
        mongo.db.assignments.update_one(
            {'_id': ObjectId(assignment_id)},
            {'$set': {
                'status': 'Returned',
                'actual_return_date': datetime.utcnow(),
                'return_condition': return_condition,
                'notes': notes
            }}
        )
        
        # Update asset status and condition
        mongo.db.assets.update_one(
            {'_id': ObjectId(assignment['asset_id'])},
            {'$set': {
                'status': 'Available',
                'condition': return_condition
            }}
        )
        
        flash('Asset returned successfully!', 'success')
        if is_employee:
            return redirect(url_for('dashboard'))
        else:
            return redirect(url_for('assignments'))
    
    return render_template('return_asset.html', assignment=assignment, form=form)


# ==================== REPORTS ROUTES ====================

@app.route('/reports')
@login_required
def reports():
    user_role = session.get('role', 'employee')
    if user_role != 'admin':
        flash('Access denied! Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Asset distribution by type
    asset_stats = get_asset_stats(mongo)
    
    # Department distribution
    department_stats = get_department_stats(mongo)
    
    # Assignment history
    total_assignments = mongo.db.assignments.count_documents({})
    active_assignments = mongo.db.assignments.count_documents({'status': 'Active'})
    returned_assignments = mongo.db.assignments.count_documents({'status': 'Returned'})
    
    # Top employees by asset count
    pipeline = [
        {'$match': {'status': 'Active'}},
        {'$group': {'_id': '$employee_id', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}},
        {'$limit': 10}
    ]
    top_employees_data = list(mongo.db.assignments.aggregate(pipeline))
    
    # Enrich with employee names
    top_employees = []
    for item in top_employees_data:
        employee = mongo.db.employees.find_one({'_id': ObjectId(item['_id'])})
        if employee:
            top_employees.append({
                'name': employee['name'],
                'employee_id': employee['employee_id'],
                'department': employee['department'],
                'count': item['count']
            })
    
    return render_template('reports.html',
                         asset_stats=asset_stats,
                         department_stats=department_stats,
                         total_assignments=total_assignments,
                         active_assignments=active_assignments,
                         returned_assignments=returned_assignments,
                         top_employees=top_employees)


# ==================== API ROUTES FOR CHARTS ====================

@app.route('/api/asset-distribution')
@login_required
def api_asset_distribution():
    asset_stats = get_asset_stats(mongo)
    return jsonify(asset_stats)


@app.route('/api/department-distribution')
@login_required
def api_department_distribution():
    department_stats = get_department_stats(mongo)
    return jsonify(department_stats)


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500


if __name__ == '__main__':
    create_admin_account()
    # Use threaded=False for Windows compatibility
    app.run(debug=True, host='127.0.0.1', port=5000, threaded=False)