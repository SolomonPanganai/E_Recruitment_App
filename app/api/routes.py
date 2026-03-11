"""REST API routes."""
from datetime import datetime
from flask import jsonify, request
from flask_login import login_required, current_user
from app import db
from app.api import api_bp
from app.models import JobPosting, Application, User, AuditLog


def hr_required_api(f):
    """API decorator for HR access."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        if current_user.role not in ('hr_officer', 'manager', 'admin'):
            return jsonify({'error': 'HR privileges required'}), 403
        return f(*args, **kwargs)
    return decorated_function


# ============== Job Endpoints ==============

@api_bp.route('/jobs')
def get_jobs():
    """Get list of published jobs."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    department = request.args.get('department')
    keyword = request.args.get('keyword')
    
    query = JobPosting.query.filter_by(status='published')
    
    if department:
        query = query.filter_by(department=department)
    if keyword:
        query = query.filter(
            (JobPosting.title.ilike(f'%{keyword}%')) |
            (JobPosting.job_purpose.ilike(f'%{keyword}%'))
        )
    
    jobs = query.order_by(JobPosting.posting_date.desc()).paginate(
        page=page,
        per_page=min(per_page, 50),
        error_out=False
    )
    
    return jsonify({
        'jobs': [{
            'id': job.id,
            'reference': job.job_reference,
            'title': job.title,
            'department': job.department,
            'location': job.location,
            'salary_range': job.salary_range,
            'closing_date': job.closing_date.isoformat() if job.closing_date else None,
            'days_until_closing': job.days_until_closing,
            'applications_count': job.applications_count
        } for job in jobs.items],
        'pagination': {
            'page': jobs.page,
            'pages': jobs.pages,
            'total': jobs.total,
            'has_next': jobs.has_next,
            'has_prev': jobs.has_prev
        }
    })


@api_bp.route('/jobs/<int:job_id>')
def get_job(job_id):
    """Get job details."""
    job = JobPosting.query.get_or_404(job_id)
    
    return jsonify({
        'id': job.id,
        'reference': job.job_reference,
        'title': job.title,
        'department': job.department,
        'location': job.location,
        'job_purpose': job.job_purpose,
        'responsibilities': job.responsibilities,
        'minimum_requirements': job.minimum_requirements,
        'preferred_requirements': job.preferred_requirements,
        'salary_range': job.salary_range,
        'posting_date': job.posting_date.isoformat() if job.posting_date else None,
        'closing_date': job.closing_date.isoformat() if job.closing_date else None,
        'status': job.status,
        'ee_target_category': job.ee_target_category,
        'views_count': job.views_count,
        'applications_count': job.applications_count
    })


@api_bp.route('/jobs/departments')
def get_departments():
    """Get list of unique departments."""
    departments = [d[0] for d in JobPosting.query.with_entities(
        JobPosting.department
    ).distinct().all()]
    
    return jsonify({'departments': departments})


@api_bp.route('/jobs/locations')
def get_locations():
    """Get list of unique locations."""
    locations = [l[0] for l in JobPosting.query.with_entities(
        JobPosting.location
    ).distinct().all()]
    
    return jsonify({'locations': locations})


# ============== Application Endpoints ==============

@api_bp.route('/applications/my')
@login_required
def get_my_applications():
    """Get current user's applications."""
    if current_user.role != 'applicant':
        return jsonify({'error': 'Applicants only'}), 403
    
    applications = Application.query.filter_by(
        applicant_id=current_user.id
    ).order_by(Application.application_date.desc()).all()
    
    return jsonify({
        'applications': [{
            'id': app.id,
            'reference': app.application_reference,
            'job': {
                'id': app.job.id,
                'title': app.job.title,
                'reference': app.job.job_reference
            },
            'status': app.status,
            'current_stage': app.current_stage,
            'application_date': app.application_date.isoformat(),
            'has_offer': app.offer is not None
        } for app in applications]
    })


@api_bp.route('/applications/<int:application_id>/status')
@login_required
def get_application_status(application_id):
    """Get application status (for applicant to track)."""
    application = Application.query.get_or_404(application_id)
    
    # Check access
    if current_user.role == 'applicant' and application.applicant_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify({
        'reference': application.application_reference,
        'status': application.status,
        'current_stage': application.current_stage,
        'screening_score': application.screening_score,
        'interview_score': application.interview_score,
        'has_interview': application.interviews.count() > 0,
        'has_offer': application.offer is not None,
        'updated_at': application.updated_at.isoformat()
    })


# ============== HR/Reports Endpoints ==============

