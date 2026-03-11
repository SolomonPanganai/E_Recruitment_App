"""HR/Manager dashboard routes."""
import os
import io
import zipfile
from datetime import datetime, timedelta
from functools import wraps
from flask import render_template, redirect, url_for, flash, request, current_app, jsonify, send_file, send_from_directory
from flask_login import login_required, current_user
from app import db
from app.hr import hr_bp
from app.models import (User, JobPosting, Application, Document, Shortlist, 
                        Interview, Offer, AuditLog, create_audit_log,
                        UserActivity, log_user_activity, Message, MessageTemplate,
                        BulkNotification, WorkflowRule, WorkflowExecution, 
                        ScheduledTask, StatusTransitionLog, SystemSettings)
from app.forms import (JobPostingForm, ApplicationStatusForm, ScreeningForm,
                       InterviewScheduleForm, InterviewFeedbackForm, OfferForm,
                       UserManagementForm, ReportFilterForm, CreateStaffForm,
                       SystemSettingsForm)
from app.utils.screening import calculate_screening_score
from app.utils.notifications import (send_status_update_email, send_interview_invitation,
                                      send_offer_email, send_rejection_email)


def hr_required(f):
    """Decorator to require HR/Manager/Admin role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ('hr_officer', 'manager', 'admin'):
            flash('Access denied. HR privileges required.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require Admin role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('hr.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def generate_job_reference(department):
    """Generate unique job reference."""
    year = datetime.utcnow().year
    dept_abbrev = ''.join([word[0].upper() for word in department.split()[:2]])
    count = JobPosting.query.filter(
        JobPosting.job_reference.like(f'MUN/{dept_abbrev}/%/{year}')
    ).count() + 1
    return f"MUN/{dept_abbrev}/{count:03d}/{year}"


# ============== Dashboard ==============

@hr_bp.route('/dashboard')
@login_required
@hr_required
def dashboard():
    """HR/Manager Dashboard with key metrics."""
    # Job statistics
    total_jobs = JobPosting.query.count()
    active_jobs = JobPosting.query.filter_by(status='published').count()
    
    # Application statistics
    total_applications = Application.query.count()
    pending_review = Application.query.filter_by(status='submitted').count()
    shortlisted = Application.query.filter_by(status='shortlisted').count()
    interviewed = Application.query.filter_by(status='interviewed').count()
    
    # Manager-specific: pending job approvals
    pending_approvals = JobPosting.query.filter_by(status='pending_approval').count()
    draft_jobs = JobPosting.query.filter_by(status='draft').count()
    
    # Jobs pending approval (for manager review)
    jobs_pending_approval = JobPosting.query.filter_by(
        status='pending_approval'
    ).order_by(JobPosting.created_at.desc()).limit(5).all()
    
    # Candidates ready for offer (interviewed status)
    ready_for_offer = Application.query.filter_by(
        status='interviewed'
    ).order_by(Application.updated_at.desc()).limit(5).all()
    
    # Recent applications
    recent_applications = Application.query.order_by(
        Application.application_date.desc()
    ).limit(10).all()
    
    # Jobs closing soon
    closing_soon = JobPosting.query.filter(
        JobPosting.status == 'published',
        JobPosting.closing_date >= datetime.utcnow()
    ).order_by(JobPosting.closing_date).limit(5).all()
    
    return render_template('hr_dashboard.html',
                           total_jobs=total_jobs,
                           active_jobs=active_jobs,
                           total_applications=total_applications,
                           pending_review=pending_review,
                           shortlisted=shortlisted,
                           interviewed=interviewed,
                           pending_approvals=pending_approvals,
                           draft_jobs=draft_jobs,
                           jobs_pending_approval=jobs_pending_approval,
                           ready_for_offer=ready_for_offer,
                           recent_applications=recent_applications,
                           closing_soon=closing_soon)

# ============== System Settings ==============
@hr_bp.route('/system-settings', methods=['GET', 'POST'])
@login_required
@admin_required
def system_settings():
    """Admin page to update system name and theme."""
    settings = SystemSettings.query.first()
    if not settings:
        settings = SystemSettings()
        db.session.add(settings)
        db.session.commit()
    form = SystemSettingsForm(obj=settings)
    # Handle theme change from modal POST
    if request.method == 'POST' and 'theme' in request.form:
        from flask_wtf.csrf import validate_csrf
        try:
            validate_csrf(request.form.get('csrf_token'))
        except Exception:
            flash('Invalid CSRF token.', 'danger')
            return redirect(url_for('hr.system_settings'))
        settings.theme = request.form['theme']
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Theme updated successfully.', 'success')
        return redirect(url_for('hr.system_settings'))
    # Standard settings form
    if request.method == 'POST':
        # Only update settings if form validates
        if form.validate_on_submit():
            settings.system_name = form.system_name.data
            settings.theme = form.theme.data
            settings.updated_at = datetime.utcnow()
            logo_file = form.logo.data
            import logging
            logger = logging.getLogger('logo_upload')
            logger.info(f"Logo upload triggered. logo_file: {logo_file}, type: {type(logo_file)}")
            logo_updated = False
            if logo_file and hasattr(logo_file, 'filename') and logo_file.filename:
                logger.info(f"Processing logo file: {logo_file.filename}")
                # Delete old logo file if exists
                if settings.logo:
                    old_logo_path = os.path.abspath(os.path.join(current_app.root_path, '..', 'static', 'images', settings.logo))
                    logger.info(f"Checking for old logo file: {old_logo_path}")
                    if os.path.exists(old_logo_path):
                        try:
                            os.remove(old_logo_path)
                            logger.info(f"Deleted old logo file: {old_logo_path}")
                        except Exception as e:
                            logger.error(f"Failed to delete old logo file: {e}")
                ext = logo_file.filename.rsplit('.', 1)[-1].lower()
                filename = f"logo_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{ext}"
                static_dir = os.path.abspath(os.path.join(current_app.root_path, '..', 'static', 'images'))
                logger.info(f"Saving logo to directory: {static_dir}")
                if not os.path.exists(static_dir):
                    os.makedirs(static_dir)
                    logger.info(f"Created directory: {static_dir}")
                logo_path = os.path.join(static_dir, filename)
                logger.info(f"Saving logo file to: {logo_path}")
                try:
                    logo_file.save(logo_path)
                    logger.info(f"Logo file saved successfully: {logo_path}")
                    settings.logo = filename
                    logo_updated = True
                except Exception as e:
                    logger.error(f"Failed to save new logo file: {e}")
                    flash(f'Failed to upload logo: {e}', 'danger')
            db.session.commit()
            # Only show one success message
            if logo_updated:
                flash('Logo updated successfully!', 'success')
            else:
                flash('System settings updated successfully.', 'success')
            return redirect(url_for('hr.system_settings'))
        else:
            flash('Form validation failed. Please check your input.', 'danger')
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        flash('System settings updated successfully.', 'success')
        return redirect(url_for('hr.system_settings'))
    return render_template('admin/system_settings.html', form=form, settings=settings)


# ============== Job Management ==============

@hr_bp.route('/jobs')
@login_required
@hr_required
def jobs():
    """List all jobs for HR with advanced search."""
    page = request.args.get('page', 1, type=int)
    
    # Search and filter parameters
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    department_filter = request.args.get('department', '')
    location_filter = request.args.get('location', '')
    sort_by = request.args.get('sort', 'date_desc')
    
    query = JobPosting.query
    
    # Text search
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                JobPosting.title.ilike(search_term),
                JobPosting.job_reference.ilike(search_term),
                JobPosting.job_purpose.ilike(search_term)
            )
        )
    
    if status_filter:
        query = query.filter(JobPosting.status == status_filter)
    if department_filter:
        query = query.filter(JobPosting.department == department_filter)
    if location_filter:
        query = query.filter(JobPosting.location.ilike(f"%{location_filter}%"))
    
    # Sorting
    if sort_by == 'date_asc':
        query = query.order_by(JobPosting.created_at.asc())
    elif sort_by == 'title_asc':
        query = query.order_by(JobPosting.title.asc())
    elif sort_by == 'title_desc':
        query = query.order_by(JobPosting.title.desc())
    elif sort_by == 'apps_desc':
        query = query.order_by(JobPosting.applications_count.desc())
    elif sort_by == 'closing_asc':
        query = query.order_by(JobPosting.closing_date.asc())
    else:  # date_desc (default)
        query = query.order_by(JobPosting.created_at.desc())
    
    jobs_paginated = query.paginate(
        page=page,
        per_page=current_app.config.get('JOBS_PER_PAGE', 10),
        error_out=False
    )
    
    # Get distinct departments and locations for filters
    departments = [d[0] for d in JobPosting.query.with_entities(JobPosting.department).distinct().all() if d[0]]
    locations = [l[0] for l in JobPosting.query.with_entities(JobPosting.location).distinct().all() if l[0]]
    
    return render_template('hr_jobs.html', 
                           jobs=jobs_paginated.items,
                           pagination=jobs_paginated,
                           search=search,
                           status_filter=status_filter,
                           department_filter=department_filter,
                           location_filter=location_filter,
                           sort_by=sort_by,
                           departments=departments,
                           locations=locations,
                           now=datetime.utcnow())


@hr_bp.route('/jobs/create', methods=['GET', 'POST'])
@login_required
@hr_required
def create_job():
    """Create a new job posting."""
    form = JobPostingForm()
    
    if form.validate_on_submit():
        # Build requirements JSON
        minimum_requirements = {
            'education': form.min_education.data,
            'experience_years': form.min_experience_years.data,
            'skills': [s.strip() for s in form.required_skills.data.split('\n') if s.strip()]
        }
        
        preferred_requirements = None
        if form.preferred_skills.data:
            preferred_requirements = {
                'skills': [s.strip() for s in form.preferred_skills.data.split('\n') if s.strip()]
            }
        
        job = JobPosting(
            job_reference=generate_job_reference(form.department.data),
            title=form.title.data,
            department=form.department.data,
            location=form.location.data,
            job_purpose=form.job_purpose.data,
            responsibilities=form.responsibilities.data,
            minimum_requirements=minimum_requirements,
            preferred_requirements=preferred_requirements,
            salary_range=form.salary_range.data,
            closing_date=form.closing_date.data,
            ee_target_category=form.ee_target_category.data,
            status=form.status.data,
            created_by=current_user.id
        )
        
        # Auto-approve if admin/manager publishing directly
        if form.status.data == 'published' and current_user.role in ('admin', 'manager'):
            job.approved_by = current_user.id
            job.approved_date = datetime.utcnow()
        
        db.session.add(job)
        db.session.flush()
        
        create_audit_log(
            user_id=current_user.id,
            action='CREATE_JOB',
            entity_type='JobPosting',
            entity_id=job.id,
            new_values={'reference': job.job_reference, 'title': job.title, 'status': job.status},
            ip_address=request.remote_addr
        )
        
        db.session.commit()
        
        flash(f'Job posting {job.job_reference} created successfully.', 'success')
        return redirect(url_for('hr.job_detail', job_id=job.id))
    
    return render_template('job_form.html', form=form, title='Create Job Posting')


@hr_bp.route('/jobs/<int:job_id>')
@login_required
@hr_required
def job_detail(job_id):
    """View job details with applications."""
    job = JobPosting.query.get_or_404(job_id)
    
    # Get applications with optional filtering
    status_filter = request.args.get('status', '')
    query = Application.query.filter_by(job_id=job_id)
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    applications = query.order_by(Application.screening_score.desc()).all()
    
    return render_template('hr_job_detail.html', 
                           job=job, 
                           applications=applications,
                           status_filter=status_filter)


@hr_bp.route('/jobs/<int:job_id>/edit', methods=['GET', 'POST'])
@login_required
@hr_required
def edit_job(job_id):
    """Edit a job posting."""
    job = JobPosting.query.get_or_404(job_id)
    
    # Don't allow editing published jobs with applications
    if job.status == 'published' and job.applications_count > 0:
        flash('Cannot edit a published job with existing applications.', 'warning')
        return redirect(url_for('hr.job_detail', job_id=job_id))
    
    form = JobPostingForm(obj=job)
    
    if request.method == 'GET':
        # Populate form with existing requirements
        if job.minimum_requirements:
            form.min_education.data = job.minimum_requirements.get('education', '')
            form.min_experience_years.data = job.minimum_requirements.get('experience_years', 0)
            form.required_skills.data = '\n'.join(job.minimum_requirements.get('skills', []))
        if job.preferred_requirements:
            form.preferred_skills.data = '\n'.join(job.preferred_requirements.get('skills', []))
    
    if form.validate_on_submit():
        old_values = {'title': job.title, 'status': job.status}
        
        job.title = form.title.data
        job.department = form.department.data
        job.location = form.location.data
        job.job_purpose = form.job_purpose.data
        job.responsibilities = form.responsibilities.data
        job.minimum_requirements = {
            'education': form.min_education.data,
            'experience_years': form.min_experience_years.data,
            'skills': [s.strip() for s in form.required_skills.data.split('\n') if s.strip()]
        }
        if form.preferred_skills.data:
            job.preferred_requirements = {
                'skills': [s.strip() for s in form.preferred_skills.data.split('\n') if s.strip()]
            }
        job.salary_range = form.salary_range.data
        job.closing_date = form.closing_date.data
        job.ee_target_category = form.ee_target_category.data
        job.status = form.status.data
        
        create_audit_log(
            user_id=current_user.id,
            action='UPDATE_JOB',
            entity_type='JobPosting',
            entity_id=job.id,
            old_values=old_values,
            new_values={'title': job.title, 'status': job.status},
            ip_address=request.remote_addr
        )
        
        db.session.commit()
        
        flash('Job posting updated successfully.', 'success')
        return redirect(url_for('hr.job_detail', job_id=job_id))
    
    return render_template('job_form.html', form=form, job=job, title='Edit Job Posting')


@hr_bp.route('/jobs/<int:job_id>/approve', methods=['POST'])
@login_required
@hr_required
def approve_job(job_id):
    """Approve and publish a job posting."""
    if current_user.role not in ('manager', 'admin'):
        flash('Only managers can approve job postings.', 'danger')
        return redirect(url_for('hr.job_detail', job_id=job_id))
    
    job = JobPosting.query.get_or_404(job_id)
    
    old_status = job.status
    job.status = 'published'
    job.approved_by = current_user.id
    job.approved_date = datetime.utcnow()
    job.posting_date = datetime.utcnow()
    
    create_audit_log(
        user_id=current_user.id,
        action='APPROVE_JOB',
        entity_type='JobPosting',
        entity_id=job.id,
        old_values={'status': old_status},
        new_values={'status': 'published'},
        ip_address=request.remote_addr
    )
    
    db.session.commit()
    
    flash(f'Job {job.job_reference} has been approved and published.', 'success')
    return redirect(url_for('hr.job_detail', job_id=job_id))


@hr_bp.route('/jobs/<int:job_id>/close', methods=['POST'])
@login_required
@hr_required
def close_job(job_id):
    """Close a job posting."""
    job = JobPosting.query.get_or_404(job_id)
    
    old_status = job.status
    job.status = 'closed'
    
    create_audit_log(
        user_id=current_user.id,
        action='CLOSE_JOB',
        entity_type='JobPosting',
        entity_id=job.id,
        old_values={'status': old_status},
        new_values={'status': 'closed'},
        ip_address=request.remote_addr
    )
    
    db.session.commit()
    
    flash(f'Job {job.job_reference} has been closed.', 'info')
    return redirect(url_for('hr.job_detail', job_id=job_id))


# ============== Application Management ==============

@hr_bp.route('/applications')
@login_required
@hr_required
def applications():
    """List all applications with advanced search and filtering."""
    page = request.args.get('page', 1, type=int)
    
    # Search and filter parameters
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    job_filter = request.args.get('job_id', type=int)
    department_filter = request.args.get('department', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    sort_by = request.args.get('sort', 'date_desc')
    
    # Score filters
    min_screening = request.args.get('min_screening', type=int)
    max_screening = request.args.get('max_screening', type=int)
    
    query = Application.query.join(User, Application.applicant_id == User.id).join(
        JobPosting, Application.job_id == JobPosting.id
    )
    
    # Text search - search in applicant name, email, reference, job title
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                User.full_name.ilike(search_term),
                User.email.ilike(search_term),
                Application.application_reference.ilike(search_term),
                JobPosting.title.ilike(search_term)
            )
        )
    
    if status_filter:
        query = query.filter(Application.status == status_filter)
    if job_filter:
        query = query.filter(Application.job_id == job_filter)
    if department_filter:
        query = query.filter(JobPosting.department == department_filter)
    
    # Date range filter
    if date_from:
        query = query.filter(Application.created_at >= date_from)
    if date_to:
        query = query.filter(Application.created_at <= date_to)
    
    # Score filters
    if min_screening:
        query = query.filter(Application.screening_score >= min_screening)
    if max_screening:
        query = query.filter(Application.screening_score <= max_screening)
    
    # Sorting
    if sort_by == 'date_asc':
        query = query.order_by(Application.created_at.asc())
    elif sort_by == 'name_asc':
        query = query.order_by(User.last_name.asc(), User.first_name.asc())
    elif sort_by == 'name_desc':
        query = query.order_by(User.last_name.desc(), User.first_name.desc())
    elif sort_by == 'score_desc':
        query = query.order_by(Application.screening_score.desc())
    elif sort_by == 'score_asc':
        query = query.order_by(Application.screening_score.asc())
    else:  # date_desc (default)
        query = query.order_by(Application.created_at.desc())
    
    applications_paginated = query.paginate(
        page=page,
        per_page=current_app.config.get('APPLICATIONS_PER_PAGE', 20),
        error_out=False
    )
    
    jobs = JobPosting.query.all()
    departments = [d[0] for d in JobPosting.query.with_entities(JobPosting.department).distinct().all() if d[0]]
    
    return render_template('hr_applications.html',
                           applications=applications_paginated.items,
                           pagination=applications_paginated,
                           jobs=jobs,
                           departments=departments,
                           search=search,
                           status_filter=status_filter,
                           job_filter=job_filter,
                           department_filter=department_filter,
                           date_from=date_from,
                           date_to=date_to,
                           sort_by=sort_by,
                           min_screening=min_screening,
                           max_screening=max_screening)


@hr_bp.route('/applications/<int:application_id>')
@login_required
@hr_required
def application_detail(application_id):
    """View application details."""
    application = Application.query.get_or_404(application_id)
    status_form = ApplicationStatusForm(obj=application)
    screening_form = ScreeningForm(obj=application)
    
    return render_template('hr_application_detail.html',
                           application=application,
                           status_form=status_form,
                           screening_form=screening_form)


@hr_bp.route('/applications/<int:application_id>/update-status', methods=['POST'])
@login_required
@hr_required
def update_application_status(application_id):
    """Update application status."""
    application = Application.query.get_or_404(application_id)
    form = ApplicationStatusForm()
    
    if form.validate_on_submit():
        old_status = application.status
        application.status = form.status.data
        application.current_stage = form.current_stage.data or application.current_stage
        
        if form.notes.data:
            application.notes = (application.notes or '') + f"\n[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] {form.notes.data}"
        
        create_audit_log(
            user_id=current_user.id,
            action='UPDATE_APPLICATION_STATUS',
            entity_type='Application',
            entity_id=application.id,
            old_values={'status': old_status},
            new_values={'status': application.status},
            ip_address=request.remote_addr
        )
        
        db.session.commit()
        
        # Send notification to applicant
        try:
            send_status_update_email(application)
        except Exception as e:
            current_app.logger.error(f'Failed to send status email: {e}')
        
        flash('Application status updated.', 'success')
    
    return redirect(url_for('hr.application_detail', application_id=application_id))


@hr_bp.route('/applications/<int:application_id>/screen', methods=['POST'])
@login_required
@hr_required
def screen_application(application_id):
    """Screen an application."""
    application = Application.query.get_or_404(application_id)
    form = ScreeningForm()
    
    if form.validate_on_submit():
        # Calculate auto score if not manually provided
        if form.screening_score.data:
            application.screening_score = form.screening_score.data
        else:
            application.screening_score = calculate_screening_score(application)
        
        if form.notes.data:
            application.notes = (application.notes or '') + f"\n[Screening] {form.notes.data}"
        
        application.status = 'under_review'
        application.current_stage = 'Screened'
        
        # Add to shortlist if requested
        if form.shortlist.data:
            if not application.shortlist:
                shortlist = Shortlist(
                    application_id=application.id,
                    job_id=application.job_id,
                    shortlisted_by=current_user.id,
                    notes=form.notes.data
                )
                db.session.add(shortlist)
                application.status = 'shortlisted'
                application.current_stage = 'Shortlisted'
        
        create_audit_log(
            user_id=current_user.id,
            action='SCREEN_APPLICATION',
            entity_type='Application',
            entity_id=application.id,
            new_values={'screening_score': application.screening_score, 'status': application.status},
            ip_address=request.remote_addr
        )
        
        db.session.commit()
        
        # Send status update email if shortlisted
        if application.status == 'shortlisted':
            try:
                send_status_update_email(application)
                current_app.logger.info(f'Shortlist notification sent for application {application_id}')
            except Exception as e:
                current_app.logger.error(f'Failed to send shortlist notification: {e}')
        
        flash('Application screened successfully.', 'success')
    
    return redirect(url_for('hr.application_detail', application_id=application_id))


@hr_bp.route('/jobs/<int:job_id>/auto-screen', methods=['POST'])
@login_required
@hr_required
def auto_screen_job(job_id):
    """Auto-screen all submitted applications for a job."""
    job = JobPosting.query.get_or_404(job_id)
    
    applications = Application.query.filter_by(
        job_id=job_id,
        status='submitted'
    ).all()
    
    screened_count = 0
    for app in applications:
        app.screening_score = calculate_screening_score(app)
        app.status = 'under_review'
        app.current_stage = 'Screened'
        screened_count += 1
    
    create_audit_log(
        user_id=current_user.id,
        action='AUTO_SCREEN_JOB',
        entity_type='JobPosting',
        entity_id=job_id,
        new_values={'screened_count': screened_count},
        ip_address=request.remote_addr
    )
    
    db.session.commit()
    
    flash(f'Auto-screened {screened_count} applications.', 'success')
    return redirect(url_for('hr.job_detail', job_id=job_id))


# ============== Interview Management ==============

@hr_bp.route('/applications/<int:application_id>/shortlist', methods=['POST'])
@login_required
@hr_required
def shortlist_application(application_id):
    """Shortlist an application."""
    application = Application.query.get_or_404(application_id)
    
    # Check if already shortlisted
    if application.shortlist:
        flash('Application is already shortlisted.', 'warning')
        return redirect(url_for('hr.application_detail', application_id=application_id))
    
    # Create shortlist entry
    shortlist = Shortlist(
        application_id=application.id,
        job_id=application.job_id,
        shortlisted_by=current_user.id,
        notes=request.form.get('notes', '')
    )
    db.session.add(shortlist)
    
    # Update application status
    application.status = 'shortlisted'
    application.current_stage = 'Shortlisted'
    
    create_audit_log(
        user_id=current_user.id,
        action='SHORTLIST_APPLICATION',
        entity_type='Application',
        entity_id=application.id,
        new_values={'status': 'shortlisted'},
        ip_address=request.remote_addr
    )
    
    db.session.commit()
    
    # Send shortlist notification email
    try:
        send_status_update_email(application)
        current_app.logger.info(f'Shortlist notification sent for application {application_id}')
    except Exception as e:
        current_app.logger.error(f'Failed to send shortlist notification: {e}')
    
    flash('Application shortlisted successfully.', 'success')
    return redirect(url_for('hr.application_detail', application_id=application_id))


@hr_bp.route('/applications/<int:application_id>/reject', methods=['POST'])
@login_required
@hr_required
def reject_application(application_id):
    """Reject an application."""
    application = Application.query.get_or_404(application_id)
    
    # Check if already rejected
    if application.status == 'rejected':
        flash('Application is already rejected.', 'warning')
        return redirect(url_for('hr.application_detail', application_id=application_id))
    
    old_status = application.status
    application.status = 'rejected'
    application.current_stage = 'Rejected'
    
    # Add rejection notes if provided
    rejection_notes = request.form.get('notes', 'Application rejected by HR.')
    application.notes = (application.notes or '') + f"\n[Rejection] {rejection_notes}"
    
    create_audit_log(
        user_id=current_user.id,
        action='REJECT_APPLICATION',
        entity_type='Application',
        entity_id=application.id,
        old_values={'status': old_status},
        new_values={'status': 'rejected'},
        description=rejection_notes,
        ip_address=request.remote_addr
    )
    
    db.session.commit()
    
    # Send rejection email
    try:
        send_rejection_email(application)
        current_app.logger.info(f'Rejection notification sent for application {application_id}')
    except Exception as e:
        current_app.logger.error(f'Failed to send rejection notification: {e}')
    
    flash('Application rejected successfully.', 'success')
    return redirect(url_for('hr.application_detail', application_id=application_id))


@hr_bp.route('/interviews')
@login_required
@hr_required
def interviews_list():
    """List all interviews with filtering and calendar view."""
    view_type = request.args.get('view', 'list')  # list or calendar
    status_filter = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    query = Interview.query.order_by(Interview.scheduled_date.desc(), Interview.start_time)
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    if date_from:
        query = query.filter(Interview.scheduled_date >= date_from)
    
    if date_to:
        query = query.filter(Interview.scheduled_date <= date_to)
    
    interviews = query.all()
    
    # For calendar view, organize by date
    calendar_data = {}
    if view_type == 'calendar':
        for interview in interviews:
            date_key = interview.scheduled_date.strftime('%Y-%m-%d')
            if date_key not in calendar_data:
                calendar_data[date_key] = []
            calendar_data[date_key].append(interview)
    
    # Upcoming interviews (next 7 days)
    today = datetime.utcnow().date()
    week_ahead = today + timedelta(days=7)
    upcoming = Interview.query.filter(
        Interview.scheduled_date >= today,
        Interview.scheduled_date <= week_ahead,
        Interview.status == 'scheduled'
    ).order_by(Interview.scheduled_date, Interview.start_time).all()
    
    return render_template('interviews_list.html',
                           interviews=interviews,
                           calendar_data=calendar_data,
                           upcoming=upcoming,
                           view_type=view_type,
                           status_filter=status_filter)


@hr_bp.route('/interviews/<int:interview_id>')
@login_required
@hr_required
def interview_detail(interview_id):
    """View interview details."""
    interview = Interview.query.get_or_404(interview_id)
    
    # Get panel member details
    panel_members = []
    if interview.panel:
        panel_members = User.query.filter(User.id.in_(interview.panel)).all()
    
    return render_template('interview_detail.html', 
                           interview=interview,
                           panel_members=panel_members)


@hr_bp.route('/interviews/<int:interview_id>/reschedule', methods=['GET', 'POST'])
@login_required
@hr_required
def reschedule_interview(interview_id):
    """Reschedule an interview."""
    interview = Interview.query.get_or_404(interview_id)
    form = InterviewScheduleForm()
    
    hr_users = User.query.filter(User.role.in_(['hr_officer', 'manager', 'admin'])).all()
    form.panel_members.choices = [(u.id, u.full_name) for u in hr_users]
    
    if request.method == 'GET':
        form.scheduled_date.data = interview.scheduled_date
        form.start_time.data = interview.start_time
        form.end_time.data = interview.end_time
        form.interview_type.data = interview.interview_type
        form.location.data = interview.location
        form.panel_members.data = interview.panel or []
    
    if form.validate_on_submit():
        old_date = interview.scheduled_date
        old_time = interview.start_time
        
        interview.scheduled_date = form.scheduled_date.data
        interview.start_time = form.start_time.data
        interview.end_time = form.end_time.data
        interview.interview_type = form.interview_type.data
        interview.location = form.location.data
        interview.panel = form.panel_members.data if form.panel_members.data else None
        
        create_audit_log(
            user_id=current_user.id,
            action='RESCHEDULE_INTERVIEW',
            entity_type='Interview',
            entity_id=interview.id,
            old_values={'date': str(old_date), 'time': str(old_time)},
            new_values={'date': str(form.scheduled_date.data), 'time': str(form.start_time.data)},
            ip_address=request.remote_addr
        )
        
        db.session.commit()
        
        # Send rescheduled notification
        try:
            send_interview_invitation(interview, is_reschedule=True)
        except Exception as e:
            current_app.logger.error(f'Failed to send reschedule notification: {e}')
        
        flash('Interview rescheduled. Notification sent to applicant.', 'success')
        return redirect(url_for('hr.interview_detail', interview_id=interview_id))
    
    return render_template('reschedule_interview.html', form=form, interview=interview)


@hr_bp.route('/interviews/<int:interview_id>/cancel', methods=['POST'])
@login_required
@hr_required
def cancel_interview(interview_id):
    """Cancel an interview."""
    interview = Interview.query.get_or_404(interview_id)
    reason = request.form.get('reason', '')
    
    interview.status = 'cancelled'
    
    create_audit_log(
        user_id=current_user.id,
        action='CANCEL_INTERVIEW',
        entity_type='Interview',
        entity_id=interview.id,
        new_values={'reason': reason},
        ip_address=request.remote_addr
    )
    
    db.session.commit()
    
    # Send cancellation notification
    try:
        from app.utils.notifications import send_email
        send_email(
            to=interview.application.applicant.email,
            subject='Interview Cancelled - E-Recruitment Portal',
            body=f"""Dear {interview.application.applicant.full_name},

