"""WTForms for the E-Recruitment system."""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import (StringField, PasswordField, TextAreaField, SelectField, 
                     DateField, TimeField, BooleanField, IntegerField, 
                     SubmitField, HiddenField, SelectMultipleField)
from wtforms.validators import (DataRequired, Email, Length, EqualTo, 
                                 ValidationError, Optional, Regexp)
from app.models import User

# ============== System Settings Form ==============
class SystemSettingsForm(FlaskForm):
    system_name = StringField('System Name', validators=[DataRequired(), Length(max=200)])
    theme = SelectField('Color Theme', choices=[
        ('default', 'Default'),
        ('dark', 'Dark'),
        ('light', 'Light'),
        ('blue', 'Blue'),
        ('green', 'Green'),
        ('red', 'Red'),
        ('purple', 'Purple'),
        ('orange', 'Orange'),
        ('yellow', 'Yellow'),
        ('teal', 'Teal'),
        ('indigo', 'Indigo'),
        ('pink', 'Pink'),
        ('gray', 'Gray'),
    ], validators=[DataRequired()])
    logo = FileField('Logo', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')])
    submit = SubmitField('Update Settings')


# ============== Authentication Forms ==============

class LoginForm(FlaskForm):
    """User login form."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class ForgotPasswordForm(FlaskForm):
    """Forgot password form."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Send Reset Link')


class ResetPasswordForm(FlaskForm):
    """Reset password form."""
    password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters')
    ])
    password2 = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Reset Password')


class RegistrationForm(FlaskForm):
    """User registration form for applicants."""
    username = StringField('Username', validators=[
        DataRequired(), 
        Length(min=3, max=64),
        Regexp('^[A-Za-z][A-Za-z0-9_.]*$', 0, 
               'Username must start with a letter and contain only letters, numbers, dots or underscores')
    ])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=64)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=64)])
    id_number = StringField('ID Number', validators=[
        Optional(),
        Length(min=13, max=13, message='SA ID number must be 13 digits'),
        Regexp('^[0-9]*$', 0, 'ID number must contain only digits')
    ])
    phone = StringField('Phone Number', validators=[Optional(), Length(max=20)])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters')
    ])
    password2 = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already taken. Please choose a different one.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different email.')
    
    def validate_id_number(self, id_number):
        if id_number.data:
            user = User.query.filter_by(id_number=id_number.data).first()
            if user:
                raise ValidationError('ID number already registered.')


class ProfileForm(FlaskForm):
    """User profile update form."""
    profile_picture = FileField('Profile Picture', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Only image files allowed (JPG, PNG, GIF)')
    ])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=64)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=64)])
    phone = StringField('Phone Number', validators=[Optional(), Length(max=20)])
    gender = SelectField('Gender', choices=[
        ('', '-- Select --'),
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say')
    ], validators=[Optional()])
    race = SelectField('Race (for EE reporting)', choices=[
        ('', '-- Select --'),
        ('african', 'African'),
        ('coloured', 'Coloured'),
        ('indian', 'Indian'),
        ('white', 'White'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say')
    ], validators=[Optional()])
    disability_status = BooleanField('Person with Disability')
    submit = SubmitField('Update Profile')


class ChangePasswordForm(FlaskForm):
    """Password change form."""
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match')
    ])
    submit = SubmitField('Change Password')


# ============== Job Posting Forms ==============

class JobPostingForm(FlaskForm):
    """Form for creating/editing job postings."""
    title = StringField('Job Title', validators=[DataRequired(), Length(max=200)])
    department = StringField('Department', validators=[DataRequired(), Length(max=100)])
    location = StringField('Location', validators=[DataRequired(), Length(max=200)])
    job_purpose = TextAreaField('Job Purpose', validators=[DataRequired()])
    responsibilities = TextAreaField('Key Responsibilities', validators=[DataRequired()])
    
    # Requirements (will be stored as JSON)
    min_education = SelectField('Minimum Education', choices=[
        ('matric', 'Matric / Grade 12'),
        ('certificate', 'Certificate'),
        ('diploma', 'Diploma'),
        ('degree', 'Bachelor\'s Degree'),
        ('honours', 'Honours Degree'),
        ('masters', 'Master\'s Degree'),
        ('doctorate', 'Doctorate')
    ], validators=[DataRequired()])
    min_experience_years = IntegerField('Minimum Years Experience', validators=[DataRequired()])
    required_skills = TextAreaField('Required Skills (one per line)', validators=[DataRequired()])
    preferred_skills = TextAreaField('Preferred Skills (one per line)', validators=[Optional()])
    
    salary_range = StringField('Salary Range', validators=[Optional(), Length(max=100)])
    closing_date = DateField('Closing Date', validators=[DataRequired()])
    ee_target_category = StringField('EE Target Category', validators=[Optional(), Length(max=100)])
    
    status = SelectField('Status', choices=[
        ('draft', 'Draft'),
        ('pending_approval', 'Submit for Approval'),
        ('published', 'Publish')
    ], validators=[DataRequired()])
    
    submit = SubmitField('Save Job Posting')


class JobSearchForm(FlaskForm):
    """Job search form."""
    keyword = StringField('Keyword', validators=[Optional()])
    department = SelectField('Department', choices=[('', 'All Departments')], validators=[Optional()])
    location = SelectField('Location', choices=[('', 'All Locations')], validators=[Optional()])
    submit = SubmitField('Search')


