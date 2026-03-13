"""Authentication routes."""
import os
import uuid
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, current_app, send_from_directory
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.utils import secure_filename
from app import db, mail
from app.auth import auth_bp
from app.models import User, create_audit_log, log_user_activity
from app.forms import LoginForm, RegistrationForm, ProfileForm, ChangePasswordForm, ForgotPasswordForm, ResetPasswordForm
from flask_mail import Message


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user is None or not user.check_password(form.password.data):
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('auth.login'))
        
        if not user.is_active:
            flash('Your account has been deactivated. Please contact support.', 'warning')
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=form.remember_me.data)
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Log the login in audit log
        create_audit_log(
            user_id=user.id,
            action='LOGIN',
            entity_type='User',
            entity_id=user.id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        
        # Log user activity for real-time tracking
        log_user_activity(
            user_id=user.id,
            activity_type='login',
            page='/auth/login',
            description=f'{user.full_name} ({user.role}) logged in',
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        
        flash(f'Welcome back, {user.first_name}!', 'success')
        
        # Redirect based on role
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        
        if user.role in ('hr_officer', 'manager', 'admin'):
            return redirect(url_for('hr.dashboard'))
        return redirect(url_for('applicant.dashboard'))
    
    return render_template('login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """User logout."""
    create_audit_log(
        user_id=current_user.id,
        action='LOGOUT',
        entity_type='User',
        entity_id=current_user.id,
        ip_address=request.remote_addr
    )
    db.session.commit()
    
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration for applicants."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            id_number=form.id_number.data or None,
            phone=form.phone.data or None,
            role='applicant'
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        # Log registration
        create_audit_log(
            user_id=user.id,
            action='REGISTER',
            entity_type='User',
            entity_id=user.id,
            new_values={'username': user.username, 'email': user.email},
            ip_address=request.remote_addr
        )
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('register.html', form=form)


def allowed_profile_picture(filename):
    """Check if file extension is allowed for profile pictures."""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_profile_picture(file):
    """Save uploaded profile picture and return filename."""
    if file and allowed_profile_picture(file.filename):
        # Generate unique filename
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        
        # Create profile_pictures subfolder
        upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profile_pictures')
        os.makedirs(upload_folder, exist_ok=True)
        
        # Save file
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        
        return filename
    return None


@auth_bp.route('/profile-picture/<filename>')
def profile_picture(filename):
    """Serve profile pictures."""
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profile_pictures')
    return send_from_directory(upload_folder, filename)


def save_cropped_image(base64_data):
    """Save a base64 encoded cropped image and return filename."""
    import base64
    import re
    
    # Extract the base64 data (remove data:image/jpeg;base64, prefix)
    match = re.match(r'data:image/(\w+);base64,(.+)', base64_data)
    if not match:
        return None
    
    ext = match.group(1)
    if ext == 'jpeg':
        ext = 'jpg'
    image_data = match.group(2)
    
    # Generate unique filename
    filename = f"{uuid.uuid4().hex}.{ext}"
    
    # Create profile_pictures subfolder
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profile_pictures')
    os.makedirs(upload_folder, exist_ok=True)
    
    # Decode and save
    file_path = os.path.join(upload_folder, filename)
    with open(file_path, 'wb') as f:
        f.write(base64.b64decode(image_data))
    
    return filename


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile page."""
    form = ProfileForm(obj=current_user)
    
    if form.validate_on_submit():
        old_values = {
            'first_name': current_user.first_name,
            'last_name': current_user.last_name,
            'phone': current_user.phone,
            'profile_picture': current_user.profile_picture
        }
        
        # Handle profile picture upload
        if form.profile_picture.data and hasattr(form.profile_picture.data, 'filename') and form.profile_picture.data.filename:
            # Delete old profile picture if exists
            if current_user.profile_picture:
                old_pic_path = os.path.join(
                    current_app.config['UPLOAD_FOLDER'], 
                    'profile_pictures', 
                    current_user.profile_picture
                )
                if os.path.exists(old_pic_path):
                    os.remove(old_pic_path)
            
            # Save new picture
            new_filename = save_profile_picture(form.profile_picture.data)
            if new_filename:
                current_user.profile_picture = new_filename
        
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.phone = form.phone.data
        current_user.gender = form.gender.data or None
        current_user.race = form.race.data or None
        current_user.disability_status = form.disability_status.data
        
        db.session.commit()
        
        create_audit_log(
            user_id=current_user.id,
            action='UPDATE_PROFILE',
            entity_type='User',
            entity_id=current_user.id,
            old_values=old_values,
            new_values={
                'first_name': current_user.first_name,
                'last_name': current_user.last_name,
                'phone': current_user.phone,
                'profile_picture': current_user.profile_picture
            },
            ip_address=request.remote_addr
        )
        db.session.commit()
        
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('profile.html', form=form)


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change password."""
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('auth.change_password'))
        
        current_user.set_password(form.new_password.data)
        db.session.commit()
        
        create_audit_log(
            user_id=current_user.id,
            action='CHANGE_PASSWORD',
            entity_type='User',
            entity_id=current_user.id,
            ip_address=request.remote_addr
        )
        db.session.commit()
        
        flash('Password changed successfully.', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('change_password.html', form=form)


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request password reset."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        
        if user:
            # Generate reset token
            token = user.get_reset_password_token()
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            
            # Send email
            try:
                msg = Message(
                    subject='Password Reset Request - E-Recruitment Portal',
                    recipients=[user.email],
                    sender=current_app.config.get('MAIL_DEFAULT_SENDER')
                )
                msg.body = f'''Dear {user.first_name},

You have requested to reset your password for the E-Recruitment Portal.

Click the link below to reset your password:
{reset_url}

This link will expire in 1 hour.

If you did not request a password reset, please ignore this email.

Best regards,
E-Recruitment Team
'''
                msg.html = f'''
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; text-align: center;">
        <h1 style="color: white; margin: 0;">E-Recruitment Portal</h1>
    </div>
    <div style="padding: 30px; background: #f9f9f9;">
        <h2 style="color: #333;">Password Reset Request</h2>
        <p>Dear {user.first_name},</p>
        <p>You have requested to reset your password for the E-Recruitment Portal.</p>
        <p style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}" style="background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                Reset Password
            </a>
        </p>
        <p style="color: #666; font-size: 14px;">This link will expire in 1 hour.</p>
        <p style="color: #666; font-size: 14px;">If you did not request a password reset, please ignore this email.</p>
    </div>
    <div style="padding: 15px; background: #333; color: #fff; text-align: center; font-size: 12px;">
        E-Recruitment Portal &copy; 2026
    </div>
</div>
'''
                mail.send(msg)
                
                create_audit_log(
                    user_id=user.id,
                    action='PASSWORD_RESET_REQUEST',
                    entity_type='User',
                    entity_id=user.id,
                    ip_address=request.remote_addr
                )
                db.session.commit()
                
            except Exception as e:
                current_app.logger.error(f'Failed to send password reset email: {e}')
        
        # Always show success message to prevent email enumeration
        flash('If an account with that email exists, we have sent a password reset link.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('forgot_password.html', form=form)


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password with token."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    user = User.verify_reset_password_token(token)
    if not user:
        flash('Invalid or expired reset link. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        
        create_audit_log(
            user_id=user.id,
            action='PASSWORD_RESET',
            entity_type='User',
            entity_id=user.id,
            ip_address=request.remote_addr
        )
        db.session.commit()
        
        flash('Your password has been reset successfully. You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('reset_password.html', form=form)