@api_bp.route('/reports/overview')
@login_required
@hr_required_api
def get_reports_overview():
    """Get recruitment overview statistics."""
    total_jobs = JobPosting.query.count()
    active_jobs = JobPosting.query.filter_by(status='published').count()
    total_applications = Application.query.count()
    
    # Applications by status
    status_counts = db.session.query(
        Application.status, 
        db.func.count(Application.id)
    ).group_by(Application.status).all()
    
    # Applications by department
    dept_counts = db.session.query(
        JobPosting.department,
        db.func.count(Application.id)
    ).join(Application).group_by(JobPosting.department).all()
    
    return jsonify({
        'jobs': {
            'total': total_jobs,
            'active': active_jobs,
            'closed': JobPosting.query.filter_by(status='closed').count()
        },
        'applications': {
            'total': total_applications,
            'by_status': dict(status_counts),
            'by_department': dict(dept_counts)
        }
    })


@api_bp.route('/reports/diversity')
@login_required
@hr_required_api
def get_diversity_report():
    """Get diversity metrics for EE reporting."""
    # Gender breakdown of applicants
    gender_counts = db.session.query(
        User.gender,
        db.func.count(User.id)
    ).filter(User.role == 'applicant').group_by(User.gender).all()
    
    # Race breakdown
    race_counts = db.session.query(
        User.race,
        db.func.count(User.id)
    ).filter(User.role == 'applicant').group_by(User.race).all()
    
    # Disability status
    disability_count = User.query.filter(
        User.role == 'applicant',
        User.disability_status == True
    ).count()
    
    # Shortlisted by demographics
    shortlisted_gender = db.session.query(
        User.gender,
        db.func.count(Application.id)
    ).join(Application, Application.applicant_id == User.id
    ).filter(Application.status.in_(['shortlisted', 'interviewed', 'offered'])
    ).group_by(User.gender).all()
    
    return jsonify({
        'applicants': {
            'by_gender': dict(gender_counts),
            'by_race': dict(race_counts),
            'with_disability': disability_count
        },
        'shortlisted': {
            'by_gender': dict(shortlisted_gender)
        }
    })


@api_bp.route('/reports/timeline')
@login_required
@hr_required_api
def get_timeline_report():
    """Get applications timeline (last 30 days)."""
    from datetime import timedelta
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    # Applications per day
    daily_applications = db.session.query(
        db.func.date(Application.application_date),
        db.func.count(Application.id)
    ).filter(
        Application.application_date >= start_date
    ).group_by(
        db.func.date(Application.application_date)
    ).all()
    
    return jsonify({
        'period': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat()
        },
        'daily_applications': [
            {'date': str(date), 'count': count}
            for date, count in daily_applications
        ]
    })


# ============== Health Check ==============

@api_bp.route('/health')
def health_check():
    """API health check endpoint."""
    try:
        # Check database connection
        db.session.execute(db.text('SELECT 1'))
        db_status = 'healthy'
    except Exception as e:
        db_status = f'unhealthy: {str(e)}'
    
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat(),
        'database': db_status
    })


# ============== Committee Endpoints ==============

@api_bp.route('/committees', methods=['GET'])
@login_required
@hr_required_api
def list_committees():
    """Get list of committees."""
    from app.models import Committee
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    committee_type = request.args.get('type')
    
    query = Committee.query.filter_by(is_active=True)
    
    if committee_type:
        query = query.filter_by(committee_type=committee_type)
    
    committees = query.paginate(
        page=page,
        per_page=min(per_page, 50),
        error_out=False
    )
    
    return jsonify({
        'committees': [{
            'id': c.id,
            'name': c.name,
            'type': c.committee_type,
            'job_id': c.job_id,
            'member_count': c.member_count,
            'requires_unanimous': c.requires_unanimous,
            'created_at': c.created_at.isoformat()
        } for c in committees.items],
        'total': committees.total,
        'page': page,
        'per_page': per_page
    })


@api_bp.route('/committees', methods=['POST'])
@login_required
@hr_required_api
def create_committee():
    """Create a new committee."""
    data = request.get_json()
    
    if not data or not data.get('name') or not data.get('type'):
        return jsonify({'error': 'Missing required fields: name, type'}), 400
    
    from app.services.workflow_service import CommitteeService
    
    committee = CommitteeService.create_committee(
        name=data['name'],
        committee_type=data['type'],
        created_by=current_user.id,
        job_id=data.get('job_id'),
        requires_unanimous=data.get('requires_unanimous', False),
        min_votes_required=data.get('min_votes_required', 1),
        description=data.get('description')
    )
    
    return jsonify({
        'id': committee.id,
        'name': committee.name,
        'type': committee.committee_type,
        'message': 'Committee created successfully'
    }), 201