We regret to inform you that your interview scheduled for {interview.scheduled_date.strftime('%d %B %Y')} 
at {interview.start_time.strftime('%H:%M')} has been cancelled.

{f'Reason: {reason}' if reason else ''}

We will contact you shortly to reschedule.

Best regards,
HR Team"""
        )
    except Exception as e:
        current_app.logger.error(f'Failed to send cancellation notification: {e}')
    
    flash('Interview cancelled. Applicant has been notified.', 'info')
    return redirect(url_for('hr.interviews_list'))


@hr_bp.route('/interviews/<int:interview_id>/send-reminder', methods=['POST'])
@login_required
@hr_required
def send_interview_reminder(interview_id):
    """Send a reminder for an upcoming interview."""
    interview = Interview.query.get_or_404(interview_id)
    
    try:
        from app.utils.notifications import send_email
        send_email(
            to=interview.application.applicant.email,
            subject='Interview Reminder - E-Recruitment Portal',
            body=f"""Dear {interview.application.applicant.full_name},

This is a reminder about your upcoming interview:

Position: {interview.application.job.title}
Date: {interview.scheduled_date.strftime('%d %B %Y')}
Time: {interview.start_time.strftime('%H:%M')} - {interview.end_time.strftime('%H:%M')}
Type: {interview.interview_type.replace('_', ' ').title()}
Location: {interview.location}

