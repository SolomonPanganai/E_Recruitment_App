"""Applicant portal routes."""
import os
import uuid
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.applicant import applicant_bp
from app.models import JobPosting, Application, Document, Offer, create_audit_log, Message
from app.forms import ApplicationForm, OfferResponseForm
from app.utils.notifications import send_application_confirmation, send_status_update_email


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def generate_application_reference():
    """Generate unique application reference."""
    date_str = datetime.utcnow().strftime('%Y%m%d')
    # Get count of applications today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    count = Application.query.filter(Application.created_at >= today_start).count() + 1
    return f"APP-{date_str}-{count:03d}"


def save_uploaded_file(file, subfolder='documents'):
    """Save uploaded file and return filename."""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Add unique identifier to prevent overwrites
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        
        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
        os.makedirs(upload_path, exist_ok=True)
        
        file_path = os.path.join(upload_path, unique_filename)
        file.save(file_path)
        
        return unique_filename
    return None


@applicant_bp.route('/dashboard')
@login_required
def dashboard():
    """Applicant dashboard."""
    if current_user.role != 'applicant':
        flash('Access denied.', 'danger')
        return redirect(url_for('hr.dashboard'))
    
    # Get applicant's applications
    applications = Application.query.filter_by(applicant_id=current_user.id).order_by(
        Application.application_date.desc()
    ).all()
    
    # Get recommended jobs (jobs they haven't applied to)
    applied_job_ids = [app.job_id for app in applications]
    recommended_jobs = JobPosting.query.filter(
        JobPosting.status == 'published',
        ~JobPosting.id.in_(applied_job_ids) if applied_job_ids else True
    ).order_by(JobPosting.posting_date.desc()).limit(5).all()
    
    return render_template('applicant_dashboard.html', 
                           applications=applications,
                           recommended_jobs=recommended_jobs)


@applicant_bp.route('/apply/<int:job_id>', methods=['GET', 'POST'])
@login_required
def apply(job_id):
    """Apply for a job."""
    if current_user.role != 'applicant':
        flash('Only applicants can apply for jobs.', 'warning')
        return redirect(url_for('main.job_detail', job_id=job_id))
    
    job = JobPosting.query.get_or_404(job_id)
    
    # Check if job is open
    if not job.is_open:
        flash('This job is no longer accepting applications.', 'warning')
        return redirect(url_for('main.job_detail', job_id=job_id))
    
    # Check for existing application
    existing = Application.query.filter_by(
        job_id=job_id, 
        applicant_id=current_user.id
    ).first()
    
    if existing:
        flash('You have already applied for this position.', 'info')
        return redirect(url_for('applicant.application_detail', application_id=existing.id))
    
    form = ApplicationForm()
    
    if form.validate_on_submit():
        # Create application
        application = Application(
            application_reference=generate_application_reference(),
            job_id=job_id,
            applicant_id=current_user.id,
            cover_letter=form.cover_letter.data,
            status='submitted',
            current_stage='Screening'
        )
        db.session.add(application)
        db.session.flush()  # Get application ID
        
        # Save CV
        if form.cv_file.data:
            cv_filename = save_uploaded_file(form.cv_file.data, f'applications/{application.id}')
            if cv_filename:
                cv_doc = Document(
                    application_id=application.id,
                    file_name=form.cv_file.data.filename,
                    local_path=cv_filename,
                    document_type='cv',
                    uploaded_by=current_user.id,
                    file_size=form.cv_file.data.content_length,
                    mime_type=form.cv_file.data.content_type
                )
                db.session.add(cv_doc)
        
        # Save ID document if provided
        if form.id_document.data:
            id_filename = save_uploaded_file(form.id_document.data, f'applications/{application.id}')
            if id_filename:
                id_doc = Document(
                    application_id=application.id,
                    file_name=form.id_document.data.filename,
                    local_path=id_filename,
                    document_type='id',
                    uploaded_by=current_user.id
                )
                db.session.add(id_doc)
        
        # Save qualifications if provided
        if form.qualifications.data:
            qual_filename = save_uploaded_file(form.qualifications.data, f'applications/{application.id}')
            if qual_filename:
                qual_doc = Document(
                    application_id=application.id,
                    file_name=form.qualifications.data.filename,
                    local_path=qual_filename,
                    document_type='qualification',
                    uploaded_by=current_user.id
                )
                db.session.add(qual_doc)
        
        # Update job application count
        job.applications_count += 1
        
        # Audit log
        create_audit_log(
            user_id=current_user.id,
            action='CREATE_APPLICATION',
            entity_type='Application',
            entity_id=application.id,
            new_values={'job_id': job_id, 'reference': application.application_reference},
            ip_address=request.remote_addr
        )
        
        db.session.commit()
        
        # Send confirmation email
        try:
            send_application_confirmation(application)
            current_app.logger.info(f'Confirmation email sent for application {application.application_reference}')
        except Exception as e:
            current_app.logger.error(f'Failed to send confirmation email: {e}')
        
        flash('Your application has been submitted successfully!', 'success')
        return redirect(url_for('applicant.application_detail', application_id=application.id))
    
    return render_template('apply.html', form=form, job=job)