@api_bp.route('/committees/<int:committee_id>/members', methods=['POST'])
@login_required
@hr_required_api
def add_committee_member(committee_id):
    """Add a member to a committee."""
    data = request.get_json()
    
    if not data or not data.get('user_id'):
        return jsonify({'error': 'Missing required field: user_id'}), 400
    
    from app.services.workflow_service import CommitteeService
    from app.models import Committee
    
    committee = Committee.query.get(committee_id)
    if not committee:
        return jsonify({'error': 'Committee not found'}), 404
    
    member = CommitteeService.add_committee_member(
        committee_id=committee_id,
        user_id=data['user_id'],
        role=data.get('role', 'member')
    )
    
    return jsonify({
        'id': member.id,
        'user_id': member.user_id,
        'role': member.role,
        'message': 'Member added successfully'
    }), 201


@api_bp.route('/committees/<int:committee_id>', methods=['GET'])
@login_required
@hr_required_api
def get_committee(committee_id):
    """Get committee details."""
    from app.models import Committee
    
    committee = Committee.query.get(committee_id)
    if not committee:
        return jsonify({'error': 'Committee not found'}), 404
    
    return jsonify({
        'id': committee.id,
        'name': committee.name,
        'description': committee.description,
        'type': committee.committee_type,
        'job_id': committee.job_id,
        'requires_unanimous': committee.requires_unanimous,
        'min_votes_required': committee.min_votes_required,
        'member_count': committee.member_count,
        'members': [{
            'id': m.id,
            'user_id': m.user_id,
            'user_name': m.user.full_name,
            'role': m.role,
            'joined_at': m.joined_at.isoformat()
        } for m in committee.members],
        'created_at': committee.created_at.isoformat()
    })


@api_bp.route('/committees/<int:committee_id>/decisions/<int:application_id>', methods=['GET'])
@login_required
@hr_required_api
def get_committee_decision(committee_id, application_id):
    """Get committee decision for an application."""
    from app.models import CommitteeDecision
    
    decision = CommitteeDecision.query.filter_by(
        committee_id=committee_id,
        application_id=application_id
    ).first()
    
    if not decision:
        return jsonify({'error': 'Decision not found'}), 404
    
    return jsonify({
        'id': decision.id,
        'committee_id': decision.committee_id,
        'application_id': decision.application_id,
        'decision': decision.decision,
        'votes_yes': decision.votes_yes,
        'votes_no': decision.votes_no,
        'votes_abstain': decision.votes_abstain,
        'total_votes': decision.total_votes,
        'votes_pending': decision.votes_pending,
        'finalized_at': decision.finalized_at.isoformat() if decision.finalized_at else None,
        'notes': decision.committee_notes
    })


@api_bp.route('/committees/<int:committee_id>/decisions', methods=['POST'])
@login_required
@hr_required_api
def create_committee_decision(committee_id):
    """Create a committee decision for an application."""
    data = request.get_json()
    
    if not data or not data.get('application_id') or not data.get('job_id'):
        return jsonify({'error': 'Missing required fields: application_id, job_id'}), 400
    
    from app.services.workflow_service import CommitteeService
    from app.models import Committee
    
    committee = Committee.query.get(committee_id)
    if not committee:
        return jsonify({'error': 'Committee not found'}), 404
    
    decision = CommitteeService.create_committee_decision(
        committee_id=committee_id,
        application_id=data['application_id'],
        job_id=data['job_id']
    )
    
    return jsonify({
        'id': decision.id,
        'committee_id': decision.committee_id,
        'application_id': decision.application_id,
        'decision': decision.decision,
        'message': 'Committee decision created and members notified'
    }), 201


@api_bp.route('/committees/<int:committee_id>/decisions/<int:decision_id>/vote', methods=['POST'])
@login_required
@hr_required_api
def cast_committee_vote(committee_id, decision_id):
    """Cast a vote on a committee decision."""
    data = request.get_json()
    
    if not data or not data.get('vote') or not data.get('member_id'):
        return jsonify({'error': 'Missing required fields: vote, member_id'}), 400
    
    if data['vote'] not in ['approved', 'rejected', 'abstain']:
        return jsonify({'error': 'Invalid vote option. Must be: approved, rejected, or abstain'}), 400
    
    from app.services.workflow_service import CommitteeService
    
    try:
        vote = CommitteeService.cast_vote(
            decision_id=decision_id,
            member_id=data['member_id'],
            vote=data['vote'],
            comments=data.get('comments'),
            rating=data.get('rating')
        )
        
        return jsonify({
            'id': vote.id,
            'vote': vote.vote,
            'member_id': vote.member_id,
            'message': 'Vote recorded successfully'
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Error recording vote: {str(e)}'}), 500