Please ensure you are prepared and arrive/log in on time.

Best regards,
HR Team"""
        )
        flash('Reminder sent successfully.', 'success')
    except Exception as e:
        current_app.logger.error(f'Failed to send reminder: {e}')
        flash('Failed to send reminder.', 'danger')
    
    return redirect(url_for('hr.interview_detail', interview_id=interview_id))


@hr_bp.route('/applications/<int:application_id>/schedule-interview', methods=['GET', 'POST'])
@login_required
@hr_required
def schedule_interview(application_id):
    """Schedule an interview."""
    application = Application.query.get_or_404(application_id)
    form = InterviewScheduleForm()
    
    # Populate panel members dropdown
    hr_users = User.query.filter(User.role.in_(['hr_officer', 'manager', 'admin'])).all()
    form.panel_members.choices = [(u.id, u.full_name) for u in hr_users]
    
    if form.validate_on_submit():
        interview = Interview(
            application_id=application.id,
            scheduled_date=form.scheduled_date.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            interview_type=form.interview_type.data,
            location=form.location.data,
            panel=form.panel_members.data if form.panel_members.data else None,
            status='scheduled'
        )
        
        db.session.add(interview)
        
        application.current_stage = 'Interview Scheduled'
        
        create_audit_log(
            user_id=current_user.id,
            action='SCHEDULE_INTERVIEW',
            entity_type='Interview',
            entity_id=interview.id,
            new_values={
                'application_id': application_id,
                'date': str(form.scheduled_date.data),
                'time': str(form.start_time.data)
            },
            ip_address=request.remote_addr
        )
        
        db.session.commit()
        
        # Send interview invitation email
        try:
            send_interview_invitation(interview)
            current_app.logger.info(f'Interview invitation sent for application {application_id}')
        except Exception as e:
            current_app.logger.error(f'Failed to send interview invitation: {e}')
        
        flash('Interview scheduled successfully. Invitation email sent to applicant.', 'success')
        return redirect(url_for('hr.application_detail', application_id=application_id))
    
    return render_template('schedule_interview.html', form=form, application=application)


@hr_bp.route('/interviews/<int:interview_id>/feedback', methods=['GET', 'POST'])
@login_required
@hr_required
def interview_feedback(interview_id):
    """Record interview feedback."""
    interview = Interview.query.get_or_404(interview_id)
    form = InterviewFeedbackForm()
    
    if form.validate_on_submit():
        interview.score = form.score.data
        interview.feedback = form.feedback.data
        interview.status = form.status.data
        
        if form.status.data == 'completed':
            interview.application.interview_score = form.score.data
            interview.application.current_stage = 'Interviewed'
            interview.application.status = 'interviewed'
        
        create_audit_log(
            user_id=current_user.id,
            action='INTERVIEW_FEEDBACK',
            entity_type='Interview',
            entity_id=interview.id,
            new_values={'score': interview.score, 'status': interview.status},
            ip_address=request.remote_addr
        )
        
        db.session.commit()
        
        flash('Interview feedback recorded.', 'success')
        return redirect(url_for('hr.application_detail', 
                                application_id=interview.application_id))
    
    return render_template('interview_feedback.html', form=form, interview=interview)


# ============== Offer Management ==============

@hr_bp.route('/applications/<int:application_id>/create-offer', methods=['GET', 'POST'])
@login_required
@hr_required
def create_offer(application_id):
    """Create a job offer."""
    if current_user.role not in ('manager', 'admin'):
        flash('Only managers can create offers.', 'danger')
        return redirect(url_for('hr.application_detail', application_id=application_id))
    
    application = Application.query.get_or_404(application_id)
    
    # Check if offer already exists
    if application.offer:
        flash('An offer already exists for this application.', 'warning')
        return redirect(url_for('hr.application_detail', application_id=application_id))
    
    form = OfferForm()
    
    if form.validate_on_submit():
        offer = Offer(
            application_id=application.id,
            salary_offered=form.salary_offered.data,
            start_date_proposed=form.start_date_proposed.data,
            response_deadline=form.response_deadline.data,
            terms=form.terms.data,
            status='pending'
        )
        
        db.session.add(offer)
        
        application.status = 'offered'
        application.current_stage = 'Offer Extended'
        
        create_audit_log(
            user_id=current_user.id,
            action='CREATE_OFFER',
            entity_type='Offer',
            entity_id=offer.id,
            new_values={
                'application_id': application_id,
                'salary': form.salary_offered.data
            },
            ip_address=request.remote_addr
        )
        
        db.session.commit()
        
        # Send offer email
        try:
            send_offer_email(offer)
            current_app.logger.info(f'Offer email sent for application {application_id}')
        except Exception as e:
            current_app.logger.error(f'Failed to send offer email: {e}')
        
        flash('Job offer created and email sent to applicant.', 'success')
        return redirect(url_for('hr.application_detail', application_id=application_id))
    
    return render_template('create_offer.html', form=form, application=application)


# ============== Reports & Analytics ==============

@hr_bp.route('/reports')
@login_required
@hr_required
def reports():
    """Reports dashboard with comprehensive analytics."""
    form = ReportFilterForm()
    
    # Populate department choices
    departments = [d[0] for d in JobPosting.query.with_entities(JobPosting.department).distinct().all()]
    form.department.choices = [('', 'All Departments')] + [(d, d) for d in departments]
    
    # Date range filters
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    department = request.args.get('department', '')
    
    # Base queries
    job_query = JobPosting.query
    app_query = Application.query
    
    if department:
        job_query = job_query.filter_by(department=department)
        job_ids = [j.id for j in job_query.all()]
        app_query = app_query.filter(Application.job_id.in_(job_ids))
    
    if date_from:
        app_query = app_query.filter(Application.created_at >= date_from)
    if date_to:
        app_query = app_query.filter(Application.created_at <= date_to)
    
    # Calculate stats
    total_applications = app_query.count()
    total_jobs = job_query.count()
    hired_count = app_query.filter_by(status='offered').count()
    
    # Conversion rate (applications to offers)
    conversion_rate = (hired_count / total_applications * 100) if total_applications > 0 else 0
    
    stats = {
        'total_jobs': total_jobs,
        'total_applications': total_applications,
        'active_jobs': job_query.filter_by(status='published').count(),
        'hired': hired_count,
        'conversion_rate': round(conversion_rate, 1),
        'avg_applications_per_job': round(total_applications / total_jobs, 1) if total_jobs > 0 else 0
    }
    
    # Application status breakdown
    status_breakdown = {}
    for status in ['submitted', 'under_review', 'shortlisted', 'interviewed', 'offered', 'rejected', 'withdrawn']:
        count = app_query.filter_by(status=status).count()
        if count > 0:
            status_breakdown[status] = count
    
    # Department breakdown
    department_breakdown = {}
    for dept in departments:
        jobs_in_dept = JobPosting.query.filter_by(department=dept).all()
        count = sum(j.applications_count for j in jobs_in_dept)
        if count > 0:
            department_breakdown[dept] = count
    
    # Top jobs by applications
    top_jobs = job_query.order_by(JobPosting.applications_count.desc()).limit(5).all()
    
    # Employment Equity stats
    ee_stats = {
        'gender': {},
        'race': {},
        'disability': {'yes': 0, 'no': 0}
    }
    
    applicants_in_apps = db.session.query(User).join(Application, Application.applicant_id == User.id)
    if department:
        applicants_in_apps = applicants_in_apps.filter(Application.job_id.in_(job_ids))
    
    for user in applicants_in_apps.distinct():
        if user.gender:
            ee_stats['gender'][user.gender] = ee_stats['gender'].get(user.gender, 0) + 1
        if user.race:
            ee_stats['race'][user.race] = ee_stats['race'].get(user.race, 0) + 1
        if user.disability_status:
            ee_stats['disability']['yes'] += 1
        else:
            ee_stats['disability']['no'] += 1
    
    # Monthly trend (last 6 months)
    monthly_trend = []
    for i in range(5, -1, -1):
        month_start = datetime.utcnow().replace(day=1) - timedelta(days=i*30)
        month_end = month_start + timedelta(days=30)
        count = Application.query.filter(
            Application.created_at >= month_start,
            Application.created_at < month_end
        ).count()
        monthly_trend.append({
            'month': month_start.strftime('%b %Y'),
            'count': count
        })
    
    return render_template('reports.html', 
                           form=form,
                           stats=stats,
                           status_breakdown=status_breakdown,
                           department_breakdown=department_breakdown,
                           top_jobs=top_jobs,
                           ee_stats=ee_stats,
                           monthly_trend=monthly_trend,
                           department_filter=department)


@hr_bp.route('/reports/export/<report_type>')
@login_required
@hr_required
def export_report(report_type):
    """Export report data as CSV."""
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    if report_type == 'applications':
        writer.writerow(['Reference', 'Applicant', 'Email', 'Job', 'Department', 'Status', 'Date Applied'])
        
        applications = Application.query.join(JobPosting).order_by(Application.created_at.desc()).all()
        for app in applications:
            writer.writerow([
                app.application_reference,
                app.applicant.full_name,
                app.applicant.email,
                app.job.title,
                app.job.department,
                app.status.replace('_', ' ').title(),
                app.created_at.strftime('%Y-%m-%d')
            ])
    
    elif report_type == 'jobs':
        writer.writerow(['Reference', 'Title', 'Department', 'Status', 'Applications', 'Posted', 'Closing'])
        
        jobs = JobPosting.query.order_by(JobPosting.created_at.desc()).all()
        for job in jobs:
            writer.writerow([
                job.job_reference,
                job.title,
                job.department,
                job.status.replace('_', ' ').title(),
                job.applications_count,
                job.posting_date.strftime('%Y-%m-%d') if job.posting_date else '',
                job.closing_date.strftime('%Y-%m-%d')
            ])
    
    elif report_type == 'ee':
        writer.writerow(['Category', 'Value', 'Count'])
        
        # Gender
        for gender in ['male', 'female', 'other', 'prefer_not_to_say']:
            count = User.query.filter_by(gender=gender, role='applicant').count()
            if count > 0:
                writer.writerow(['Gender', gender.replace('_', ' ').title(), count])
        
        # Race
        for race in ['african', 'coloured', 'indian', 'white', 'other', 'prefer_not_to_say']:
            count = User.query.filter_by(race=race, role='applicant').count()
            if count > 0:
                writer.writerow(['Race', race.replace('_', ' ').title(), count])
        
        # Disability
        disability_count = User.query.filter_by(disability_status=True, role='applicant').count()
        writer.writerow(['Disability', 'Yes', disability_count])
    
    output.seek(0)
    
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'{report_type}_report_{datetime.utcnow().strftime("%Y%m%d")}.csv'
    )


@hr_bp.route('/reports/recruitment-funnel')
@login_required
@hr_required
def recruitment_funnel():
    """Show recruitment funnel visualization."""
    job_id = request.args.get('job_id', type=int)
    
    if job_id:
        job = JobPosting.query.get_or_404(job_id)
        apps = Application.query.filter_by(job_id=job_id)
    else:
        job = None
        apps = Application.query
    
    funnel = {
        'applications': apps.count(),
        'under_review': apps.filter(Application.status.in_(['under_review', 'shortlisted', 'interviewed', 'offered'])).count(),
        'shortlisted': apps.filter(Application.status.in_(['shortlisted', 'interviewed', 'offered'])).count(),
        'interviewed': apps.filter(Application.status.in_(['interviewed', 'offered'])).count(),
        'offered': apps.filter_by(status='offered').count()
    }
    
    jobs = JobPosting.query.filter(JobPosting.status.in_(['published', 'closed'])).all()
    
    return render_template('recruitment_funnel.html', funnel=funnel, job=job, jobs=jobs)


@hr_bp.route('/reports/time-to-hire')
@login_required
@hr_required
def time_to_hire_report():
    """Analyze time-to-hire metrics."""
    # Get applications that have reached offer stage
    offered_apps = Application.query.filter_by(status='offered').all()
    
    time_data = []
    for app in offered_apps:
        if app.offer and app.created_at:
            days = (app.offer.created_at - app.created_at).days
            time_data.append({
                'application': app,
                'days': days
            })
    
    # Calculate stats
    all_days = [t['days'] for t in time_data]
    avg_days = sum(all_days) / len(all_days) if all_days else 0
    min_days = min(all_days) if all_days else 0
    max_days = max(all_days) if all_days else 0
    
    # Group by department
    by_department = {}
    for t in time_data:
        dept = t['application'].job.department or 'Not Specified'
        if dept not in by_department:
            by_department[dept] = []
        by_department[dept].append(t['days'])
    
    dept_stats = []
    for dept, days in by_department.items():
        dept_stats.append({
            'department': dept,
            'count': len(days),
            'avg_days': round(sum(days) / len(days), 1)
        })
    dept_stats.sort(key=lambda x: x['avg_days'])
    
    # Recent hires
    recent_hires = []
    for t in sorted(time_data, key=lambda x: x['application'].offer.created_at, reverse=True)[:10]:
        app = t['application']
        recent_hires.append({
            'candidate': app.applicant.full_name,
            'job_title': app.job.title,
            'department': app.job.department,
            'applied_date': app.created_at,
            'hired_date': app.offer.created_at,
            'days_to_hire': t['days']
        })
    
    return render_template('time_to_hire.html', 
                           avg_days=round(avg_days, 1),
                           min_days=min_days,
                           max_days=max_days,
                           dept_stats=dept_stats,
                           recent_hires=recent_hires)


# ============== Admin Functions ==============

@hr_bp.route('/admin/users')
@login_required
@admin_required
def manage_users():
    """User management page."""
    page = request.args.get('page', 1, type=int)
    role_filter = request.args.get('role', '')
    
    query = User.query
    if role_filter:
        query = query.filter_by(role=role_filter)
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page,
        per_page=20,
        error_out=False
    )
    
    return render_template('manage_users.html', 
                           users=users.items,
                           pagination=users,
                           role_filter=role_filter)


@hr_bp.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Edit user role and status."""
    user = User.query.get_or_404(user_id)
    form = UserManagementForm(obj=user)
    
    if form.validate_on_submit():
        old_values = {'role': user.role, 'is_active': user.is_active}
        
        user.role = form.role.data
        user.is_active = form.is_active.data
        
        create_audit_log(
            user_id=current_user.id,
            action='UPDATE_USER',
            entity_type='User',
            entity_id=user.id,
            old_values=old_values,
            new_values={'role': user.role, 'is_active': user.is_active},
            ip_address=request.remote_addr
        )
        
        db.session.commit()
        
        flash(f'User {user.username} updated.', 'success')
        return redirect(url_for('hr.manage_users'))
    
    return render_template('edit_user.html', form=form, user=user)


