from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId

class User:
    def __init__(self, username, email, password, full_name, role='employee'):
        self.username = username
        self.email = email
        self.password_hash = generate_password_hash(password)
        self.full_name = full_name
        self.role = role  # 'admin' or 'employee'
        self.created_at = datetime.utcnow()
        self.is_active = True

    def to_dict(self):
        return {
            'username': self.username,
            'email': self.email,
            'password_hash': self.password_hash,
            'full_name': self.full_name,
            'role': self.role,
            'created_at': self.created_at,
            'is_active': self.is_active
        }

    @staticmethod
    def verify_password(password_hash, password):
        return check_password_hash(password_hash, password)


class Employee:
    def __init__(self, employee_id, name, email, department, phone=None):
        self.employee_id = employee_id
        self.name = name
        self.email = email
        self.department = department
        self.phone = phone
        self.created_at = datetime.utcnow()
        self.is_active = True

    def to_dict(self):
        return {
            'employee_id': self.employee_id,
            'name': self.name,
            'email': self.email,
            'department': self.department,
            'phone': self.phone,
            'created_at': self.created_at,
            'is_active': self.is_active
        }


class Asset:
    def __init__(self, asset_type, brand, model, serial_number, condition='New', description=None):
        self.asset_type = asset_type
        self.brand = brand
        self.model = model
        self.serial_number = serial_number
        self.condition = condition
        self.description = description
        self.status = 'Available'
        self.created_at = datetime.utcnow()

    def to_dict(self):
        return {
            'asset_type': self.asset_type,
            'brand': self.brand,
            'model': self.model,
            'serial_number': self.serial_number,
            'condition': self.condition,
            'description': self.description,
            'status': self.status,
            'created_at': self.created_at
        }


class Assignment:
    def __init__(self, employee_id, asset_id, assigned_by):
        self.employee_id = employee_id
        self.asset_id = asset_id
        self.assigned_by = assigned_by
        self.assigned_date = datetime.utcnow()
        self.expected_return_date = None
        self.actual_return_date = None
        self.return_condition = None
        self.status = 'Pending Approval'  # Changed from 'Active' to require approval
        self.approval_status = 'Pending'  # New field: Pending, Approved, Rejected
        self.approved_date = None
        self.rejected_date = None
        self.rejection_reason = None
        self.notes = None

    def to_dict(self):
        return {
            'employee_id': self.employee_id,
            'asset_id': self.asset_id,
            'assigned_by': self.assigned_by,
            'assigned_date': self.assigned_date,
            'expected_return_date': self.expected_return_date,
            'actual_return_date': self.actual_return_date,
            'return_condition': self.return_condition,
            'status': self.status,
            'approval_status': self.approval_status,
            'approved_date': self.approved_date,
            'rejected_date': self.rejected_date,
            'rejection_reason': self.rejection_reason,
            'notes': self.notes
        }