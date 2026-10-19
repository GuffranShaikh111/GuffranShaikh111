from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, TextAreaField, DateField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])

class EmployeeForm(FlaskForm):
    employee_id = StringField('Employee ID', validators=[Optional(), Length(max=20)])
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    department = SelectField('Department', choices=[
        ('IT', 'IT'),
        ('HR', 'Human Resources'),
        ('Marketing', 'Marketing'),
        ('Finance', 'Finance'),
        ('Operations', 'Operations'),
        ('Sales', 'Sales'),
        ('Engineering', 'Engineering'),
        ('Administration', 'Administration')
    ], validators=[DataRequired()])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])

class AssetForm(FlaskForm):
    asset_type = SelectField('Asset Type', choices=[
        ('Laptop', 'Laptop'),
        ('Desktop', 'Desktop'),
        ('Mobile Phone', 'Mobile Phone'),
        ('Tablet', 'Tablet'),
        ('Monitor', 'Monitor'),
        ('Keyboard', 'Keyboard'),
        ('Mouse', 'Mouse'),
        ('Headset', 'Headset'),
        ('ID Card', 'ID Card'),
        ('Access Card', 'Access Card'),
        ('Other', 'Other')
    ], validators=[DataRequired()])
    brand = StringField('Brand', validators=[DataRequired(), Length(max=50)])
    model = StringField('Model', validators=[DataRequired(), Length(max=100)])
    serial_number = StringField('Serial Number', validators=[DataRequired(), Length(max=100)])
    condition = SelectField('Condition', choices=[
        ('New', 'New'),
        ('Good', 'Good'),
        ('Fair', 'Fair'),
        ('Poor', 'Poor'),
        ('Damaged', 'Damaged')
    ], validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional()])

class AssignmentForm(FlaskForm):
    employee_id = SelectField('Employee', coerce=str, validators=[DataRequired()])
    asset_id = SelectField('Asset', coerce=str, validators=[DataRequired()])
    expected_return_date = DateField('Expected Return Date', format='%Y-%m-%d', validators=[Optional()])
    notes = TextAreaField('Notes', validators=[Optional()])

class ApprovalForm(FlaskForm):
    action = SelectField('Action', choices=[('approve', 'Approve'), ('reject', 'Reject')], validators=[DataRequired()])
    rejection_reason = TextAreaField('Rejection Reason', validators=[Optional()])

class ReturnForm(FlaskForm):
    return_condition = SelectField('Return Condition', choices=[
        ('Good', 'Good'),
        ('Fair', 'Fair'),
        ('Poor', 'Poor'),
        ('Damaged', 'Damaged')
    ], validators=[DataRequired()])
    notes = TextAreaField('Notes', validators=[Optional()])