@hr_bp.route('/admin/audit-log')
@login_required
@admin_required
def audit_log():
    """View audit log."""
    page = request.args.get('page', 1, type=int)
    
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).paginate(
        page=page,
        per_page=50,
        error_out=False
    )
    
    return render_template('audit_log.html', logs=logs.items, pagination=logs)


@hr_bp.route('/admin/staff/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_staff():
    """Create new staff account (HR Officer/Manager/Admin)."""
    form = CreateStaffForm()
    
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            phone=form.phone.data,
            role=form.role.data,
            is_active=True
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        
        create_audit_log(
            user_id=current_user.id,
            action='CREATE_STAFF',
            entity_type='User',
            entity_id=None,  # Will be set after commit
            new_values={
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'full_name': f"{user.first_name} {user.last_name}"
            },
            description=f"Admin created new {user.role} account: {user.email}",
            ip_address=request.remote_addr
        )
        
        db.session.commit()
        
        flash(f'Staff account for {user.full_name} ({user.role}) created successfully!', 'success')
        return redirect(url_for('hr.manage_users'))
    
    return render_template('create_staff.html', form=form)


@hr_bp.route('/admin/staff/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_staff(user_id):
    """Delete a staff account."""
    user = User.query.get_or_404(user_id)
    
    # Prevent deleting yourself
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('hr.manage_users'))
    
    # Only allow deleting staff (not applicants)
    if user.role == 'applicant':
        flash('Use the applicants page to manage applicant accounts.', 'warning')
        return redirect(url_for('hr.manage_users'))
    
    user_info = {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role,
        'full_name': user.full_name
    }
    
    create_audit_log(
        user_id=current_user.id,
        action='DELETE_STAFF',
        entity_type='User',
        entity_id=user.id,
        old_values=user_info,
        description=f"Admin deleted {user.role} account: {user.email}",
        ip_address=request.remote_addr
    )
    
    db.session.delete(user)
    db.session.commit()
    
    flash(f'Staff account for {user_info["full_name"]} has been deleted.', 'success')
    return redirect(url_for('hr.manage_users'))


@hr_bp.route('/admin/applicants')
@login_required
@admin_required
def view_applicants():
    """View all registered applicants."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')  # active, inactive
    
    query = User.query.filter_by(role='applicant')
    
    if search:
        query = query.filter(
            db.or_(
                User.email.ilike(f'%{search}%'),
                User.first_name.ilike(f'%{search}%'),
                User.last_name.ilike(f'%{search}%'),
                User.id_number.ilike(f'%{search}%')
            )
        )
    
    if status_filter == 'active':
        query = query.filter_by(is_active=True)
    elif status_filter == 'inactive':
        query = query.filter_by(is_active=False)
    
    applicants = query.order_by(User.created_at.desc()).paginate(
        page=page,
        per_page=20,
        error_out=False
    )
    
    # Get application count for each applicant
    applicant_stats = {}
    for applicant in applicants.items:
        applicant_stats[applicant.id] = {
            'total_applications': Application.query.filter_by(applicant_id=applicant.id).count(),
            'pending': Application.query.filter_by(applicant_id=applicant.id, status='submitted').count(),
            'shortlisted': Application.query.filter_by(applicant_id=applicant.id, status='shortlisted').count()
        }
    
    return render_template('view_applicants.html',
                           applicants=applicants.items,
                           pagination=applicants,
                           applicant_stats=applicant_stats,
                           search=search,
                           status_filter=status_filter)


@hr_bp.route('/admin/applicants/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_applicant_status(user_id):
    """Activate or deactivate an applicant account."""
    user = User.query.get_or_404(user_id)
    
    if user.role != 'applicant':
        flash('This action is only for applicant accounts.', 'warning')
        return redirect(url_for('hr.view_applicants'))
    
    old_status = user.is_active
    user.is_active = not user.is_active
    
    create_audit_log(
        user_id=current_user.id,
        action='TOGGLE_APPLICANT_STATUS',
        entity_type='User',
        entity_id=user.id,
        old_values={'is_active': old_status},
        new_values={'is_active': user.is_active},
        description=f"Admin {'activated' if user.is_active else 'deactivated'} applicant: {user.email}",
        ip_address=request.remote_addr
    )
    
    db.session.commit()
    
    status_text = 'activated' if user.is_active else 'deactivated'
    flash(f'Applicant {user.full_name} has been {status_text}.', 'success')
    return redirect(url_for('hr.view_applicants'))


@hr_bp.route('/admin/activity')
@login_required
@admin_required
def live_activity():
    """View real-time user activity in the system."""
    # Get recent activities (last 24 hours)
    since = datetime.utcnow() - timedelta(hours=24)
    
    activities = UserActivity.query.filter(
        UserActivity.timestamp >= since
    ).order_by(UserActivity.timestamp.desc()).limit(100).all()
    
    # Get currently active users (active in last 15 minutes)
    active_since = datetime.utcnow() - timedelta(minutes=15)
    active_users = db.session.query(User).join(UserActivity).filter(
        UserActivity.timestamp >= active_since
    ).distinct().all()
    
    # Get activity summary by type
    activity_summary = db.session.query(
        UserActivity.activity_type,
        db.func.count(UserActivity.id).label('count')
    ).filter(
        UserActivity.timestamp >= since
    ).group_by(UserActivity.activity_type).all()
    
    # Get recent logins
    recent_logins = UserActivity.query.filter(
        UserActivity.activity_type == 'login',
        UserActivity.timestamp >= since
    ).order_by(UserActivity.timestamp.desc()).limit(20).all()
    
    return render_template('live_activity.html',
                           activities=activities,
                           active_users=active_users,
                           activity_summary=dict(activity_summary),
                           recent_logins=recent_logins)


@hr_bp.route('/admin/activity/api')
@login_required
@admin_required
def activity_api():
    """API endpoint for real-time activity updates."""
    since = request.args.get('since', None)
    
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except:
            since_dt = datetime.utcnow() - timedelta(minutes=5)
    else:
        since_dt = datetime.utcnow() - timedelta(minutes=5)
    
    activities = UserActivity.query.filter(
        UserActivity.timestamp >= since_dt
    ).order_by(UserActivity.timestamp.desc()).limit(50).all()
    
    return jsonify({
        'activities': [{
            'id': a.id,
            'user': a.user.full_name if a.user else 'Unknown',
            'user_role': a.user.role if a.user else 'unknown',
            'activity_type': a.activity_type,
            'page': a.page,
            'description': a.description,
            'timestamp': a.timestamp.isoformat(),
            'ip_address': a.ip_address
        } for a in activities],
        'server_time': datetime.utcnow().isoformat()
    })


# ============== Document Management ==============

@hr_bp.route('/documents')
@login_required
@hr_required
def document_library():
    """Document library - all uploaded documents."""
    page = request.args.get('page', 1, type=int)
    doc_type = request.args.get('type', '')
    search = request.args.get('search', '')
    
    query = Document.query
    
    if doc_type:
        query = query.filter_by(document_type=doc_type)
    
    if search:
        query = query.filter(Document.file_name.ilike(f'%{search}%'))
    
    documents = query.order_by(Document.uploaded_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('document_library.html', 
                           documents=documents,
                           doc_type=doc_type,
                           search=search)


@hr_bp.route('/documents/<int:doc_id>')
@login_required
@hr_required
def download_document(doc_id):
    """Download a document by ID."""
    document = Document.query.get_or_404(doc_id)
    
    # Determine subfolder
    if document.application_id:
        subfolder = f'applications/{document.application_id}'
    else:
        subfolder = 'documents'
    
    upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    actual_filename = document.local_path if document.local_path else document.file_name
    
    return send_from_directory(upload_path, actual_filename, as_attachment=True, 
                               download_name=document.file_name)


@hr_bp.route('/documents/<int:doc_id>/preview')
@login_required
@hr_required
def preview_document(doc_id):
    """Preview a document (inline view)."""
    document = Document.query.get_or_404(doc_id)
    
    # Determine subfolder
    if document.application_id:
        subfolder = f'applications/{document.application_id}'
    else:
        subfolder = 'documents'
    
    upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    actual_filename = document.local_path if document.local_path else document.file_name
    
    return send_from_directory(upload_path, actual_filename, as_attachment=False)


@hr_bp.route('/applications/<int:application_id>/documents/download-all')
@login_required
@hr_required
def download_all_documents(application_id):
    """Download all documents for an application as a ZIP file."""
    application = Application.query.get_or_404(application_id)
    
    if not application.documents:
        flash('No documents to download.', 'warning')
        return redirect(url_for('hr.application_detail', application_id=application_id))
    
    # Create a ZIP file in memory
    memory_file = io.BytesIO()
    
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for doc in application.documents:
            subfolder = f'applications/{application.id}'
            upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
            actual_filename = doc.local_path if doc.local_path else doc.file_name
            file_path = os.path.join(upload_path, actual_filename)
            
            if os.path.exists(file_path):
                # Use document type as prefix for clarity
                archive_name = f"{doc.document_type}_{doc.file_name}"
                zf.write(file_path, archive_name)
    
    memory_file.seek(0)
    
    # Generate ZIP filename
    applicant_name = application.applicant.full_name.replace(' ', '_')
    zip_filename = f"{applicant_name}_{application.application_reference}_documents.zip"
    
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=zip_filename
    )


@hr_bp.route('/jobs/<int:job_id>/documents/download-all')
@login_required
@hr_required
def download_job_documents(job_id):
    """Download all documents for all applications of a job."""
    job = JobPosting.query.get_or_404(job_id)
    
    applications = Application.query.filter_by(job_id=job_id).all()
    
    if not applications:
        flash('No applications found.', 'warning')
        return redirect(url_for('hr.job_detail', job_id=job_id))
    
    # Create a ZIP file in memory
    memory_file = io.BytesIO()
    
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for app in applications:
            if app.documents:
                applicant_name = app.applicant.full_name.replace(' ', '_')
                folder_prefix = f"{applicant_name}_{app.application_reference}"
                
                for doc in app.documents:
                    subfolder = f'applications/{app.id}'
                    upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
                    actual_filename = doc.local_path if doc.local_path else doc.file_name
                    file_path = os.path.join(upload_path, actual_filename)
                    
                    if os.path.exists(file_path):
                        archive_name = f"{folder_prefix}/{doc.document_type}_{doc.file_name}"
                        zf.write(file_path, archive_name)
    
    memory_file.seek(0)
    
    # Generate ZIP filename
    job_title = job.title.replace(' ', '_')[:30]
    zip_filename = f"{job_title}_all_documents.zip"
    
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=zip_filename
    )


# ============== Assessment Management ==============

@hr_bp.route('/assessments')
@login_required
@hr_required
def assessments_list():
    """List all assessments."""
    from app.models import Assessment
    
    page = request.args.get('page', 1, type=int)
    job_id = request.args.get('job_id', type=int)
    
    query = Assessment.query.order_by(Assessment.created_at.desc())
    
    if job_id:
        query = query.filter_by(job_id=job_id)
    
    assessments = query.paginate(page=page, per_page=20)
    jobs = JobPosting.query.filter(JobPosting.status.in_(['published', 'closed'])).all()
    
    return render_template('assessments_list.html', 
                           assessments=assessments, 
                           jobs=jobs, 
                           selected_job=job_id)


@hr_bp.route('/assessments/create', methods=['GET', 'POST'])
@login_required
@hr_required
def create_assessment():
    """Create a new assessment."""
    from app.models import Assessment
    
    if request.method == 'POST':
        job_id = request.form.get('job_id', type=int)
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        instructions = request.form.get('instructions', '').strip()
        time_limit = request.form.get('time_limit_minutes', type=int)
        pass_score = request.form.get('pass_score', 50.0, type=float)
        max_attempts = request.form.get('max_attempts', 1, type=int)
        shuffle_questions = request.form.get('shuffle_questions') == 'on'
        show_results = request.form.get('show_results_immediately') == 'on'
        is_mandatory = request.form.get('is_mandatory') == 'on'
        
        if not job_id or not title:
            flash('Job and title are required.', 'danger')
            return redirect(url_for('hr.create_assessment'))
        
        assessment = Assessment(
            job_id=job_id,
            title=title,
            description=description,
            instructions=instructions,
            time_limit_minutes=time_limit if time_limit and time_limit > 0 else None,
            pass_score=pass_score,
            max_attempts=max_attempts,
            shuffle_questions=shuffle_questions,
            show_results_immediately=show_results,
            is_mandatory=is_mandatory,
            created_by=current_user.id
        )
        
        db.session.add(assessment)
        db.session.commit()
        
        flash(f'Assessment "{title}" created successfully!', 'success')
        return redirect(url_for('hr.manage_questions', assessment_id=assessment.id))
    
    jobs = JobPosting.query.filter(JobPosting.status.in_(['draft', 'published'])).all()
    return render_template('assessment_create.html', jobs=jobs)


@hr_bp.route('/assessments/<int:assessment_id>')
@login_required
@hr_required
def assessment_detail(assessment_id):
    """View assessment details and results."""
    from app.models import Assessment, CandidateAssessment
    
    assessment = Assessment.query.get_or_404(assessment_id)
    
    # Get all candidate attempts
    attempts = CandidateAssessment.query.filter_by(assessment_id=assessment_id)\
        .order_by(CandidateAssessment.completed_at.desc()).all()
    
    # Calculate statistics
    completed_attempts = [a for a in attempts if a.status == 'completed']
    total_attempts = len(completed_attempts)
    passed_count = len([a for a in completed_attempts if a.passed])
    avg_score = sum(a.score for a in completed_attempts) / total_attempts if total_attempts > 0 else 0
    
    stats = {
        'total_attempts': total_attempts,
        'passed': passed_count,
        'failed': total_attempts - passed_count,
        'pass_rate': (passed_count / total_attempts * 100) if total_attempts > 0 else 0,
        'avg_score': avg_score
    }
    
    return render_template('assessment_detail.html', 
                           assessment=assessment, 
                           attempts=attempts,
                           stats=stats)


@hr_bp.route('/assessments/<int:assessment_id>/edit', methods=['GET', 'POST'])
@login_required
@hr_required
def edit_assessment(assessment_id):
    """Edit assessment settings."""
    from app.models import Assessment
    
    assessment = Assessment.query.get_or_404(assessment_id)
    
    if request.method == 'POST':
        assessment.title = request.form.get('title', '').strip()
        assessment.description = request.form.get('description', '').strip()
        assessment.instructions = request.form.get('instructions', '').strip()
        time_limit = request.form.get('time_limit_minutes', type=int)
        assessment.time_limit_minutes = time_limit if time_limit and time_limit > 0 else None
        assessment.pass_score = request.form.get('pass_score', 50.0, type=float)
        assessment.max_attempts = request.form.get('max_attempts', 1, type=int)
        assessment.shuffle_questions = request.form.get('shuffle_questions') == 'on'
        assessment.show_results_immediately = request.form.get('show_results_immediately') == 'on'
        assessment.is_mandatory = request.form.get('is_mandatory') == 'on'
        assessment.is_active = request.form.get('is_active') == 'on'
        
        db.session.commit()
        flash('Assessment updated successfully!', 'success')
        return redirect(url_for('hr.assessment_detail', assessment_id=assessment_id))
    
    return render_template('assessment_edit.html', assessment=assessment)


@hr_bp.route('/assessments/<int:assessment_id>/questions', methods=['GET', 'POST'])
@login_required
@hr_required
def manage_questions(assessment_id):
    """Manage assessment questions."""
    from app.models import Assessment, AssessmentQuestion, QuestionOption
    
    assessment = Assessment.query.get_or_404(assessment_id)
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_question':
            question_text = request.form.get('question_text', '').strip()
            question_type = request.form.get('question_type', 'multiple_choice')
            points = request.form.get('points', 1.0, type=float)
            expected_answer = request.form.get('expected_answer', '').strip()
            
            # Get max order
            max_order = db.session.query(db.func.max(AssessmentQuestion.order))\
                .filter_by(assessment_id=assessment_id).scalar() or 0
            
            question = AssessmentQuestion(
                assessment_id=assessment_id,
                question_text=question_text,
                question_type=question_type,
                points=points,
                expected_answer=expected_answer if question_type == 'text' else None,
                order=max_order + 1
            )
            db.session.add(question)
            db.session.commit()
            
            # Add options for multiple choice / true-false
            if question_type in ['multiple_choice', 'multiple_select']:
                options = request.form.getlist('options[]')
                correct_indices = request.form.getlist('correct[]')
                
                for idx, option_text in enumerate(options):
                    if option_text.strip():
                        is_correct = str(idx) in correct_indices
                        option = QuestionOption(
                            question_id=question.id,
                            option_text=option_text.strip(),
                            is_correct=is_correct,
                            order=idx
                        )
                        db.session.add(option)
                db.session.commit()
            
            elif question_type == 'true_false':
                correct_answer = request.form.get('correct_tf', 'true')
                for idx, text in enumerate(['True', 'False']):
                    option = QuestionOption(
                        question_id=question.id,
                        option_text=text,
                        is_correct=(text.lower() == correct_answer),
                        order=idx
                    )
                    db.session.add(option)
                db.session.commit()
            
            flash('Question added successfully!', 'success')
        
        elif action == 'delete_question':
            question_id = request.form.get('question_id', type=int)
            question = AssessmentQuestion.query.get_or_404(question_id)
            db.session.delete(question)
            db.session.commit()
            flash('Question deleted.', 'info')
        
        elif action == 'reorder':
            order_data = request.form.get('order_data', '')
            if order_data:
                for item in order_data.split(','):
                    qid, new_order = item.split(':')
                    q = AssessmentQuestion.query.get(int(qid))
                    if q:
                        q.order = int(new_order)
                db.session.commit()
        
        return redirect(url_for('hr.manage_questions', assessment_id=assessment_id))
    
    questions = assessment.questions.order_by(AssessmentQuestion.order).all()
    return render_template('assessment_questions.html', assessment=assessment, questions=questions)


@hr_bp.route('/assessments/<int:assessment_id>/delete', methods=['POST'])
@login_required
@hr_required
def delete_assessment(assessment_id):
    """Delete an assessment."""
    from app.models import Assessment
    
    assessment = Assessment.query.get_or_404(assessment_id)
    job_id = assessment.job_id
    
    # Check if there are any completed attempts
    if assessment.candidate_assessments.filter_by(status='completed').count() > 0:
        flash('Cannot delete assessment with completed attempts. Deactivate instead.', 'warning')
        return redirect(url_for('hr.assessment_detail', assessment_id=assessment_id))
    
    db.session.delete(assessment)
    db.session.commit()
    
    flash('Assessment deleted.', 'info')
    return redirect(url_for('hr.assessments_list'))


@hr_bp.route('/assessments/results/<int:attempt_id>')
@login_required
@hr_required
def view_assessment_result(attempt_id):
    """View detailed results of a candidate's assessment attempt."""
    from app.models import CandidateAssessment, CandidateAnswer
    
    attempt = CandidateAssessment.query.get_or_404(attempt_id)
    answers = CandidateAnswer.query.filter_by(candidate_assessment_id=attempt_id).all()
    
    return render_template('assessment_result_detail.html', attempt=attempt, answers=answers)

# ============== Communication Tools ==============

@hr_bp.route('/messages')
@login_required
@hr_required
def messages_inbox():
    """HR Messaging inbox."""
    page = request.args.get('page', 1, type=int)
    view = request.args.get('view', 'inbox')  # inbox, sent, archived
    
    if view == 'sent':
        messages = Message.query.filter_by(
            sender_id=current_user.id,
            is_deleted_by_sender=False
        ).order_by(Message.created_at.desc())
    elif view == 'archived':
        messages = Message.query.filter_by(
            recipient_id=current_user.id,
            is_archived=True,
            is_deleted_by_recipient=False
        ).order_by(Message.created_at.desc())
    else:  # inbox
        messages = Message.query.filter_by(
            recipient_id=current_user.id,
            is_archived=False,
            is_deleted_by_recipient=False
        ).order_by(Message.created_at.desc())
    
    messages = messages.paginate(page=page, per_page=20, error_out=False)
    unread_count = Message.get_unread_count(current_user.id)
    
    return render_template('messages/inbox.html', 
                           messages=messages, 
                           view=view,
                           unread_count=unread_count)


@hr_bp.route('/messages/compose', methods=['GET', 'POST'])
@login_required
@hr_required
def compose_message():
    """Compose a new message."""
    if request.method == 'POST':
        recipient_id = request.form.get('recipient_id', type=int)
        subject = request.form.get('subject', '').strip()
        body = request.form.get('body', '').strip()
        message_type = request.form.get('message_type', 'general')
        application_id = request.form.get('application_id', type=int)
        send_email = request.form.get('send_email') == 'on'
        
        if not recipient_id or not subject or not body:
            flash('Please fill in all required fields.', 'warning')
            return redirect(url_for('hr.compose_message'))
        
        recipient = User.query.get_or_404(recipient_id)
        
        # Create message
        message = Message(
            sender_id=current_user.id,
            recipient_id=recipient_id,
            subject=subject,
            body=body,
            message_type=message_type,
            application_id=application_id if application_id else None
        )
        db.session.add(message)
        db.session.commit()
        
        # Send email notification if requested
        if send_email:
            try:
                from flask_mail import Message as MailMessage
                from app import mail
                
                msg = MailMessage(
                    subject=f'New Message: {subject}',
                    recipients=[recipient.email],
                    html=render_template('emails/new_message.html',
                                         sender=current_user,
                                         subject=subject,
                                         body=body)
                )
                mail.send(msg)
            except Exception as e:
                current_app.logger.error(f'Failed to send email notification: {e}')
        
        flash('Message sent successfully!', 'success')
        return redirect(url_for('hr.messages_inbox', view='sent'))
    
    # GET - show compose form
    recipient_id = request.args.get('recipient_id', type=int)
    application_id = request.args.get('application_id', type=int)
    reply_to = request.args.get('reply_to', type=int)
    
    recipient = None
    application = None
    parent_message = None
    
    if recipient_id:
        recipient = User.query.get(recipient_id)
    if application_id:
        application = Application.query.get(application_id)
        if application and not recipient:
            recipient = application.applicant
    if reply_to:
        parent_message = Message.query.get(reply_to)
        if parent_message:
            recipient = parent_message.sender
    
    # Get applicants for recipient dropdown
    applicants = User.query.filter_by(role='applicant').order_by(User.last_name, User.first_name).all()
    
    # Get message templates
    templates = MessageTemplate.query.filter_by(is_active=True).all()
    
    return render_template('messages/compose.html',
                           recipient=recipient,
                           application=application,
                           parent_message=parent_message,
                           applicants=applicants,
                           templates=templates)


@hr_bp.route('/messages/<int:message_id>')
@login_required
@hr_required
def view_message(message_id):
    """View a specific message."""
    message = Message.query.get_or_404(message_id)
    
    # Check permission
    if message.sender_id != current_user.id and message.recipient_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('hr.messages_inbox'))
    
    # Mark as read if recipient
    if message.recipient_id == current_user.id and not message.is_read:
        message.mark_as_read()
    
    # Get conversation thread
    thread = []
    if message.parent_id:
        thread = Message.query.filter_by(parent_id=message.parent_id).order_by(Message.created_at).all()
    
    replies = Message.query.filter_by(parent_id=message.id).order_by(Message.created_at).all()
    
    return render_template('messages/view.html', 
                           message=message, 
                           thread=thread,
                           replies=replies)