@applicant_bp.route('/applications')
@login_required
def applications():
    """List all applications for current user."""
    if current_user.role != 'applicant':
        return redirect(url_for('hr.dashboard'))
    
    page = request.args.get('page', 1, type=int)
    applications_paginated = Application.query.filter_by(
        applicant_id=current_user.id
    ).order_by(Application.application_date.desc()).paginate(
        page=page,
        per_page=current_app.config.get('APPLICATIONS_PER_PAGE', 20),
        error_out=False
    )
    
    return render_template('applications.html', 
                           applications=applications_paginated.items,
                           pagination=applications_paginated)


@applicant_bp.route('/applications/<int:application_id>')
@login_required
def application_detail(application_id):
    """View application details."""
    application = Application.query.get_or_404(application_id)
    
    # Ensure applicant can only view their own applications
    if application.applicant_id != current_user.id and current_user.role == 'applicant':
        flash('Access denied.', 'danger')
        return redirect(url_for('applicant.dashboard'))
    
    return render_template('application_detail.html', application=application)


@applicant_bp.route('/applications/<int:application_id>/withdraw', methods=['POST'])
@login_required
def withdraw_application(application_id):
    """Withdraw an application."""
    application = Application.query.get_or_404(application_id)
    
    if application.applicant_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('applicant.dashboard'))
    
    if application.status in ('offered', 'rejected', 'withdrawn'):
        flash('This application cannot be withdrawn.', 'warning')
        return redirect(url_for('applicant.application_detail', application_id=application_id))
    
    old_status = application.status
    application.status = 'withdrawn'
    
    create_audit_log(
        user_id=current_user.id,
        action='WITHDRAW_APPLICATION',
        entity_type='Application',
        entity_id=application.id,
        old_values={'status': old_status},
        new_values={'status': 'withdrawn'},
        ip_address=request.remote_addr
    )
    
    db.session.commit()
    
    flash('Your application has been withdrawn.', 'info')
    return redirect(url_for('applicant.dashboard'))


@applicant_bp.route('/offers/<int:offer_id>/respond', methods=['GET', 'POST'])
@login_required
def respond_to_offer(offer_id):
    """Respond to a job offer."""
    offer = Offer.query.get_or_404(offer_id)
    
    # Verify ownership
    if offer.application.applicant_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('applicant.dashboard'))
    
    if offer.status != 'pending':
        flash('This offer is no longer pending.', 'warning')
        return redirect(url_for('applicant.application_detail', 
                                application_id=offer.application_id))
    
    form = OfferResponseForm()
    
    if form.validate_on_submit():
        old_status = offer.status
        offer.status = form.response.data
        
        if form.response.data == 'accepted':
            offer.accepted_date = datetime.utcnow()
            offer.application.status = 'offered'
            flash('Congratulations! You have accepted the offer.', 'success')
        else:
            offer.application.status = 'rejected'
            flash('You have declined the offer.', 'info')
        
        create_audit_log(
            user_id=current_user.id,
            action='RESPOND_TO_OFFER',
            entity_type='Offer',
            entity_id=offer.id,
            old_values={'status': old_status},
            new_values={'status': offer.status},
            ip_address=request.remote_addr
        )
        
        db.session.commit()
        
        return redirect(url_for('applicant.application_detail', 
                                application_id=offer.application_id))
    
    return render_template('offer_response.html', form=form, offer=offer)


