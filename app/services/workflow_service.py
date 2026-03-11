"""Workflow automation service for E-Recruitment system."""
from datetime import datetime, timedelta
from flask import current_app, render_template
from flask_mail import Message as MailMessage
from app import db, mail
from app.models import (
    WorkflowRule, WorkflowExecution, ScheduledTask, StatusTransitionLog,
    Application, JobPosting, User, Message, MessageTemplate, Interview,
    Committee, CommitteeMember, CommitteeDecision, CommitteeMemberVote
)


def send_workflow_email(subject, recipients, body, html_body=None):
    """Send an email from workflow service."""
    try:
        msg = MailMessage(
            subject=subject,
            recipients=recipients if isinstance(recipients, list) else [recipients],
            body=body,
            html=html_body or f"<p>{body}</p>"
        )
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send workflow email: {e}")
        return False


class WorkflowService:
    """Service class for handling workflow automation."""
    
    # Valid status transitions
    STATUS_TRANSITIONS = {
        'submitted': ['under_review', 'rejected', 'withdrawn'],
        'under_review': ['shortlisted', 'rejected', 'withdrawn'],
        'shortlisted': ['interview_scheduled', 'rejected', 'withdrawn'],
        'interview_scheduled': ['interviewed', 'rejected', 'withdrawn'],
        'interviewed': ['offered', 'rejected', 'withdrawn'],
        'offered': ['hired', 'rejected', 'withdrawn'],
        'rejected': [],
        'hired': [],
        'withdrawn': []
    }
    
    @classmethod
    def is_valid_transition(cls, from_status, to_status):
        """Check if a status transition is valid."""
        if from_status is None:
            return to_status == 'submitted'
        return to_status in cls.STATUS_TRANSITIONS.get(from_status, [])
    
    @classmethod
    def log_status_transition(cls, application_id, from_status, to_status, 
                              changed_by=None, change_type='manual', 
                              notes=None, workflow_rule_id=None):
        """Log a status transition."""
        log = StatusTransitionLog(
            application_id=application_id,
            from_status=from_status,
            to_status=to_status,
            changed_by=changed_by,
            change_type=change_type,
            notes=notes,
            workflow_rule_id=workflow_rule_id
        )
        db.session.add(log)
        db.session.commit()
        return log
    
    @classmethod
    def trigger_status_change_rules(cls, application, old_status, new_status, triggered_by=None):
        """Execute workflow rules triggered by status changes."""
        rules = WorkflowRule.query.filter(
            WorkflowRule.is_active == True,
            WorkflowRule.trigger_type == 'status_change',
            WorkflowRule.trigger_status == new_status
        ).order_by(WorkflowRule.priority.desc()).all()
        
        for rule in rules:
            # Check if rule applies to this job
            if rule.condition_job_id and rule.condition_job_id != application.job_id:
                continue
            
            # Check score conditions
            if rule.condition_min_score and application.score and application.score < rule.condition_min_score:
                continue
            if rule.condition_max_score and application.score and application.score > rule.condition_max_score:
                continue
            
            # Execute the rule
            cls.execute_rule(rule, application, f"Status changed from {old_status} to {new_status}")
    
    @classmethod
    def trigger_score_based_rules(cls, application, new_score):
        """Execute workflow rules triggered by score changes."""
        rules = WorkflowRule.query.filter(
            WorkflowRule.is_active == True,
            WorkflowRule.trigger_type == 'score_based'
        ).order_by(WorkflowRule.priority.desc()).all()
        
        for rule in rules:
            # Check if rule applies to this job
            if rule.condition_job_id and rule.condition_job_id != application.job_id:
                continue
            
            # Check if score threshold is met
            if rule.trigger_score and new_score >= rule.trigger_score:
                cls.execute_rule(rule, application, f"Score reached {new_score}")
    
    @classmethod
    def trigger_document_rules(cls, application, document_type):
        """Execute workflow rules triggered by document submission."""
        rules = WorkflowRule.query.filter(
            WorkflowRule.is_active == True,
            WorkflowRule.trigger_type == 'document_submitted'
        ).order_by(WorkflowRule.priority.desc()).all()
        
        for rule in rules:
            if rule.condition_job_id and rule.condition_job_id != application.job_id:
                continue
            
            cls.execute_rule(rule, application, f"Document submitted: {document_type}")
    
    @classmethod
    def trigger_interview_scheduled_rules(cls, application, interview):
        """Execute workflow rules triggered by interview scheduling."""
        rules = WorkflowRule.query.filter(
            WorkflowRule.is_active == True,
            WorkflowRule.trigger_type == 'interview_scheduled'
        ).order_by(WorkflowRule.priority.desc()).all()
        
        for rule in rules:
            if rule.condition_job_id and rule.condition_job_id != application.job_id:
                continue
            
            cls.execute_rule(rule, application, f"Interview scheduled for {interview.scheduled_date}")
    
    @classmethod
    def trigger_interview_completed_rules(cls, application, interview):
        """Execute workflow rules triggered by interview completion."""
        rules = WorkflowRule.query.filter(
            WorkflowRule.is_active == True,
            WorkflowRule.trigger_type == 'interview_completed'
        ).order_by(WorkflowRule.priority.desc()).all()
        
        for rule in rules:
            if rule.condition_job_id and rule.condition_job_id != application.job_id:
                continue
            
            # Check score conditions (using interview score)
            if rule.condition_min_score and interview.overall_score and interview.overall_score < rule.condition_min_score:
                continue
            if rule.condition_max_score and interview.overall_score and interview.overall_score > rule.condition_max_score:
                continue
            
            cls.execute_rule(rule, application, f"Interview completed with score {interview.overall_score}")
    
    @classmethod
    def execute_rule(cls, rule, application, trigger_event):
        """Execute a workflow rule action."""
        execution = WorkflowExecution(
            rule_id=rule.id,
            application_id=application.id if application else None,
            job_id=application.job_id if application else None,
            trigger_event=trigger_event,
            status='pending'
        )
        db.session.add(execution)
        
        try:
            if rule.action_type == 'change_status':
                cls._execute_status_change(rule, application, execution)
            elif rule.action_type == 'send_email':
                cls._execute_send_email(rule, application, execution)
            elif rule.action_type == 'send_notification':
                cls._execute_send_notification(rule, application, execution)
            elif rule.action_type == 'create_task':
                cls._execute_create_task(rule, application, execution)
            elif rule.action_type == 'schedule_reminder':
                cls._execute_schedule_reminder(rule, application, execution)
            
            execution.status = 'completed'
            db.session.commit()
            
        except Exception as e:
            execution.status = 'failed'
            execution.error_message = str(e)
            db.session.commit()
            current_app.logger.error(f"Workflow rule execution failed: {e}")
        
        return execution
    
    @classmethod
    def _execute_status_change(cls, rule, application, execution):
        """Change application status."""
        if not rule.action_status:
            raise ValueError("No target status specified")
        
        old_status = application.status
        if cls.is_valid_transition(old_status, rule.action_status):
            application.status = rule.action_status
            execution.action_taken = f"Status changed from {old_status} to {rule.action_status}"
            
            # Log the transition
            cls.log_status_transition(
                application.id, old_status, rule.action_status,
                change_type='automated', workflow_rule_id=rule.id,
                notes=f"Triggered by rule: {rule.name}"
            )
        else:
            execution.status = 'skipped'
            execution.action_taken = f"Invalid transition from {old_status} to {rule.action_status}"
    
    @classmethod
    def _execute_send_email(cls, rule, application, execution):
        """Send email notification."""
        if not application or not application.applicant:
            raise ValueError("No applicant found")
        
        template = rule.action_template
        applicant = application.applicant
        job = application.job
        
        # Prepare context for template
        context = {
            'applicant_name': f"{applicant.first_name} {applicant.last_name}",
            'job_title': job.title if job else 'N/A',
            'job_reference': job.job_reference if job else 'N/A',
            'application_status': application.status,
            'company_name': 'E-Recruit'
        }
        
        if template:
            subject = template.subject
            # Replace placeholders in body
            body = template.body
            for key, value in context.items():
                body = body.replace(f'{{{{{key}}}}}', str(value))
        else:
            config = rule.action_config or {}
            subject = config.get('subject', 'Application Update')
            body = config.get('body', f"Your application status has been updated to: {application.status}")
        
        send_workflow_email(
            subject=subject,
            recipients=[applicant.email],
            body=body,
            html_body=f"<p>{body}</p>"
        )
        
        execution.action_taken = f"Email sent to {applicant.email}"
    
    @classmethod
    def _execute_send_notification(cls, rule, application, execution):
        """Send internal notification/message."""
        if not application or not application.applicant:
            raise ValueError("No applicant found")
        
        template = rule.action_template
        applicant = application.applicant
        job = application.job
        
        # Prepare context
        context = {
            'applicant_name': f"{applicant.first_name} {applicant.last_name}",
            'job_title': job.title if job else 'N/A',
            'application_status': application.status
        }
        
        if template:
            subject = template.subject
            body = template.body
            for key, value in context.items():
                body = body.replace(f'{{{{{key}}}}}', str(value))
        else:
            config = rule.action_config or {}
            subject = config.get('subject', 'Application Update')
            body = config.get('body', f"Your application status has been updated to: {application.status}")
        
        # Create internal message
        message = Message(
            sender_id=rule.created_by,
            recipient_id=applicant.id,
            subject=subject,
            body=body,
            is_system_message=True
        )
        db.session.add(message)
        
        execution.action_taken = f"Notification sent to {applicant.email}"
    
    @classmethod
    def _execute_create_task(cls, rule, application, execution):
        """Create a follow-up task."""
        config = rule.action_config or {}
        
        task = ScheduledTask(
            name=config.get('task_name', f"Follow up on application {application.id}"),
            description=config.get('description', ''),
            task_type='application_followup',
            task_config={'application_id': application.id},
            schedule_type='once',
            scheduled_date=datetime.utcnow().date() + timedelta(days=config.get('days', 3)),
            created_by=rule.created_by,
            is_active=True
        )
        db.session.add(task)
        
        execution.action_taken = f"Task created: {task.name}"
    
    @classmethod
    def _execute_schedule_reminder(cls, rule, application, execution):
        """Schedule a reminder."""
        config = rule.action_config or {}
        days = config.get('days', 7)
        
        task = ScheduledTask(
            name=f"Reminder: {config.get('reminder_text', 'Review application')}",
            description=f"Application ID: {application.id}",
            task_type='application_followup',
            task_config={
                'application_id': application.id,
                'reminder_text': config.get('reminder_text', 'Review this application')
            },
            schedule_type='once',
            scheduled_date=datetime.utcnow().date() + timedelta(days=days),
            created_by=rule.created_by,
            is_active=True
        )
        db.session.add(task)
        
        execution.action_taken = f"Reminder scheduled for {task.scheduled_date}"
    
    @classmethod
    def process_time_based_rules(cls):
        """Process time-based workflow rules. Called by scheduled task."""
        rules = WorkflowRule.query.filter(
            WorkflowRule.is_active == True,
            WorkflowRule.trigger_type == 'time_based'
        ).all()
        
        for rule in rules:
            cls._process_time_rule(rule)
    
    @classmethod
    def _process_time_rule(cls, rule):
        """Process a single time-based rule."""
        days = rule.trigger_days or 0
        config = rule.action_config or {}
        reference = config.get('time_reference', 'application_date')
        
        # Calculate the target date
        target_date = datetime.utcnow() - timedelta(days=days)
        
        # Build query based on reference
        query = Application.query
        
        if reference == 'application_date':
            query = query.filter(Application.application_date <= target_date)
        elif reference == 'last_updated':
            query = query.filter(Application.updated_at <= target_date)
        
        # Apply job condition
        if rule.condition_job_id:
            query = query.filter(Application.job_id == rule.condition_job_id)
        
        # Apply status filter if specified
        if rule.trigger_status:
            query = query.filter(Application.status == rule.trigger_status)
        
        applications = query.all()
        
        for application in applications:
            # Check if rule was already executed for this application recently
            recent_execution = WorkflowExecution.query.filter(
                WorkflowExecution.rule_id == rule.id,
                WorkflowExecution.application_id == application.id,
                WorkflowExecution.executed_at >= datetime.utcnow() - timedelta(days=1)
            ).first()
            
            if not recent_execution:
                cls.execute_rule(rule, application, f"Time-based trigger: {days} days elapsed")
    
    @classmethod
    def process_job_closing_rules(cls):
        """Process rules for jobs approaching closing date."""
        rules = WorkflowRule.query.filter(
            WorkflowRule.is_active == True,
            WorkflowRule.trigger_type == 'job_closing'
        ).all()
        
        for rule in rules:
            days_before = rule.trigger_days or 3
            target_date = datetime.utcnow().date() + timedelta(days=days_before)
            
            jobs = JobPosting.query.filter(
                JobPosting.status == 'published',
                JobPosting.closing_date == target_date
            ).all()
            
            for job in jobs:
                # Execute for each pending application if rule targets applications
                if rule.action_type in ['send_email', 'send_notification']:
                    applications = Application.query.filter(
                        Application.job_id == job.id,
                        Application.status.in_(['submitted', 'under_review'])
                    ).all()
                    
                    for app in applications:
                        cls.execute_rule(rule, app, f"Job closing in {days_before} days")
    
    @classmethod
    def run_scheduled_tasks(cls):
        """Run all due scheduled tasks."""
        now = datetime.utcnow()
        
        tasks = ScheduledTask.query.filter(
            ScheduledTask.is_active == True,
            ScheduledTask.next_run <= now
        ).all()
        
        for task in tasks:
            cls._run_task(task)
    
    @classmethod
    def _run_task(cls, task):
        """Run a single scheduled task."""
        try:
            if task.task_type == 'job_closing_reminder':
                cls._task_job_closing_reminder(task)
            elif task.task_type == 'interview_reminder':
                cls._task_interview_reminder(task)
            elif task.task_type == 'application_followup':
                cls._task_application_followup(task)
            elif task.task_type == 'document_reminder':
                cls._task_document_reminder(task)
            elif task.task_type == 'cleanup':
                cls._task_cleanup(task)
            
            # Update task run info
            task.last_run = datetime.utcnow()
            task.run_count += 1
            
            # Calculate next run
            if task.schedule_type == 'once':
                task.is_active = False
            elif task.schedule_type == 'daily':
                task.next_run = datetime.combine(
                    datetime.utcnow().date() + timedelta(days=1),
                    task.scheduled_time or datetime.utcnow().time()
                )
            elif task.schedule_type == 'weekly':
                days_ahead = task.day_of_week - datetime.utcnow().weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                task.next_run = datetime.combine(
                    datetime.utcnow().date() + timedelta(days=days_ahead),
                    task.scheduled_time or datetime.utcnow().time()
                )
            elif task.schedule_type == 'monthly':
                next_month = datetime.utcnow().replace(day=1) + timedelta(days=32)
                task.next_run = datetime.combine(
                    next_month.replace(day=min(task.day_of_month or 1, 28)),
                    task.scheduled_time or datetime.utcnow().time()
                )
            
            db.session.commit()
            
        except Exception as e:
            current_app.logger.error(f"Scheduled task failed: {e}")
    
    @classmethod
    def _task_job_closing_reminder(cls, task):
        """Send reminders for jobs approaching closing date."""
        config = task.task_config or {}
        days = config.get('days_before', 3)
        
        target_date = datetime.utcnow().date() + timedelta(days=days)
        
        jobs = JobPosting.query.filter(
            JobPosting.status == 'published',
            JobPosting.closing_date == target_date
        ).all()
        
        for job in jobs:
            # Notify HR about closing jobs
            hr_users = User.query.filter(User.role.in_(['hr_officer', 'admin'])).all()
            for hr in hr_users:
                message = Message(
                    sender_id=task.created_by,
                    recipient_id=hr.id,
                    subject=f"Job Closing Soon: {job.title}",
                    body=f"The job posting '{job.title}' ({job.job_reference}) will close on {job.closing_date}. "
                         f"There are currently {job.applications.count()} applications.",
                    is_system_message=True
                )
                db.session.add(message)
    
    @classmethod
    def _task_interview_reminder(cls, task):
        """Send reminders for upcoming interviews."""
        config = task.task_config or {}
        hours_before = config.get('hours_before', 24)
        
        reminder_time = datetime.utcnow() + timedelta(hours=hours_before)
        
        interviews = Interview.query.filter(
            Interview.status == 'scheduled',
            Interview.scheduled_date <= reminder_time.date(),
            Interview.scheduled_time <= reminder_time.time()
        ).all()
        
        for interview in interviews:
            # Send reminder to applicant
            if interview.application and interview.application.applicant:
                applicant = interview.application.applicant
                job = interview.application.job
                
                send_workflow_email(
                    subject=f"Interview Reminder: {job.title}",
                    recipients=[applicant.email],
                    body=f"This is a reminder that you have an interview scheduled for "
                         f"{interview.scheduled_date} at {interview.scheduled_time}.",
                    html_body=render_template('emails/interview_reminder.html',
                                             interview=interview, applicant=applicant, job=job)
                )
    
    @classmethod
    def _task_application_followup(cls, task):
        """Follow up on applications."""
        config = task.task_config or {}
        application_id = config.get('application_id')
        
        if application_id:
            application = Application.query.get(application_id)
            if application:
                # Create a notification for HR to follow up
                hr_users = User.query.filter(User.role.in_(['hr_officer', 'admin'])).limit(1).all()
                for hr in hr_users:
                    message = Message(
                        sender_id=task.created_by,
                        recipient_id=hr.id,
                        subject=f"Follow-up Required: Application #{application_id}",
                        body=f"This is a reminder to follow up on application #{application_id} "
                             f"for {application.applicant.first_name} {application.applicant.last_name}. "
                             f"Current status: {application.status}",
                        is_system_message=True
                    )
                    db.session.add(message)
    
    @classmethod
    def _task_document_reminder(cls, task):
        """Send reminders for missing documents."""
        config = task.task_config or {}
        days_since_application = config.get('days', 7)
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_since_application)
        
        # Find applications with missing documents
        from app.models import ApplicationDocument
        
        applications = Application.query.filter(
            Application.status.in_(['submitted', 'under_review']),
            Application.application_date <= cutoff_date
        ).all()
        
        for app in applications:
            # Check if mandatory documents are missing
            docs = ApplicationDocument.query.filter_by(application_id=app.id).all()
            doc_types = [d.document_type for d in docs]
            
            required_docs = ['resume', 'id_copy']
            missing = [d for d in required_docs if d not in doc_types]
            
            if missing:
                send_workflow_email(
                    subject="Document Reminder: Complete Your Application",
                    recipients=[app.applicant.email],
                    body=f"Your application for {app.job.title} is missing the following documents: "
                         f"{', '.join(missing)}. Please upload them to complete your application.",
                    html_body=f"<p>Your application for <strong>{app.job.title}</strong> is missing "
                              f"the following documents: {', '.join(missing)}.</p>"
                              f"<p>Please upload them to complete your application.</p>"
                )
    
    @classmethod
    def _task_cleanup(cls, task):
        """Clean up old data."""
        config = task.task_config or {}
        
        # Clean old workflow executions (older than 90 days)
        cutoff = datetime.utcnow() - timedelta(days=config.get('execution_log_days', 90))
        WorkflowExecution.query.filter(
            WorkflowExecution.executed_at < cutoff
        ).delete()
        
        # Clean read messages older than 180 days
        message_cutoff = datetime.utcnow() - timedelta(days=config.get('message_days', 180))
        Message.query.filter(
            Message.is_read == True,
            Message.created_at < message_cutoff
        ).delete()
        
        db.session.commit()