@hr_bp.route('/messages/<int:message_id>/action', methods=['POST'])
@login_required
@hr_required
def message_action(message_id):
    """Perform action on message (archive, delete, etc.)."""
    message = Message.query.get_or_404(message_id)
    action = request.form.get('action')
    
    if message.recipient_id != current_user.id and message.sender_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('hr.messages_inbox'))
    
    if action == 'archive':
        if message.recipient_id == current_user.id:
            message.is_archived = True
            flash('Message archived.', 'info')
    elif action == 'unarchive':
        if message.recipient_id == current_user.id:
            message.is_archived = False
            flash('Message restored.', 'info')
    elif action == 'delete':
        if message.sender_id == current_user.id:
            message.is_deleted_by_sender = True
        if message.recipient_id == current_user.id:
            message.is_deleted_by_recipient = True
        flash('Message deleted.', 'info')
    elif action == 'mark_unread':
        message.is_read = False
        message.read_at = None
        flash('Message marked as unread.', 'info')
    
    db.session.commit()
    return redirect(request.referrer or url_for('hr.messages_inbox'))


@hr_bp.route('/messages/templates')
@login_required
@hr_required
def message_templates():
    """Manage message templates."""
    templates = MessageTemplate.query.filter_by(created_by=current_user.id).order_by(
        MessageTemplate.template_type, MessageTemplate.name
    ).all()
    
    return render_template('messages/templates.html', templates=templates)


