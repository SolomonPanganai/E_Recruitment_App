"""Database models for the E-Recruitment system."""
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db
# ==================== SYSTEM SETTINGS MODEL ====================
from datetime import datetime

class SystemSettings(db.Model):
    """Store system-wide settings like name and theme."""
    __tablename__ = 'system_settings'
    id = db.Column(db.Integer, primary_key=True)
    system_name = db.Column(db.String(200), nullable=False, default='E-Recruitment Portal')
    theme = db.Column(db.String(50), nullable=False, default='default')
    logo = db.Column(db.String(255), nullable=True)  # Filename of uploaded logo
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(UserMixin, db.Model):
    """User model for applicants, HR officers, managers, and admins."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.Enum('applicant', 'hr_officer', 'manager', 'admin', name='user_roles'), 
                     default='applicant', nullable=False)
    
    # Personal information
    id_number = db.Column(db.String(13), unique=True, nullable=True)  # SA ID
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    
    # Profile picture
    profile_picture = db.Column(db.String(255), nullable=True)  # Filename of uploaded picture
    
    # Employment Equity fields
    gender = db.Column(db.Enum('male', 'female', 'other', 'prefer_not_to_say', name='gender_types'), nullable=True)
    race = db.Column(db.Enum('african', 'coloured', 'indian', 'white', 'other', 'prefer_not_to_say', name='race_types'), nullable=True)
    disability_status = db.Column(db.Boolean, default=False)
    
    # Account status
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    applications = db.relationship('Application', backref='applicant', lazy='dynamic',
                                   foreign_keys='Application.applicant_id')
    created_jobs = db.relationship('JobPosting', backref='creator', lazy='dynamic',
                                   foreign_keys='JobPosting.created_by')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        """Hash and set password."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password."""
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        """Return full name."""
        return f"{self.first_name} {self.last_name}"
    
    def is_hr(self):
        """Check if user has HR privileges."""
        return self.role in ('hr_officer', 'manager', 'admin')
    
    def is_admin(self):
        """Check if user is admin."""
        return self.role == 'admin'
    
    def get_reset_password_token(self, expires_in=3600):
        """Generate a password reset token."""
        from itsdangerous import URLSafeTimedSerializer
        from flask import current_app
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps({'reset_password': self.id}, salt='password-reset-salt')
    
    @staticmethod
    def verify_reset_password_token(token, expires_in=3600):
        """Verify a password reset token and return the user."""
        from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
        from flask import current_app
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, salt='password-reset-salt', max_age=expires_in)
        except (SignatureExpired, BadSignature):
            return None
        return User.query.get(data.get('reset_password'))
    
    def __repr__(self):
        return f'<User {self.username}>'


class JobPosting(db.Model):
    """Job posting model."""
    __tablename__ = 'job_postings'
    
    id = db.Column(db.Integer, primary_key=True)
    job_reference = db.Column(db.String(50), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    
    # Job details
    job_purpose = db.Column(db.Text, nullable=False)
    responsibilities = db.Column(db.Text, nullable=False)
    minimum_requirements = db.Column(db.JSON, nullable=False)  # Structured requirements
    preferred_requirements = db.Column(db.JSON, nullable=True)
    salary_range = db.Column(db.String(100), nullable=True)
    
    # Dates and status
    posting_date = db.Column(db.DateTime, default=datetime.utcnow)
    closing_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.Enum('draft', 'pending_approval', 'published', 'closed', name='job_status'),
                       default='draft', nullable=False)
    
    # Employment Equity
    ee_target_category = db.Column(db.String(100), nullable=True)
    
    # SharePoint integration
    sharepoint_folder_path = db.Column(db.String(500), nullable=True)
    
    # Timestamps and audit
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Statistics
    views_count = db.Column(db.Integer, default=0)
    applications_count = db.Column(db.Integer, default=0)
    
    # Relationships
    applications = db.relationship('Application', backref='job', lazy='dynamic')
    documents = db.relationship('Document', backref='job_posting', lazy='dynamic',
                                foreign_keys='Document.job_posting_id')
    shortlists = db.relationship('Shortlist', backref='job', lazy='dynamic')
    
    approver = db.relationship('User', foreign_keys=[approved_by])
    
    @property
    def is_open(self):
        """Check if job is open for applications."""
        return self.status == 'published' and self.closing_date > datetime.utcnow()
    
    @property
    def days_until_closing(self):
        """Return days until closing date."""
        if self.closing_date:
            delta = self.closing_date - datetime.utcnow()
            return max(0, delta.days)
        return 0
    
    def __repr__(self):
        return f'<JobPosting {self.job_reference}: {self.title}>'