@applicant_bp.route('/documents/<int:doc_id>')
@login_required
def download_document(doc_id):
    """Download a document by ID (only own documents for applicants)."""
    document = Document.query.get_or_404(doc_id)
    
    # Security: verify user has access to this document
    if current_user.role == 'applicant':
        if document.application and document.application.applicant_id != current_user.id:
            flash('Access denied.', 'danger')
            return redirect(url_for('applicant.dashboard'))
    
    # Determine subfolder from document
    if document.application_id:
        subfolder = f'applications/{document.application_id}'
    else:
        subfolder = 'documents'
    
    upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    
    # Get the actual filename from local_path
    actual_filename = document.local_path if document.local_path else document.file_name
    
    return send_from_directory(upload_path, actual_filename, as_attachment=True, 
                               download_name=document.file_name)


@applicant_bp.route('/documents/<int:doc_id>/view')
@login_required
def view_document(doc_id):
    """View document inline (for PDF previews)."""
    document = Document.query.get_or_404(doc_id)
    
    # Security: verify user has access
    if current_user.role == 'applicant':
        if document.application and document.application.applicant_id != current_user.id:
            flash('Access denied.', 'danger')
            return redirect(url_for('applicant.dashboard'))
    
    # Determine subfolder
    if document.application_id:
        subfolder = f'applications/{document.application_id}'
    else:
        subfolder = 'documents'
    
    upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    actual_filename = document.local_path if document.local_path else document.file_name
    
    return send_from_directory(upload_path, actual_filename, as_attachment=False)


# ============== Assessment Taking ==============

@applicant_bp.route('/assessments')
@login_required
def my_assessments():
    """List available and completed assessments for the applicant."""
    from app.models import Assessment, CandidateAssessment
    
    # Get all applications for the current user
    applications = Application.query.filter_by(applicant_id=current_user.id).all()
    
    available_assessments = []
    completed_assessments = []
    
    for application in applications:
        # Get assessments for this job
        assessments = Assessment.query.filter_by(job_id=application.job_id, is_active=True).all()
        
        for assessment in assessments:
            # Check if candidate has attempted this assessment
            attempt = CandidateAssessment.query.filter_by(
                assessment_id=assessment.id,
                application_id=application.id,
                candidate_id=current_user.id
            ).order_by(CandidateAssessment.attempt_number.desc()).first()
            
            if attempt and attempt.status == 'completed':
                completed_assessments.append({
                    'assessment': assessment,
                    'application': application,
                    'attempt': attempt
                })
            elif not attempt or (attempt.status != 'completed' and 
                                 attempt.attempt_number < assessment.max_attempts):
                available_assessments.append({
                    'assessment': assessment,
                    'application': application,
                    'attempts_used': attempt.attempt_number if attempt else 0
                })
    
    return render_template('applicant_assessments.html',
                           available_assessments=available_assessments,
                           completed_assessments=completed_assessments)


@applicant_bp.route('/assessment/<int:assessment_id>/start/<int:application_id>', methods=['GET', 'POST'])
@login_required
def start_assessment(assessment_id, application_id):
    """Start or continue an assessment."""
    from app.models import Assessment, CandidateAssessment, AssessmentQuestion
    
    assessment = Assessment.query.get_or_404(assessment_id)
    application = Application.query.get_or_404(application_id)
    
    # Verify ownership
    if application.applicant_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('applicant.dashboard'))
    
    # Verify assessment belongs to this job
    if assessment.job_id != application.job_id:
        flash('Invalid assessment for this application.', 'danger')
        return redirect(url_for('applicant.my_assessments'))
    
    # Check if assessment is active
    if not assessment.is_active:
        flash('This assessment is no longer available.', 'warning')
        return redirect(url_for('applicant.my_assessments'))
    
    # Check for existing in-progress attempt or create new one
    existing_attempt = CandidateAssessment.query.filter_by(
        assessment_id=assessment_id,
        application_id=application_id,
        candidate_id=current_user.id,
        status='in_progress'
    ).first()
    
    if existing_attempt:
        # Check if timed out
        if existing_attempt.is_timed_out:
            existing_attempt.status = 'timed_out'
            existing_attempt.completed_at = datetime.utcnow()
            db.session.commit()
            flash('Your previous attempt has timed out.', 'warning')
            existing_attempt = None
    
    if not existing_attempt:
        # Check max attempts
        attempt_count = CandidateAssessment.query.filter_by(
            assessment_id=assessment_id,
            application_id=application_id,
            candidate_id=current_user.id
        ).count()
        
        if attempt_count >= assessment.max_attempts:
            flash('You have used all your attempts for this assessment.', 'warning')
            return redirect(url_for('applicant.my_assessments'))
        
        # Create new attempt
        existing_attempt = CandidateAssessment(
            assessment_id=assessment_id,
            application_id=application_id,
            candidate_id=current_user.id,
            attempt_number=attempt_count + 1,
            total_points=assessment.total_points
        )
        db.session.add(existing_attempt)
        db.session.commit()
    
    # Get questions
    questions = assessment.questions.order_by(AssessmentQuestion.order).all()
    
    if assessment.shuffle_questions:
        import random
        questions = list(questions)
        random.shuffle(questions)
    
    return render_template('assessment_take.html',
                           assessment=assessment,
                           attempt=existing_attempt,
                           questions=questions,
                           application=application)