# ============== Application Forms ==============

class ApplicationForm(FlaskForm):
    """Job application form."""
    cover_letter = TextAreaField('Cover Letter', validators=[Optional(), Length(max=5000)])
    cv_file = FileField('Upload CV (PDF, DOC, DOCX)', validators=[
        FileRequired(),
        FileAllowed(['pdf', 'doc', 'docx'], 'Only PDF and Word documents allowed')
    ])
    id_document = FileField('Upload ID Document (PDF, JPG, PNG)', validators=[
        Optional(),
        FileAllowed(['pdf', 'jpg', 'jpeg', 'png'], 'Only PDF and image files allowed')
    ])
    qualifications = FileField('Upload Qualifications (PDF)', validators=[
        Optional(),
        FileAllowed(['pdf'], 'Only PDF files allowed')
    ])
    
    # Declaration
    confirm_accuracy = BooleanField('I confirm that all information provided is accurate', 
                                    validators=[DataRequired()])
    submit = SubmitField('Submit Application')


class ApplicationStatusForm(FlaskForm):
    """Form for updating application status (HR use)."""
    status = SelectField('Status', choices=[
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('shortlisted', 'Shortlisted'),
        ('interviewed', 'Interviewed'),
        ('offered', 'Offered'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn')
    ], validators=[DataRequired()])
    current_stage = StringField('Current Stage', validators=[Optional(), Length(max=100)])
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Update Status')


class ScreeningForm(FlaskForm):
    """Application screening form."""
    screening_score = IntegerField('Screening Score (0-100)', validators=[Optional()])
    notes = TextAreaField('Screening Notes', validators=[Optional()])
    shortlist = BooleanField('Add to Shortlist')
    submit = SubmitField('Save Screening')


# ============== Interview Forms ==============

class InterviewScheduleForm(FlaskForm):
    """Interview scheduling form."""
    scheduled_date = DateField('Interview Date', validators=[DataRequired()])
    start_time = TimeField('Start Time', validators=[DataRequired()])
    end_time = TimeField('End Time', validators=[DataRequired()])
    interview_type = SelectField('Interview Type', choices=[
        ('in_person', 'In Person'),
        ('video', 'Video Conference'),
        ('phone', 'Phone Interview')
    ], validators=[DataRequired()])
    location = StringField('Location / Meeting Link', validators=[DataRequired(), Length(max=500)])
    panel_members = SelectMultipleField('Panel Members', coerce=int, validators=[Optional()])
    submit = SubmitField('Schedule Interview')


class InterviewFeedbackForm(FlaskForm):
    """Interview feedback form."""
    score = IntegerField('Interview Score (0-100)', validators=[Optional()])
    feedback = TextAreaField('Feedback', validators=[DataRequired()])
    status = SelectField('Interview Status', choices=[
        ('completed', 'Completed'),
        ('no_show', 'Candidate No Show'),
        ('cancelled', 'Cancelled')
    ], validators=[DataRequired()])
    submit = SubmitField('Submit Feedback')


# ============== Offer Forms ==============

class OfferForm(FlaskForm):
    """Job offer form."""
    salary_offered = StringField('Salary Offered', validators=[DataRequired(), Length(max=100)])
    start_date_proposed = DateField('Proposed Start Date', validators=[DataRequired()])
    response_deadline = DateField('Response Deadline', validators=[DataRequired()])
    terms = TextAreaField('Terms and Conditions', validators=[Optional()])
    submit = SubmitField('Create Offer')


class OfferResponseForm(FlaskForm):
    """Offer response form (for applicant)."""
    response = SelectField('Your Response', choices=[
        ('accepted', 'Accept Offer'),
        ('declined', 'Decline Offer')
    ], validators=[DataRequired()])
    submit = SubmitField('Submit Response')


# ============== Admin Forms ==============

class UserManagementForm(FlaskForm):
    """Admin user management form."""
    role = SelectField('Role', choices=[
        ('applicant', 'Applicant'),
        ('hr_officer', 'HR Officer'),
        ('manager', 'Hiring Manager'),
        ('admin', 'System Admin')
    ], validators=[DataRequired()])
    is_active = BooleanField('Account Active')
    submit = SubmitField('Update User')


class CreateStaffForm(FlaskForm):
    """Admin form for creating staff accounts (HR/Manager)."""
    username = StringField('Username', validators=[
        DataRequired(), 
        Length(min=3, max=64),
        Regexp('^[A-Za-z][A-Za-z0-9_.]*$', 0, 
               'Username must start with a letter and contain only letters, numbers, dots or underscores')
    ])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=64)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=64)])
    phone = StringField('Phone Number', validators=[Optional(), Length(max=20)])
    role = SelectField('Role', choices=[
        ('hr_officer', 'HR Officer'),
        ('manager', 'Hiring Manager'),
        ('admin', 'System Admin')
    ], validators=[DataRequired()])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters')
    ])
    password2 = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Create Staff Account')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already taken.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered.')


class ReportFilterForm(FlaskForm):
    """Report filtering form."""
    date_from = DateField('From Date', validators=[Optional()])
    date_to = DateField('To Date', validators=[Optional()])
    department = SelectField('Department', choices=[('', 'All Departments')], validators=[Optional()])
    status = SelectField('Status', choices=[('', 'All Statuses')], validators=[Optional()])
    submit = SubmitField('Generate Report')