class Application(db.Model):
    """Job application model."""
    __tablename__ = 'applications'
    
    id = db.Column(db.Integer, primary_key=True)
    application_reference = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    # Foreign keys
    job_id = db.Column(db.Integer, db.ForeignKey('job_postings.id'), nullable=False)
    applicant_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Application details
    application_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.Enum('submitted', 'under_review', 'shortlisted', 'interviewed', 
                               'offered', 'rejected', 'withdrawn', name='application_status'),
                       default='submitted', nullable=False)
    current_stage = db.Column(db.String(100), default='Screening')
    
    # Scores
    screening_score = db.Column(db.Float, nullable=True)
    interview_score = db.Column(db.Float, nullable=True)
    
    # Notes
    notes = db.Column(db.Text, nullable=True)
    cover_letter = db.Column(db.Text, nullable=True)
    
    # SharePoint
    sharepoint_folder_path = db.Column(db.String(500), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    documents = db.relationship('Document', backref='application', lazy='dynamic',
                                foreign_keys='Document.application_id')
    shortlist = db.relationship('Shortlist', backref='application', uselist=False)
    interviews = db.relationship('Interview', backref='application', lazy='dynamic')
    offer = db.relationship('Offer', backref='application', uselist=False)
    
    def __repr__(self):
        return f'<Application {self.application_reference}>'


class Document(db.Model):
    """Document metadata model (files stored in SharePoint)."""
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign keys (nullable for flexibility)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=True)
    job_posting_id = db.Column(db.Integer, db.ForeignKey('job_postings.id'), nullable=True)
    
    # File information
    file_name = db.Column(db.String(255), nullable=False)
    sharepoint_url = db.Column(db.String(1000), nullable=True)
    local_path = db.Column(db.String(500), nullable=True)  # Fallback if SharePoint unavailable
    document_type = db.Column(db.Enum('cv', 'id', 'qualification', 'offer_letter', 
                                       'reference', 'other', name='document_types'),
                              nullable=False)
    
    # Metadata
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    file_size = db.Column(db.Integer, nullable=True)  # bytes
    mime_type = db.Column(db.String(100), nullable=True)
    
    uploader = db.relationship('User', foreign_keys=[uploaded_by])
    
    def __repr__(self):
        return f'<Document {self.file_name}>'


class Shortlist(db.Model):
    """Shortlist model for tracking shortlisted applications."""
    __tablename__ = 'shortlists'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign keys
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=False, unique=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job_postings.id'), nullable=False)
    shortlisted_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Details
    shortlisted_date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)
    ranking = db.Column(db.Integer, nullable=True)
    
    shortlister = db.relationship('User', foreign_keys=[shortlisted_by])
    
    def __repr__(self):
        return f'<Shortlist for Application {self.application_id}>'


class Interview(db.Model):
    """Interview model."""
    __tablename__ = 'interviews'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign key
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=False)
    
    # Schedule
    scheduled_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    location = db.Column(db.String(500), nullable=False)  # Physical address or meeting link
    interview_type = db.Column(db.Enum('in_person', 'video', 'phone', name='interview_types'),
                               default='in_person')
    
    # Panel
    panel = db.Column(db.JSON, nullable=True)  # Array of user IDs
    
    # Results
    feedback = db.Column(db.Text, nullable=True)
    score = db.Column(db.Float, nullable=True)
    status = db.Column(db.Enum('scheduled', 'completed', 'cancelled', 'no_show', name='interview_status'),
                       default='scheduled')
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Interview {self.id} for Application {self.application_id}>'


