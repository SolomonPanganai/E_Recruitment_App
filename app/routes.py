"""Main application routes."""
from flask import Blueprint, render_template, request, current_app
from app.models import JobPosting
from app.forms import JobSearchForm

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Home page with featured jobs."""
    featured_jobs = JobPosting.query.filter_by(status='published').order_by(
        JobPosting.posting_date.desc()
    ).limit(6).all()
    return render_template('index.html', featured_jobs=featured_jobs)


@main_bp.route('/jobs')
def jobs():
    """Job listings page with advanced search."""
    form = JobSearchForm()
    page = request.args.get('page', 1, type=int)
    
    # Build query
    query = JobPosting.query.filter_by(status='published')
    
    # Search and filter parameters
    keyword = request.args.get('keyword', '').strip()
    department = request.args.get('department', '')
    location = request.args.get('location', '')
    sort_by = request.args.get('sort', 'newest')
    
    # Apply filters
    if keyword:
        search_term = f"%{keyword}%"
        query = query.filter(
            db.or_(
                JobPosting.title.ilike(search_term),
                JobPosting.job_purpose.ilike(search_term),
                JobPosting.responsibilities.ilike(search_term)
            )
        )
    if department:
        query = query.filter(JobPosting.department == department)
    if location:
        query = query.filter(JobPosting.location.ilike(f'%{location}%'))
    
    # Sorting
    if sort_by == 'oldest':
        query = query.order_by(JobPosting.posting_date.asc())
    elif sort_by == 'title':
        query = query.order_by(JobPosting.title.asc())
    elif sort_by == 'closing':
        query = query.order_by(JobPosting.closing_date.asc())
    else:  # newest (default)
        query = query.order_by(JobPosting.posting_date.desc())
    
    # Paginate
    jobs_pagination = query.paginate(
        page=page, 
        per_page=current_app.config.get('JOBS_PER_PAGE', 10),
        error_out=False
    )
    
    # Get unique departments and locations for filters
    departments = [d[0] for d in JobPosting.query.filter_by(status='published').with_entities(JobPosting.department).distinct().all() if d[0]]
    locations = [l[0] for l in JobPosting.query.filter_by(status='published').with_entities(JobPosting.location).distinct().all() if l[0]]
    
    form.department.choices = [('', 'All Departments')] + [(d, d) for d in departments]
    form.location.choices = [('', 'All Locations')] + [(l, l) for l in locations]
    
    return render_template('jobs.html', 
                           form=form,
                           jobs=jobs_pagination.items, 
                           pagination=jobs_pagination,
                           keyword=keyword,
                           selected_department=department,
                           selected_location=location,
                           sort_by=sort_by,
                           total_jobs=jobs_pagination.total)


@main_bp.route('/jobs/<int:job_id>')
def job_detail(job_id):
    """Job detail page."""
    job = JobPosting.query.get_or_404(job_id)
    
    # Increment view count
    job.views_count += 1
    from app import db
    db.session.commit()
    
    return render_template('job_detail.html', job=job)


@main_bp.route('/faq')
def faq():
    """FAQ page."""
    return render_template('faq.html')


@main_bp.route('/contact')
def contact():
    """Contact/Support page."""
    return render_template('contact.html')


@main_bp.route('/privacy')
def privacy():
    """Privacy Policy page."""
    return render_template('privacy.html')


@main_bp.route('/terms')
def terms():
    """Terms of Service page."""
    return render_template('terms.html')


@main_bp.app_errorhandler(404)
def not_found_error(error):
    """404 error handler."""
    return render_template('errors/404.html'), 404


@main_bp.app_errorhandler(500)
def internal_error(error):
    """500 error handler."""
    from app import db
    db.session.rollback()
    return render_template('errors/500.html'), 500