@applicant_bp.route('/assessment/<int:attempt_id>/submit', methods=['POST'])
@login_required
def submit_assessment(attempt_id):
    """Submit assessment answers."""
    from app.models import CandidateAssessment, CandidateAnswer, AssessmentQuestion, QuestionOption
    
    attempt = CandidateAssessment.query.get_or_404(attempt_id)
    
    # Verify ownership
    if attempt.candidate_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('applicant.dashboard'))
    
    if attempt.status == 'completed':
        flash('This assessment has already been submitted.', 'info')
        return redirect(url_for('applicant.assessment_result', attempt_id=attempt_id))
    
    # Check for timeout
    if attempt.is_timed_out:
        attempt.status = 'timed_out'
        attempt.completed_at = datetime.utcnow()
        db.session.commit()
        flash('Assessment timed out.', 'warning')
        return redirect(url_for('applicant.my_assessments'))
    
    assessment = attempt.assessment
    total_points = 0
    earned_points = 0
    
    # Process each question
    for question in assessment.questions:
        total_points += question.points
        
        # Check if already answered
        existing_answer = CandidateAnswer.query.filter_by(
            candidate_assessment_id=attempt_id,
            question_id=question.id
        ).first()
        
        if existing_answer:
            continue  # Skip if already answered
        
        answer = CandidateAnswer(
            candidate_assessment_id=attempt_id,
            question_id=question.id
        )
        
        if question.question_type == 'multiple_choice':
            selected_option_id = request.form.get(f'question_{question.id}', type=int)
            if selected_option_id:
                answer.selected_option_id = selected_option_id
                option = QuestionOption.query.get(selected_option_id)
                if option and option.is_correct:
                    answer.is_correct = True
                    answer.points_awarded = question.points
                    earned_points += question.points
                else:
                    answer.is_correct = False
        
        elif question.question_type == 'true_false':
            selected_option_id = request.form.get(f'question_{question.id}', type=int)
            if selected_option_id:
                answer.selected_option_id = selected_option_id
                option = QuestionOption.query.get(selected_option_id)
                if option and option.is_correct:
                    answer.is_correct = True
                    answer.points_awarded = question.points
                    earned_points += question.points
                else:
                    answer.is_correct = False
        
        elif question.question_type == 'multiple_select':
            selected_ids = request.form.getlist(f'question_{question.id}')
            answer.selected_options = [int(sid) for sid in selected_ids]
            
            # Check if all correct options were selected and no incorrect ones
            correct_options = set(o.id for o in question.options if o.is_correct)
            selected_set = set(answer.selected_options)
            
            if correct_options == selected_set:
                answer.is_correct = True
                answer.points_awarded = question.points
                earned_points += question.points
            else:
                answer.is_correct = False
        
        elif question.question_type == 'text':
            text_answer = request.form.get(f'question_{question.id}', '').strip()
            answer.text_answer = text_answer
            # Text questions need manual grading
            answer.is_correct = None
        
        db.session.add(answer)
    
    # Calculate score
    score_percentage = (earned_points / total_points * 100) if total_points > 0 else 0
    
    # Update attempt
    attempt.completed_at = datetime.utcnow()
    attempt.status = 'completed'
    attempt.points_earned = earned_points
    attempt.total_points = total_points
    attempt.score = score_percentage
    attempt.passed = score_percentage >= assessment.pass_score
    
    db.session.commit()
    
    flash('Assessment submitted successfully!', 'success')
    
    if assessment.show_results_immediately:
        return redirect(url_for('applicant.assessment_result', attempt_id=attempt_id))
    else:
        flash('Results will be available after review.', 'info')
        return redirect(url_for('applicant.my_assessments'))