class Offer(db.Model):
    """Job offer model."""
    __tablename__ = 'offers'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign key
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=False, unique=True)
    
    # Offer details
    offer_date = db.Column(db.DateTime, default=datetime.utcnow)
    salary_offered = db.Column(db.String(100), nullable=False)
    start_date_proposed = db.Column(db.Date, nullable=False)
    terms = db.Column(db.Text, nullable=True)
    
    # Status
    status = db.Column(db.Enum('pending', 'accepted', 'declined', 'expired', name='offer_status'),
                       default='pending')
    response_deadline = db.Column(db.DateTime, nullable=True)
    accepted_date = db.Column(db.DateTime, nullable=True)
    
    # Document
    sharepoint_document_url = db.Column(db.String(1000), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Offer {self.id} for Application {self.application_id}>'


class AuditLog(db.Model):
    """Audit log for tracking all system actions."""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Who
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Nullable for system actions
    
    # What
    action = db.Column(db.String(100), nullable=False)  # e.g., CREATE_JOB, UPDATE_APPLICATION
    entity_type = db.Column(db.String(100), nullable=False)  # e.g., JobPosting, Application
    entity_id = db.Column(db.Integer, nullable=True)
    
    # Changes
    old_values = db.Column(db.JSON, nullable=True)
    new_values = db.Column(db.JSON, nullable=True)
    description = db.Column(db.Text, nullable=True)
    
    # Context
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 compatible
    user_agent = db.Column(db.String(500), nullable=True)
    
    # When
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f'<AuditLog {self.action} on {self.entity_type} {self.entity_id}>'


# Helper function for creating audit logs
def create_audit_log(user_id, action, entity_type, entity_id=None, 
                     old_values=None, new_values=None, description=None,
                     ip_address=None, user_agent=None):
    """Create an audit log entry."""
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_values=old_values,
        new_values=new_values,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.session.add(log)
    return log


class UserActivity(db.Model):
    """Track real-time user activity in the system."""
    __tablename__ = 'user_activities'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Activity details
    activity_type = db.Column(db.String(100), nullable=False)  # e.g., 'page_view', 'login', 'action'
    page = db.Column(db.String(200), nullable=True)  # URL or page name
    description = db.Column(db.String(500), nullable=True)
    
    # Context
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    
    # When
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationship
    user = db.relationship('User', backref=db.backref('activities', lazy='dynamic'))
    
    def __repr__(self):
        return f'<UserActivity {self.user_id} - {self.activity_type}>'


def log_user_activity(user_id, activity_type, page=None, description=None, 
                      ip_address=None, user_agent=None):
    """Log a user activity."""
    activity = UserActivity(
        user_id=user_id,
        activity_type=activity_type,
        page=page,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.session.add(activity)
    db.session.commit()
    return activity


# ==================== ASSESSMENT/TESTING MODULE ====================

class Assessment(db.Model):
    """Assessment/Test model for evaluating candidates."""
    __tablename__ = 'assessments'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign key - link to job posting
    job_id = db.Column(db.Integer, db.ForeignKey('job_postings.id'), nullable=False)
    
    # Assessment details
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    instructions = db.Column(db.Text, nullable=True)
    
    # Settings
    time_limit_minutes = db.Column(db.Integer, nullable=True)  # None = no time limit
    pass_score = db.Column(db.Float, default=50.0)  # Percentage needed to pass
    max_attempts = db.Column(db.Integer, default=1)
    shuffle_questions = db.Column(db.Boolean, default=False)
    show_results_immediately = db.Column(db.Boolean, default=True)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_mandatory = db.Column(db.Boolean, default=False)  # Must complete before shortlisting
    
    # Timestamps
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    job = db.relationship('JobPosting', backref=db.backref('assessments', lazy='dynamic'))
    questions = db.relationship('AssessmentQuestion', backref='assessment', lazy='dynamic',
                                cascade='all, delete-orphan')
    creator = db.relationship('User', foreign_keys=[created_by])
    candidate_assessments = db.relationship('CandidateAssessment', backref='assessment', lazy='dynamic')
    
    @property
    def total_questions(self):
        return self.questions.count()
    
    @property
    def total_points(self):
        return sum(q.points for q in self.questions)
    
    def __repr__(self):
        return f'<Assessment {self.title}>'


class AssessmentQuestion(db.Model):
    """Questions for assessments."""
    __tablename__ = 'assessment_questions'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign key
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessments.id'), nullable=False)
    
    # Question details
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.Enum('multiple_choice', 'true_false', 'text', 'multiple_select',
                                       name='question_types'), default='multiple_choice')
    
    # For ordering
    order = db.Column(db.Integer, default=0)
    
    # Scoring
    points = db.Column(db.Float, default=1.0)
    
    # For text questions - expected keywords or answer guide
    expected_answer = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    options = db.relationship('QuestionOption', backref='question', lazy='dynamic',
                              cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Question {self.id}: {self.question_text[:50]}>'


class QuestionOption(db.Model):
    """Options for multiple choice questions."""
    __tablename__ = 'question_options'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign key
    question_id = db.Column(db.Integer, db.ForeignKey('assessment_questions.id'), nullable=False)
    
    # Option details
    option_text = db.Column(db.String(500), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<Option {self.option_text[:30]}>'


class CandidateAssessment(db.Model):
    """Track candidate's assessment attempts."""
    __tablename__ = 'candidate_assessments'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign keys
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessments.id'), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=False)
    candidate_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Attempt tracking
    attempt_number = db.Column(db.Integer, default=1)
    
    # Timing
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Results
    score = db.Column(db.Float, nullable=True)  # Percentage score
    points_earned = db.Column(db.Float, nullable=True)
    total_points = db.Column(db.Float, nullable=True)
    passed = db.Column(db.Boolean, nullable=True)
    
    # Status
    status = db.Column(db.Enum('in_progress', 'completed', 'timed_out', 'abandoned',
                               name='assessment_status'), default='in_progress')
    
    # Relationships
    application = db.relationship('Application', backref=db.backref('candidate_assessments', lazy='dynamic'))
    candidate = db.relationship('User', foreign_keys=[candidate_id])
    answers = db.relationship('CandidateAnswer', backref='candidate_assessment', lazy='dynamic',
                              cascade='all, delete-orphan')
    
    @property
    def time_remaining(self):
        """Calculate remaining time in seconds."""
        if not self.assessment.time_limit_minutes:
            return None
        elapsed = (datetime.utcnow() - self.started_at).total_seconds()
        remaining = (self.assessment.time_limit_minutes * 60) - elapsed
        return max(0, remaining)
    
    @property
    def is_timed_out(self):
        """Check if assessment has timed out."""
        if not self.assessment.time_limit_minutes:
            return False
        return self.time_remaining <= 0
    
    def __repr__(self):
        return f'<CandidateAssessment {self.id}>'


class CandidateAnswer(db.Model):
    """Store candidate's answers to questions."""
    __tablename__ = 'candidate_answers'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign keys
    candidate_assessment_id = db.Column(db.Integer, db.ForeignKey('candidate_assessments.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('assessment_questions.id'), nullable=False)
    
    # Answer - for multiple choice, store option_id; for text, store text
    selected_option_id = db.Column(db.Integer, db.ForeignKey('question_options.id'), nullable=True)
    selected_options = db.Column(db.JSON, nullable=True)  # For multiple select
    text_answer = db.Column(db.Text, nullable=True)  # For text questions
    
    # Scoring
    is_correct = db.Column(db.Boolean, nullable=True)
    points_awarded = db.Column(db.Float, default=0)
    
    # Timestamps
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    question = db.relationship('AssessmentQuestion')
    selected_option = db.relationship('QuestionOption', foreign_keys=[selected_option_id])
    
    def __repr__(self):
        return f'<CandidateAnswer {self.id}>'


class Message(db.Model):
    """Internal messaging between HR and applicants."""
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Participants
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Context (optional - link to application/job)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job_postings.id'), nullable=True)
    
    # Message content
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    
    # Message type
    message_type = db.Column(db.Enum('general', 'application_update', 'interview_invite', 
                                      'document_request', 'offer', 'rejection', 'inquiry',
                                      name='message_types'), default='general')
    
    # Status
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime, nullable=True)
    is_archived = db.Column(db.Boolean, default=False)
    is_deleted_by_sender = db.Column(db.Boolean, default=False)
    is_deleted_by_recipient = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Reply chain
    parent_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=True)
    
    # Relationships
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_messages')
    application = db.relationship('Application', backref=db.backref('messages', lazy='dynamic'))
    job = db.relationship('JobPosting', backref=db.backref('messages', lazy='dynamic'))
    replies = db.relationship('Message', backref=db.backref('parent', remote_side=[id]))
    
    def mark_as_read(self):
        """Mark message as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()
            db.session.commit()
    
    @staticmethod
    def get_unread_count(user_id):
        """Get count of unread messages for a user."""
        return Message.query.filter_by(
            recipient_id=user_id,
            is_read=False,
            is_deleted_by_recipient=False
        ).count()
    
    def __repr__(self):
        return f'<Message {self.id}: {self.subject[:30]}>'


class MessageTemplate(db.Model):
    """Reusable message templates for HR."""
    __tablename__ = 'message_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Template details
    name = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    
    # Categorization
    template_type = db.Column(db.Enum('application_update', 'interview_invite', 'document_request',
                                       'offer', 'rejection', 'general',
                                       name='template_types'), default='general')
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    
    # Ownership
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    creator = db.relationship('User', backref='message_templates')
    
    def __repr__(self):
        return f'<MessageTemplate {self.name}>'


class BulkNotification(db.Model):
    """Track bulk notifications sent to multiple recipients."""
    __tablename__ = 'bulk_notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Notification details
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    
    # Targeting
    target_type = db.Column(db.Enum('all_applicants', 'job_applicants', 'status_group', 'custom',
                                     name='target_types'), default='all_applicants')
    target_job_id = db.Column(db.Integer, db.ForeignKey('job_postings.id'), nullable=True)
    target_status = db.Column(db.String(50), nullable=True)  # e.g., 'shortlisted', 'submitted'
    
    # Delivery
    send_email = db.Column(db.Boolean, default=True)
    send_internal = db.Column(db.Boolean, default=True)
    
    # Stats
    total_recipients = db.Column(db.Integer, default=0)
    sent_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    
    # Status
    status = db.Column(db.Enum('draft', 'sending', 'completed', 'failed',
                               name='notification_status'), default='draft')
    
    # Ownership
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    creator = db.relationship('User', backref='bulk_notifications')
    target_job = db.relationship('JobPosting', backref='bulk_notifications')
    
    def __repr__(self):
        return f'<BulkNotification {self.id}: {self.subject[:30]}>'


# ==================== WORKFLOW AUTOMATION MODELS ====================

class WorkflowRule(db.Model):
    """Define automated workflow rules for recruitment process."""
    __tablename__ = 'workflow_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Trigger configuration
    trigger_type = db.Column(db.Enum('status_change', 'time_based', 'score_based', 'document_submitted',
                                      'interview_scheduled', 'interview_completed', 'job_closing',
                                      name='trigger_types'), nullable=False)
    trigger_status = db.Column(db.String(50), nullable=True)  # For status_change trigger
    trigger_days = db.Column(db.Integer, nullable=True)  # For time_based trigger (days before/after)
    trigger_score = db.Column(db.Integer, nullable=True)  # For score_based trigger
    
    # Action configuration
    action_type = db.Column(db.Enum('change_status', 'send_email', 'send_notification', 'assign_reviewer',
                                     'create_task', 'schedule_reminder',
                                     name='action_types'), nullable=False)
    action_status = db.Column(db.String(50), nullable=True)  # For change_status action
    action_template_id = db.Column(db.Integer, db.ForeignKey('message_templates.id'), nullable=True)
    action_config = db.Column(db.JSON, nullable=True)  # Additional action configuration
    
    # Conditions
    condition_job_id = db.Column(db.Integer, db.ForeignKey('job_postings.id'), nullable=True)  # Apply to specific job or null for all
    condition_min_score = db.Column(db.Integer, nullable=True)
    condition_max_score = db.Column(db.Integer, nullable=True)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    priority = db.Column(db.Integer, default=0)  # Higher priority rules execute first
    
    # Ownership
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    creator = db.relationship('User', backref='workflow_rules')
    condition_job = db.relationship('JobPosting', backref='workflow_rules')
    action_template = db.relationship('MessageTemplate', backref='workflow_rules')
    executions = db.relationship('WorkflowExecution', backref='rule', lazy='dynamic')
    
    def __repr__(self):
        return f'<WorkflowRule {self.name}>'


class WorkflowExecution(db.Model):
    """Log workflow rule executions."""
    __tablename__ = 'workflow_executions'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Rule reference
    rule_id = db.Column(db.Integer, db.ForeignKey('workflow_rules.id'), nullable=False)
    
    # Target
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job_postings.id'), nullable=True)
    
    # Execution details
    trigger_event = db.Column(db.String(100), nullable=True)  # What triggered this execution
    action_taken = db.Column(db.String(255), nullable=True)  # Description of action taken
    
    # Status
    status = db.Column(db.Enum('pending', 'completed', 'failed', 'skipped',
                               name='execution_status'), default='pending')
    error_message = db.Column(db.Text, nullable=True)
    
    # Timestamps
    executed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    application = db.relationship('Application', backref='workflow_executions')
    job = db.relationship('JobPosting', backref='workflow_executions')
    
    def __repr__(self):
        return f'<WorkflowExecution {self.id} for rule {self.rule_id}>'


class ScheduledTask(db.Model):
    """Scheduled tasks for automated workflows."""
    __tablename__ = 'scheduled_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Task configuration
    task_type = db.Column(db.Enum('job_closing_reminder', 'interview_reminder', 'application_followup',
                                   'document_reminder', 'status_update', 'report_generation', 'cleanup',
                                   name='task_types'), nullable=False)
    task_config = db.Column(db.JSON, nullable=True)  # Task-specific configuration
    
    # Scheduling
    schedule_type = db.Column(db.Enum('once', 'daily', 'weekly', 'monthly',
                                       name='schedule_types'), default='once')
    scheduled_time = db.Column(db.Time, nullable=True)  # Time of day to run
    scheduled_date = db.Column(db.Date, nullable=True)  # For one-time tasks
    day_of_week = db.Column(db.Integer, nullable=True)  # 0=Monday, 6=Sunday for weekly
    day_of_month = db.Column(db.Integer, nullable=True)  # 1-31 for monthly
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.DateTime, nullable=True)
    next_run = db.Column(db.DateTime, nullable=True)
    run_count = db.Column(db.Integer, default=0)
    
    # Ownership
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    creator = db.relationship('User', backref='scheduled_tasks')
    
    def __repr__(self):
        return f'<ScheduledTask {self.name}>'


class StatusTransitionLog(db.Model):
    """Log all status transitions for applications."""
    __tablename__ = 'status_transition_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Reference
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=False)
    
    # Transition details
    from_status = db.Column(db.String(50), nullable=True)  # Null for initial status
    to_status = db.Column(db.String(50), nullable=False)
    
    # Who made the change
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Null for automated changes
    change_type = db.Column(db.Enum('manual', 'automated', 'system',
                                     name='change_types'), default='manual')
    
    # Additional info
    notes = db.Column(db.Text, nullable=True)
    workflow_rule_id = db.Column(db.Integer, db.ForeignKey('workflow_rules.id'), nullable=True)  # If triggered by rule
    
    # Timestamp
    transitioned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    application = db.relationship('Application', backref='status_transitions')
    changed_by_user = db.relationship('User', backref='status_changes')
    workflow_rule = db.relationship('WorkflowRule', backref='status_transitions')
    
    def __repr__(self):
        return f'<StatusTransitionLog {self.from_status} -> {self.to_status}>'


# ==================== COMMITTEE MANAGEMENT MODELS ====================

class Committee(db.Model):
    """Committee for shortlisting and interviewing candidates."""
    __tablename__ = 'committees'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Committee type
    committee_type = db.Column(db.Enum('shortlisting', 'interviewing', name='committee_types'),
                               nullable=False)
    
    # Scope
    job_id = db.Column(db.Integer, db.ForeignKey('job_postings.id'), nullable=True)  # NULL = org-wide
    
    # Decision rules
    requires_unanimous = db.Column(db.Boolean, default=False)  # True = all must approve, False = majority
    min_votes_required = db.Column(db.Integer, default=1)  # Minimum votes to make decision
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    
    # Ownership and timestamps
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    creator = db.relationship('User', backref='created_committees')
    job = db.relationship('JobPosting', backref='committees')
    members = db.relationship('CommitteeMember', backref='committee', lazy='dynamic',
                            cascade='all, delete-orphan')
    decisions = db.relationship('CommitteeDecision', backref='committee', lazy='dynamic',
                               cascade='all, delete-orphan')
    
    @property
    def member_count(self):
        """Get number of active members."""
        return self.members.count()
    
    def get_decision_status(self, application_id):
        """Get decision status for an application."""
        decision = CommitteeDecision.query.filter_by(
            committee_id=self.id,
            application_id=application_id
        ).first()
        return decision.decision if decision else None
    
    def __repr__(self):
        return f'<Committee {self.name}>'


class CommitteeMember(db.Model):
    """Members of a committee."""
    __tablename__ = 'committee_members'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign keys
    committee_id = db.Column(db.Integer, db.ForeignKey('committees.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Role in committee
    role = db.Column(db.Enum('chair', 'member', name='committee_roles'),
                    default='member')
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='committee_memberships')
    
    def __repr__(self):
        return f'<CommitteeMember {self.user.full_name} in {self.committee.name}>'


class CommitteeDecision(db.Model):
    """Individual votes and decisions by committee members."""
    __tablename__ = 'committee_decisions'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # References
    committee_id = db.Column(db.Integer, db.ForeignKey('committees.id'), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job_postings.id'), nullable=False)
    
    # Overall decision
    decision = db.Column(db.Enum('pending', 'approved', 'rejected', 'needs_review',
                                 name='decision_statuses'), default='pending')
    
    # Vote aggregation
    votes_yes = db.Column(db.Integer, default=0)
    votes_no = db.Column(db.Integer, default=0)
    votes_abstain = db.Column(db.Integer, default=0)
    
    # Individual votes (JSON format: {user_id: 'approved'|'rejected'|'abstain'})
    individual_votes = db.Column(db.JSON, nullable=True)
    
    # Final decision info
    finalized_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Chair who finalized
    finalized_at = db.Column(db.DateTime, nullable=True)
    
    # Committee notes and comments
    committee_notes = db.Column(db.Text, nullable=True)
    
    # For tracking reviews
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    application = db.relationship('Application', backref='committee_decisions')
    job = db.relationship('JobPosting', backref='committee_decisions')
    finalized_by_user = db.relationship('User', foreign_keys=[finalized_by], 
                                       backref='finalized_decisions')
    individual_votes_details = db.relationship('CommitteeMemberVote', backref='decision',
                                             lazy='dynamic', cascade='all, delete-orphan')
    
    @property
    def total_votes(self):
        """Get total number of votes cast."""
        return self.votes_yes + self.votes_no + self.votes_abstain
    
    @property
    def votes_pending(self):
        """Calculate votes still pending from committee."""
        committee = self.committee
        votes_cast = self.total_votes if self.individual_votes else 0
        return committee.member_count - votes_cast
    
    @property
    def is_decision_final(self):
        """Check if decision is final."""
        return self.decision in ('approved', 'rejected')
    
    def __repr__(self):
        return f'<CommitteeDecision for Application {self.application_id}>'


class CommitteeMemberVote(db.Model):
    """Individual votes cast by committee members."""
    __tablename__ = 'committee_member_votes'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # References
    decision_id = db.Column(db.Integer, db.ForeignKey('committee_decisions.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('committee_members.id'), nullable=False)
    
    # Vote
    vote = db.Column(db.Enum('approved', 'rejected', 'abstain', name='vote_options'),
                    nullable=False)
    
    # Vote details
    comments = db.Column(db.Text, nullable=True)
    rating = db.Column(db.Float, nullable=True)  # 1-5 star rating
    
    # Timestamps
    voted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    member = db.relationship('CommitteeMember', backref='votes')
    
    def __repr__(self):
        return f'<CommitteeMemberVote {self.member.user.full_name}: {self.vote}>'