class CommitteeService:
    """Service class for committee management and voting."""
    
    @classmethod
    def create_committee(cls, name, committee_type, created_by, job_id=None, 
                        requires_unanimous=False, min_votes_required=1, description=None):
        """Create a new committee."""
        from app.models import Committee
        
        committee = Committee(
            name=name,
            committee_type=committee_type,
            created_by=created_by,
            job_id=job_id,
            requires_unanimous=requires_unanimous,
            min_votes_required=min_votes_required,
            description=description,
            is_active=True
        )
        db.session.add(committee)
        db.session.commit()
        return committee
    
    @classmethod
    def add_committee_member(cls, committee_id, user_id, role='member'):
        """Add a member to a committee."""
        from app.models import CommitteeMember
        
        # Check if member already exists
        existing = CommitteeMember.query.filter_by(
            committee_id=committee_id, 
            user_id=user_id
        ).first()
        
        if existing:
            existing.is_active = True
            db.session.commit()
            return existing
        
        member = CommitteeMember(
            committee_id=committee_id,
            user_id=user_id,
            role=role,
            is_active=True
        )
        db.session.add(member)
        db.session.commit()
        return member
    
    @classmethod
    def create_committee_decision(cls, committee_id, application_id, job_id):
        """Create a new committee decision record for an application."""
        from app.models import CommitteeDecision, Committee
        
        # Check if decision already exists
        existing = CommitteeDecision.query.filter_by(
            committee_id=committee_id,
            application_id=application_id
        ).first()
        
        if existing:
            return existing
        
        committee = Committee.query.get(committee_id)
        
        decision = CommitteeDecision(
            committee_id=committee_id,
            application_id=application_id,
            job_id=job_id,
            decision='pending',
            individual_votes={}
        )
        db.session.add(decision)
        db.session.commit()
        
        # Notify committee members
        cls._notify_committee_for_review(decision)
        
        return decision
    
    @classmethod
    def cast_vote(cls, decision_id, member_id, vote, comments=None, rating=None):
        """Cast a vote for a committee member."""
        from app.models import CommitteeDecision, CommitteeMemberVote, CommitteeMember
        
        decision = CommitteeDecision.query.get(decision_id)
        if not decision:
            raise ValueError("Decision not found")
        
        member = CommitteeMember.query.get(member_id)
        if not member:
            raise ValueError("Member not found")
        
        # Record the vote
        vote_record = CommitteeMemberVote(
            decision_id=decision_id,
            member_id=member_id,
            vote=vote,
            comments=comments,
            rating=rating
        )
        db.session.add(vote_record)
        
        # Update vote counts
        if vote == 'approved':
            decision.votes_yes += 1
        elif vote == 'rejected':
            decision.votes_no += 1
        else:  # abstain
            decision.votes_abstain += 1
        
        # Update individual votes JSON
        if decision.individual_votes is None:
            decision.individual_votes = {}
        decision.individual_votes[str(member.user_id)] = vote
        
        # Check if decision should be finalized
        cls._check_and_finalize_decision(decision)
        
        db.session.commit()
        return vote_record
    
    @classmethod
    def _check_and_finalize_decision(cls, decision):
        """Check if committee decision can be finalized."""
        from app.models import Committee
        
        committee = decision.committee
        total_members = committee.member_count
        votes_cast = decision.total_votes
        
        # If not all votes received, return early
        if votes_cast < committee.min_votes_required:
            return
        
        # Determine if decision threshold is met
        decision_made = False
        final_decision = 'needs_review'
        
        if committee.requires_unanimous:
            # All votes must be approved
            if decision.votes_yes == total_members:
                decision_made = True
                final_decision = 'approved'
            elif decision.votes_no > 0:
                decision_made = True
                final_decision = 'rejected'
        else:
            # Majority vote determines outcome
            if decision.votes_yes > (total_members / 2):
                decision_made = True
                final_decision = 'approved'
            elif decision.votes_no > (total_members / 2):
                decision_made = True
                final_decision = 'rejected'
        
        if decision_made:
            decision.decision = final_decision
            decision.finalized_at = datetime.utcnow()
            # Find the first chair to finalize
            chair = CommitteeService._get_committee_chair(committee.id)
            if chair:
                decision.finalized_by = chair.user_id
            
            # Trigger workflow based on decision
            cls._apply_committee_decision(decision)
    
    @classmethod
    def _get_committee_chair(cls, committee_id):
        """Get the chair of a committee."""
        from app.models import CommitteeMember
        
        return CommitteeMember.query.filter_by(
            committee_id=committee_id,
            role='chair'
        ).first()
    
    @classmethod
    def _apply_committee_decision(cls, decision):
        """Apply the committee decision to the application status."""
        application = decision.application
        committee = decision.committee
        
        if decision.decision == 'approved':
            # Move to next stage in recruitment
            if committee.committee_type == 'shortlisting':
                # Shortlisting approved, move to interview scheduling
                if WorkflowService.is_valid_transition(application.status, 'interview_scheduled'):
                    # Create notification for HR to schedule interview
                    hr_users = User.query.filter(User.role.in_(['hr_officer', 'admin'])).all()
                    for hr in hr_users:
                        message = Message(
                            sender_id=None,  # System message
                            recipient_id=hr.id,
                            subject=f"Candidate Approved by Shortlisting Committee: {application.applicant.full_name}",
                            body=f"Candidate {application.applicant.full_name} has been approved by the "
                                 f"shortlisting committee for {application.job.title}. "
                                 f"Please schedule an interview.",
                            message_type='application_update'
                        )
                        db.session.add(message)
            
            elif committee.committee_type == 'interviewing':
                # Interview approved, move to offer stage
                if WorkflowService.is_valid_transition(application.status, 'offered'):
                    message_body = f"Candidate {application.applicant.full_name} has been approved by " \
                                 f"the interviewing committee. Prepare an offer letter."
                    
                    hr_users = User.query.filter(User.role.in_(['hr_officer', 'admin'])).all()
                    for hr in hr_users:
                        msg = Message(
                            sender_id=None,
                            recipient_id=hr.id,
                            subject=f"Candidate Approved by Interviewing Committee: {application.applicant.full_name}",
                            body=message_body,
                            message_type='application_update'
                        )
                        db.session.add(msg)
        
        elif decision.decision == 'rejected':
            # Rejection - update application status
            if WorkflowService.is_valid_transition(application.status, 'rejected'):
                WorkflowService.log_status_transition(
                    application.id, application.status, 'rejected',
                    change_type='automated',
                    notes=f"Rejected by {committee.committee_type} committee"
                )
                
                # Notify applicant of rejection
                send_workflow_email(
                    subject=f"Application Status Update: {application.job.title}",
                    recipients=[application.applicant.email],
                    body=f"Thank you for applying for {application.job.title}. Unfortunately, "
                         f"we have decided not to move forward with your application at this time.",
                    html_body=f"<p>Thank you for applying for <strong>{application.job.title}</strong>. "
                              f"Unfortunately, we have decided not to move forward with your application "
                              f"at this time.</p>"
                )
    
    @classmethod
    def _notify_committee_for_review(cls, decision):
        """Notify committee members that a candidate is ready for review."""
        committee = decision.committee
        application = decision.application
        
        for member in committee.members.filter_by(is_active=True).all():
            message = Message(
                sender_id=None,
                recipient_id=member.user_id,
                subject=f"Review Required: {application.applicant.full_name} for {application.job.title}",
                body=f"A candidate requires your review as part of the {committee.committee_type} "
                     f"committee for {application.job.title}.",
                message_type='application_update'
            )
            db.session.add(message)


# Helper function to be called from routes when status changes
def on_application_status_change(application, old_status, new_status, changed_by=None):
    """Handle application status change events."""
    # Log the transition
    WorkflowService.log_status_transition(
        application.id, old_status, new_status,
        changed_by=changed_by,
        change_type='manual' if changed_by else 'system'
    )
    
    # Trigger workflow rules
    WorkflowService.trigger_status_change_rules(application, old_status, new_status, changed_by)