@applicant_bp.route('/assessment/result/<int:attempt_id>')
@login_required
def assessment_result(attempt_id):
    """View assessment result."""
    from app.models import CandidateAssessment, CandidateAnswer
    
    attempt = CandidateAssessment.query.get_or_404(attempt_id)
    
    # Verify ownership
    if attempt.candidate_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('applicant.dashboard'))
    
    # Check if results should be shown
    if not attempt.assessment.show_results_immediately and attempt.status != 'completed':
        flash('Results are not yet available.', 'info')
        return redirect(url_for('applicant.my_assessments'))
    
    answers = CandidateAnswer.query.filter_by(candidate_assessment_id=attempt_id).all()
    
    return render_template('assessment_result.html', attempt=attempt, answers=answers)


# ============== Applicant Messaging ==============

@applicant_bp.route('/messages')
@login_required
def applicant_messages():
    """Applicant inbox."""
    page = request.args.get('page', 1, type=int)
    view = request.args.get('view', 'inbox')  # inbox, sent
    
    if view == 'sent':
        messages = Message.query.filter_by(
            sender_id=current_user.id,
            is_deleted_by_sender=False
        ).order_by(Message.created_at.desc())
    else:  # inbox
        messages = Message.query.filter_by(
            recipient_id=current_user.id,
            is_deleted_by_recipient=False
        ).order_by(Message.created_at.desc())
    
    messages = messages.paginate(page=page, per_page=20, error_out=False)
    unread_count = Message.get_unread_count(current_user.id)
    
    return render_template('applicant_messages/inbox.html',
                           messages=messages,
                           view=view,
                           unread_count=unread_count)


@applicant_bp.route('/messages/<int:message_id>')
@login_required
def view_applicant_message(message_id):
    """View a message."""
    message = Message.query.get_or_404(message_id)
    
    # Check permission
    if message.sender_id != current_user.id and message.recipient_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('applicant.applicant_messages'))
    
    # Mark as read if recipient
    if message.recipient_id == current_user.id and not message.is_read:
        message.mark_as_read()
    
    return render_template('applicant_messages/view.html', message=message)


@applicant_bp.route('/messages/reply/<int:message_id>', methods=['GET', 'POST'])
@login_required
def reply_message(message_id):
    """Reply to a message."""
    original = Message.query.get_or_404(message_id)
    
    # Can only reply to messages where user is recipient
    if original.recipient_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('applicant.applicant_messages'))
    
    if request.method == 'POST':
        body = request.form.get('body', '').strip()
        
        if not body:
            flash('Please enter a message.', 'warning')
            return redirect(url_for('applicant.reply_message', message_id=message_id))
        
        reply = Message(
            sender_id=current_user.id,
            recipient_id=original.sender_id,
            subject=f"Re: {original.subject}",
            body=body,
            message_type='inquiry',
            application_id=original.application_id,
            parent_id=original.id
        )
        db.session.add(reply)
        db.session.commit()
        
        flash('Reply sent!', 'success')
        return redirect(url_for('applicant.view_applicant_message', message_id=message_id))
    
    return render_template('applicant_messages/reply.html', original=original)


@applicant_bp.route('/messages/<int:message_id>/delete', methods=['POST'])
@login_required
def delete_applicant_message(message_id):
    """Delete a message."""
    message = Message.query.get_or_404(message_id)
    
    if message.sender_id == current_user.id:
        message.is_deleted_by_sender = True
    elif message.recipient_id == current_user.id:
        message.is_deleted_by_recipient = True
    else:
        flash('Access denied.', 'danger')
        return redirect(url_for('applicant.applicant_messages'))
    
    db.session.commit()
    flash('Message deleted.', 'info')
    return redirect(url_for('applicant.applicant_messages'))