@hr_bp.route('/messages/templates/create', methods=['GET', 'POST'])
@login_required
@hr_required
def create_template():
    """Create a new message template."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        subject = request.form.get('subject', '').strip()
        body = request.form.get('body', '').strip()
        template_type = request.form.get('template_type', 'general')
        
        if not name or not subject or not body:
            flash('Please fill in all required fields.', 'warning')
            return redirect(url_for('hr.create_template'))
        
        template = MessageTemplate(
            name=name,
            subject=subject,
            body=body,
            template_type=template_type,
            created_by=current_user.id
        )
        db.session.add(template)
        db.session.commit()
        
        flash('Template created successfully!', 'success')
        return redirect(url_for('hr.message_templates'))
    
    return render_template('messages/template_form.html', template=None)


@hr_bp.route('/messages/templates/<int:template_id>/edit', methods=['GET', 'POST'])
@login_required
@hr_required
def edit_template(template_id):
    """Edit a message template."""
    template = MessageTemplate.query.get_or_404(template_id)
    
    if template.created_by != current_user.id and current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('hr.message_templates'))
    
    if request.method == 'POST':
        template.name = request.form.get('name', '').strip()
        template.subject = request.form.get('subject', '').strip()
        template.body = request.form.get('body', '').strip()
        template.template_type = request.form.get('template_type', 'general')
        template.is_active = request.form.get('is_active') == 'on'
        
        if not template.name or not template.subject or not template.body:
            flash('Please fill in all required fields.', 'warning')
            return redirect(url_for('hr.edit_template', template_id=template_id))
        
        db.session.commit()
        flash('Template updated successfully!', 'success')
        return redirect(url_for('hr.message_templates'))
    
    return render_template('messages/template_form.html', template=template)


@hr_bp.route('/messages/templates/<int:template_id>/delete', methods=['POST'])
@login_required
@hr_required
def delete_template(template_id):
    """Delete a message template."""
    template = MessageTemplate.query.get_or_404(template_id)
    
    if template.created_by != current_user.id and current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('hr.message_templates'))
    
    db.session.delete(template)
    db.session.commit()
    flash('Template deleted.', 'info')
    return redirect(url_for('hr.message_templates'))


@hr_bp.route('/api/templates/<int:template_id>')
@login_required
@hr_required
def get_template(template_id):
    """Get template content for AJAX."""
    template = MessageTemplate.query.get_or_404(template_id)
    
    return jsonify({
        'subject': template.subject,
        'body': template.body,
        'template_type': template.template_type
    })


@hr_bp.route('/bulk-notifications')
@login_required
@hr_required
def bulk_notifications():
    """List of bulk notifications."""
    page = request.args.get('page', 1, type=int)
    
    notifications = BulkNotification.query.order_by(
        BulkNotification.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    
    return render_template('messages/bulk_notifications.html', notifications=notifications)


@hr_bp.route('/bulk-notifications/create', methods=['GET', 'POST'])
@login_required
@hr_required
def create_bulk_notification():
    """Create and send bulk notification."""
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        body = request.form.get('body', '').strip()
        target_type = request.form.get('target_type', 'all_applicants')
        target_job_id = request.form.get('target_job_id', type=int)
        target_status = request.form.get('target_status', '')
        send_email = request.form.get('send_email') == 'on'
        send_internal = request.form.get('send_internal') == 'on'
        
        if not subject or not body:
            flash('Please fill in all required fields.', 'warning')
            return redirect(url_for('hr.create_bulk_notification'))
        
        # Determine recipients
        recipients = []
        if target_type == 'all_applicants':
            recipients = User.query.filter_by(role='applicant', is_active=True).all()
        elif target_type == 'job_applicants' and target_job_id:
            apps = Application.query.filter_by(job_id=target_job_id).all()
            recipients = [app.applicant for app in apps]
        elif target_type == 'status_group' and target_status:
            apps = Application.query.filter_by(status=target_status).all()
            recipients = list(set([app.applicant for app in apps]))
        
        if not recipients:
            flash('No recipients match the criteria.', 'warning')
            return redirect(url_for('hr.create_bulk_notification'))
        
        # Create bulk notification record
        notification = BulkNotification(
            subject=subject,
            body=body,
            target_type=target_type,
            target_job_id=target_job_id if target_job_id else None,
            target_status=target_status if target_status else None,
            send_email=send_email,
            send_internal=send_internal,
            total_recipients=len(recipients),
            status='sending',
            created_by=current_user.id
        )
        db.session.add(notification)
        db.session.commit()
        
        # Send notifications
        sent_count = 0
        failed_count = 0
        
        for recipient in recipients:
            try:
                # Create internal message
                if send_internal:
                    message = Message(
                        sender_id=current_user.id,
                        recipient_id=recipient.id,
                        subject=subject,
                        body=body,
                        message_type='general'
                    )
                    db.session.add(message)
                
                # Send email
                if send_email:
                    from flask_mail import Message as MailMessage
                    from app import mail
                    
                    msg = MailMessage(
                        subject=subject,
                        recipients=[recipient.email],
                        html=render_template('emails/bulk_notification.html',
                                             recipient=recipient,
                                             subject=subject,
                                             body=body)
                    )
                    mail.send(msg)
                
                sent_count += 1
            except Exception as e:
                current_app.logger.error(f'Failed to send to {recipient.email}: {e}')
                failed_count += 1
        
        notification.sent_count = sent_count
        notification.failed_count = failed_count
        notification.status = 'completed'
        notification.sent_at = datetime.utcnow()
        db.session.commit()
        
        flash(f'Bulk notification sent to {sent_count} recipients ({failed_count} failed).', 'success')
        return redirect(url_for('hr.bulk_notifications'))
    
    # GET - show form
    jobs = JobPosting.query.filter(JobPosting.status.in_(['published', 'draft', 'closed'])).all()
    statuses = ['submitted', 'under_review', 'shortlisted', 'interview_scheduled', 
                'interviewed', 'offered', 'rejected', 'hired', 'withdrawn']
    templates = MessageTemplate.query.filter_by(is_active=True).all()
    
    return render_template('messages/bulk_notification_form.html',
                           jobs=jobs,
                           statuses=statuses,
                           templates=templates)


# ==================== WORKFLOW AUTOMATION ROUTES ====================

@hr_bp.route('/workflows')
@login_required
@hr_required
def workflows():
    """View all workflow rules."""
    rules = WorkflowRule.query.order_by(WorkflowRule.priority.desc(), WorkflowRule.name).all()
    
    # Get execution stats for each rule
    rule_stats = {}
    for rule in rules:
        total = rule.executions.count()
        completed = rule.executions.filter_by(status='completed').count()
        failed = rule.executions.filter_by(status='failed').count()
        rule_stats[rule.id] = {
            'total': total,
            'completed': completed,
            'failed': failed
        }
    
    return render_template('workflows/rules.html', 
                          rules=rules, 
                          rule_stats=rule_stats)


@hr_bp.route('/workflows/create', methods=['GET', 'POST'])
@login_required
@hr_required
def create_workflow():
    """Create a new workflow rule."""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        trigger_type = request.form.get('trigger_type')
        trigger_status = request.form.get('trigger_status')
        trigger_days = request.form.get('trigger_days', type=int)
        trigger_score = request.form.get('trigger_score', type=int)
        action_type = request.form.get('action_type')
        action_status = request.form.get('action_status')
        action_template_id = request.form.get('action_template_id', type=int)
        condition_job_id = request.form.get('condition_job_id', type=int)
        condition_min_score = request.form.get('condition_min_score', type=int)
        condition_max_score = request.form.get('condition_max_score', type=int)
        priority = request.form.get('priority', 0, type=int)
        is_active = request.form.get('is_active') == 'on'
        
        # Build action config from form
        action_config = {}
        if action_type in ['send_email', 'send_notification']:
            action_config['subject'] = request.form.get('email_subject', '')
            action_config['body'] = request.form.get('email_body', '')
        elif action_type == 'create_task':
            action_config['task_name'] = request.form.get('task_name', '')
            action_config['description'] = request.form.get('task_description', '')
            action_config['days'] = request.form.get('task_days', 3, type=int)
        elif action_type == 'schedule_reminder':
            action_config['reminder_text'] = request.form.get('reminder_text', '')
            action_config['days'] = request.form.get('reminder_days', 7, type=int)
        
        if trigger_type == 'time_based':
            action_config['time_reference'] = request.form.get('time_reference', 'application_date')
        
        rule = WorkflowRule(
            name=name,
            description=description,
            trigger_type=trigger_type,
            trigger_status=trigger_status if trigger_status else None,
            trigger_days=trigger_days,
            trigger_score=trigger_score,
            action_type=action_type,
            action_status=action_status if action_status else None,
            action_template_id=action_template_id if action_template_id else None,
            action_config=action_config if action_config else None,
            condition_job_id=condition_job_id if condition_job_id else None,
            condition_min_score=condition_min_score,
            condition_max_score=condition_max_score,
            priority=priority,
            is_active=is_active,
            created_by=current_user.id
        )
        
        db.session.add(rule)
        db.session.commit()
        
        create_audit_log(current_user.id, 'create', 'workflow_rule', rule.id, 
                        {'name': name, 'trigger': trigger_type, 'action': action_type})
        
        flash(f'Workflow rule "{name}" created successfully.', 'success')
        return redirect(url_for('hr.workflows'))
    
    # GET - show form
    jobs = JobPosting.query.filter(JobPosting.status.in_(['published', 'draft'])).all()
    templates = MessageTemplate.query.filter_by(is_active=True).all()
    statuses = ['submitted', 'under_review', 'shortlisted', 'interview_scheduled', 
                'interviewed', 'offered', 'rejected', 'hired', 'withdrawn']
    
    return render_template('workflows/rule_form.html',
                          rule=None,
                          jobs=jobs,
                          templates=templates,
                          statuses=statuses)


@hr_bp.route('/workflows/<int:rule_id>/edit', methods=['GET', 'POST'])
@login_required
@hr_required
def edit_workflow(rule_id):
    """Edit a workflow rule."""
    rule = WorkflowRule.query.get_or_404(rule_id)
    
    if request.method == 'POST':
        rule.name = request.form.get('name')
        rule.description = request.form.get('description')
        rule.trigger_type = request.form.get('trigger_type')
        rule.trigger_status = request.form.get('trigger_status') or None
        rule.trigger_days = request.form.get('trigger_days', type=int)
        rule.trigger_score = request.form.get('trigger_score', type=int)
        rule.action_type = request.form.get('action_type')
        rule.action_status = request.form.get('action_status') or None
        rule.action_template_id = request.form.get('action_template_id', type=int) or None
        rule.condition_job_id = request.form.get('condition_job_id', type=int) or None
        rule.condition_min_score = request.form.get('condition_min_score', type=int)
        rule.condition_max_score = request.form.get('condition_max_score', type=int)
        rule.priority = request.form.get('priority', 0, type=int)
        rule.is_active = request.form.get('is_active') == 'on'
        
        # Build action config
        action_config = {}
        if rule.action_type in ['send_email', 'send_notification']:
            action_config['subject'] = request.form.get('email_subject', '')
            action_config['body'] = request.form.get('email_body', '')
        elif rule.action_type == 'create_task':
            action_config['task_name'] = request.form.get('task_name', '')
            action_config['description'] = request.form.get('task_description', '')
            action_config['days'] = request.form.get('task_days', 3, type=int)
        elif rule.action_type == 'schedule_reminder':
            action_config['reminder_text'] = request.form.get('reminder_text', '')
            action_config['days'] = request.form.get('reminder_days', 7, type=int)
        
        if rule.trigger_type == 'time_based':
            action_config['time_reference'] = request.form.get('time_reference', 'application_date')
        
        rule.action_config = action_config if action_config else None
        
        db.session.commit()
        
        create_audit_log(current_user.id, 'update', 'workflow_rule', rule.id, 
                        {'name': rule.name})
        
        flash(f'Workflow rule "{rule.name}" updated successfully.', 'success')
        return redirect(url_for('hr.workflows'))
    
    # GET - show form
    jobs = JobPosting.query.filter(JobPosting.status.in_(['published', 'draft'])).all()
    templates = MessageTemplate.query.filter_by(is_active=True).all()
    statuses = ['submitted', 'under_review', 'shortlisted', 'interview_scheduled', 
                'interviewed', 'offered', 'rejected', 'hired', 'withdrawn']
    
    return render_template('workflows/rule_form.html',
                          rule=rule,
                          jobs=jobs,
                          templates=templates,
                          statuses=statuses)


@hr_bp.route('/workflows/<int:rule_id>/delete', methods=['POST'])
@login_required
@hr_required
def delete_workflow(rule_id):
    """Delete a workflow rule."""
    rule = WorkflowRule.query.get_or_404(rule_id)
    name = rule.name
    
    # Delete associated executions
    WorkflowExecution.query.filter_by(rule_id=rule_id).delete()
    
    db.session.delete(rule)
    db.session.commit()
    
    create_audit_log(current_user.id, 'delete', 'workflow_rule', rule_id, 
                    {'name': name})
    
    flash(f'Workflow rule "{name}" deleted.', 'success')
    return redirect(url_for('hr.workflows'))


@hr_bp.route('/workflows/<int:rule_id>/toggle', methods=['POST'])
@login_required
@hr_required
def toggle_workflow(rule_id):
    """Toggle a workflow rule active status."""
    rule = WorkflowRule.query.get_or_404(rule_id)
    rule.is_active = not rule.is_active
    db.session.commit()
    
    status = 'activated' if rule.is_active else 'deactivated'
    flash(f'Workflow rule "{rule.name}" {status}.', 'success')
    return redirect(url_for('hr.workflows'))


@hr_bp.route('/workflows/<int:rule_id>/executions')
@login_required
@hr_required
def workflow_executions(rule_id):
    """View execution history for a workflow rule."""
    rule = WorkflowRule.query.get_or_404(rule_id)
    page = request.args.get('page', 1, type=int)
    
    executions = rule.executions.order_by(WorkflowExecution.executed_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('workflows/executions.html',
                          rule=rule,
                          executions=executions)


@hr_bp.route('/scheduled-tasks')
@login_required
@hr_required
def scheduled_tasks():
    """View all scheduled tasks."""
    tasks = ScheduledTask.query.order_by(ScheduledTask.next_run.asc()).all()
    
    return render_template('workflows/scheduled_tasks.html', tasks=tasks, now=datetime.utcnow())


@hr_bp.route('/scheduled-tasks/create', methods=['GET', 'POST'])
@login_required
@hr_required
def create_scheduled_task():
    """Create a new scheduled task."""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        task_type = request.form.get('task_type')
        schedule_type = request.form.get('schedule_type')
        scheduled_time = request.form.get('scheduled_time')
        scheduled_date = request.form.get('scheduled_date')
        day_of_week = request.form.get('day_of_week', type=int)
        day_of_month = request.form.get('day_of_month', type=int)
        is_active = request.form.get('is_active') == 'on'
        
        # Build task config
        task_config = {}
        if task_type == 'job_closing_reminder':
            task_config['days_before'] = request.form.get('days_before', 3, type=int)
        elif task_type == 'interview_reminder':
            task_config['hours_before'] = request.form.get('hours_before', 24, type=int)
        elif task_type == 'document_reminder':
            task_config['days'] = request.form.get('doc_reminder_days', 7, type=int)
        elif task_type == 'cleanup':
            task_config['execution_log_days'] = request.form.get('log_retention_days', 90, type=int)
            task_config['message_days'] = request.form.get('message_retention_days', 180, type=int)
        
        # Parse time and date
        parsed_time = None
        if scheduled_time:
            try:
                parsed_time = datetime.strptime(scheduled_time, '%H:%M').time()
            except ValueError:
                pass
        
        parsed_date = None
        if scheduled_date:
            try:
                parsed_date = datetime.strptime(scheduled_date, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        # Calculate next run
        next_run = None
        if schedule_type == 'once' and parsed_date:
            next_run = datetime.combine(parsed_date, parsed_time or datetime.min.time())
        elif schedule_type == 'daily' and parsed_time:
            next_run = datetime.combine(datetime.utcnow().date(), parsed_time)
            if next_run < datetime.utcnow():
                next_run += timedelta(days=1)
        elif schedule_type == 'weekly' and day_of_week is not None:
            days_ahead = day_of_week - datetime.utcnow().weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_run = datetime.combine(
                datetime.utcnow().date() + timedelta(days=days_ahead),
                parsed_time or datetime.min.time()
            )
        elif schedule_type == 'monthly' and day_of_month:
            today = datetime.utcnow()
            if today.day > day_of_month:
                next_month = today.replace(day=1) + timedelta(days=32)
                next_run = datetime.combine(
                    next_month.replace(day=min(day_of_month, 28)),
                    parsed_time or datetime.min.time()
                )
            else:
                next_run = datetime.combine(
                    today.replace(day=min(day_of_month, 28)),
                    parsed_time or datetime.min.time()
                )
        
        task = ScheduledTask(
            name=name,
            description=description,
            task_type=task_type,
            task_config=task_config,
            schedule_type=schedule_type,
            scheduled_time=parsed_time,
            scheduled_date=parsed_date,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            is_active=is_active,
            next_run=next_run,
            created_by=current_user.id
        )
        
        db.session.add(task)
        db.session.commit()
        
        flash(f'Scheduled task "{name}" created successfully.', 'success')
        return redirect(url_for('hr.scheduled_tasks'))
    
    return render_template('workflows/scheduled_task_form.html', task=None)


@hr_bp.route('/scheduled-tasks/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
@hr_required
def edit_scheduled_task(task_id):
    """Edit a scheduled task."""
    task = ScheduledTask.query.get_or_404(task_id)
    
    if request.method == 'POST':
        task.name = request.form.get('name')
        task.description = request.form.get('description')
        task.task_type = request.form.get('task_type')
        task.schedule_type = request.form.get('schedule_type')
        task.is_active = request.form.get('is_active') == 'on'
        
        # Parse time and date
        scheduled_time = request.form.get('scheduled_time')
        scheduled_date = request.form.get('scheduled_date')
        
        if scheduled_time:
            try:
                task.scheduled_time = datetime.strptime(scheduled_time, '%H:%M').time()
            except ValueError:
                pass
        
        if scheduled_date:
            try:
                task.scheduled_date = datetime.strptime(scheduled_date, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        task.day_of_week = request.form.get('day_of_week', type=int)
        task.day_of_month = request.form.get('day_of_month', type=int)
        
        # Update task config
        task_config = {}
        if task.task_type == 'job_closing_reminder':
            task_config['days_before'] = request.form.get('days_before', 3, type=int)
        elif task.task_type == 'interview_reminder':
            task_config['hours_before'] = request.form.get('hours_before', 24, type=int)
        elif task.task_type == 'document_reminder':
            task_config['days'] = request.form.get('doc_reminder_days', 7, type=int)
        elif task.task_type == 'cleanup':
            task_config['execution_log_days'] = request.form.get('log_retention_days', 90, type=int)
            task_config['message_days'] = request.form.get('message_retention_days', 180, type=int)
        
        task.task_config = task_config
        
        # Recalculate next run
        if task.schedule_type == 'once' and task.scheduled_date:
            task.next_run = datetime.combine(task.scheduled_date, task.scheduled_time or datetime.min.time())
        elif task.schedule_type == 'daily' and task.scheduled_time:
            task.next_run = datetime.combine(datetime.utcnow().date(), task.scheduled_time)
            if task.next_run < datetime.utcnow():
                task.next_run += timedelta(days=1)
        elif task.schedule_type == 'weekly' and task.day_of_week is not None:
            days_ahead = task.day_of_week - datetime.utcnow().weekday()
            if days_ahead <= 0:
                days_ahead += 7
            task.next_run = datetime.combine(
                datetime.utcnow().date() + timedelta(days=days_ahead),
                task.scheduled_time or datetime.min.time()
            )
        elif task.schedule_type == 'monthly' and task.day_of_month:
            today = datetime.utcnow()
            if today.day > task.day_of_month:
                next_month = today.replace(day=1) + timedelta(days=32)
                task.next_run = datetime.combine(
                    next_month.replace(day=min(task.day_of_month, 28)),
                    task.scheduled_time or datetime.min.time()
                )
            else:
                task.next_run = datetime.combine(
                    today.replace(day=min(task.day_of_month, 28)),
                    task.scheduled_time or datetime.min.time()
                )
        
        db.session.commit()
        
        flash(f'Scheduled task "{task.name}" updated.', 'success')
        return redirect(url_for('hr.scheduled_tasks'))
    
    return render_template('workflows/scheduled_task_form.html', task=task)


@hr_bp.route('/scheduled-tasks/<int:task_id>/delete', methods=['POST'])
@login_required
@hr_required
def delete_scheduled_task(task_id):
    """Delete a scheduled task."""
    task = ScheduledTask.query.get_or_404(task_id)
    name = task.name
    
    db.session.delete(task)
    db.session.commit()
    
    flash(f'Scheduled task "{name}" deleted.', 'success')
    return redirect(url_for('hr.scheduled_tasks'))


@hr_bp.route('/scheduled-tasks/<int:task_id>/toggle', methods=['POST'])
@login_required
@hr_required
def toggle_scheduled_task(task_id):
    """Toggle a scheduled task active status."""
    task = ScheduledTask.query.get_or_404(task_id)
    task.is_active = not task.is_active
    db.session.commit()
    
    status = 'activated' if task.is_active else 'deactivated'
    flash(f'Scheduled task "{task.name}" {status}.', 'success')
    return redirect(url_for('hr.scheduled_tasks'))


@hr_bp.route('/status-transitions')
@login_required
@hr_required
def status_transitions():
    """View status transition history."""
    page = request.args.get('page', 1, type=int)
    application_id = request.args.get('application_id', type=int)
    
    query = StatusTransitionLog.query
    
    if application_id:
        query = query.filter_by(application_id=application_id)
    
    transitions = query.order_by(StatusTransitionLog.transitioned_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    return render_template('workflows/status_transitions.html',
                          transitions=transitions,
                          filter_application_id=application_id)


@hr_bp.route('/run-workflow-tasks', methods=['POST'])
@login_required
@admin_required
def run_workflow_tasks():
    """Manually trigger workflow task processing."""
    from app.services.workflow_service import WorkflowService
    
    task_type = request.form.get('task_type', 'all')
    
    try:
        if task_type == 'time_based' or task_type == 'all':
            WorkflowService.process_time_based_rules()
        
        if task_type == 'job_closing' or task_type == 'all':
            WorkflowService.process_job_closing_rules()
        
        if task_type == 'scheduled' or task_type == 'all':
            WorkflowService.run_scheduled_tasks()
        
        flash('Workflow tasks executed successfully.', 'success')
    except Exception as e:
        current_app.logger.error(f'Error running workflow tasks: {e}')
        flash(f'Error executing workflow tasks: {str(e)}', 'danger')
    
    return redirect(url_for('hr.workflows'))