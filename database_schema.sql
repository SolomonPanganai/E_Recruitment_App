-- E-Recruitment Portal Database Schema
-- MySQL 8.0+ recommended

CREATE DATABASE e_recruit_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE e_recruit_db;

-- SYSTEM SETTINGS
CREATE TABLE system_settings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    system_name VARCHAR(200) NOT NULL DEFAULT 'E-Recruitment Portal',
    theme VARCHAR(50) NOT NULL DEFAULT 'default',
    logo VARCHAR(255),
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- USERS
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(64) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    role ENUM('applicant','hr_officer','manager','admin') NOT NULL DEFAULT 'applicant',
    id_number VARCHAR(13) UNIQUE,
    first_name VARCHAR(64) NOT NULL,
    last_name VARCHAR(64) NOT NULL,
    phone VARCHAR(20),
    profile_picture VARCHAR(255),
    gender ENUM('male','female','other','prefer_not_to_say'),
    race ENUM('african','coloured','indian','white','other','prefer_not_to_say'),
    disability_status BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    last_login DATETIME
);

-- JOB POSTINGS
CREATE TABLE job_postings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    job_reference VARCHAR(50) NOT NULL UNIQUE,
    title VARCHAR(200) NOT NULL,
    department VARCHAR(100) NOT NULL,
    location VARCHAR(200) NOT NULL,
    job_purpose TEXT NOT NULL,
    responsibilities TEXT NOT NULL,
    minimum_requirements JSON NOT NULL,
    preferred_requirements JSON,
    salary_range VARCHAR(100),
    posting_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    closing_date DATETIME NOT NULL,
    status ENUM('draft','pending_approval','published','closed') NOT NULL DEFAULT 'draft',
    ee_target_category VARCHAR(100),
    sharepoint_folder_path VARCHAR(500),
    created_by INT NOT NULL,
    approved_by INT,
    approved_date DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    views_count INT DEFAULT 0,
    applications_count INT DEFAULT 0,
    FOREIGN KEY (created_by) REFERENCES users(id),
    FOREIGN KEY (approved_by) REFERENCES users(id)
);

-- APPLICATIONS
CREATE TABLE applications (
    id INT PRIMARY KEY AUTO_INCREMENT,
    application_reference VARCHAR(50) NOT NULL UNIQUE,
    job_id INT NOT NULL,
    applicant_id INT NOT NULL,
    application_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    status ENUM('submitted','under_review','shortlisted','interviewed','offered','rejected','withdrawn') NOT NULL DEFAULT 'submitted',
    current_stage VARCHAR(100) DEFAULT 'Screening',
    screening_score FLOAT,
    interview_score FLOAT,
    notes TEXT,
    cover_letter TEXT,
    sharepoint_folder_path VARCHAR(500),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES job_postings(id),
    FOREIGN KEY (applicant_id) REFERENCES users(id)
);

-- DOCUMENTS
CREATE TABLE documents (
    id INT PRIMARY KEY AUTO_INCREMENT,
    application_id INT,
    job_posting_id INT,
    file_name VARCHAR(255) NOT NULL,
    sharepoint_url VARCHAR(1000),
    local_path VARCHAR(500),
    document_type ENUM('cv','id','qualification','offer_letter','reference','other') NOT NULL,
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    uploaded_by INT NOT NULL,
    file_size INT,
    mime_type VARCHAR(100),
    FOREIGN KEY (application_id) REFERENCES applications(id),
    FOREIGN KEY (job_posting_id) REFERENCES job_postings(id),
    FOREIGN KEY (uploaded_by) REFERENCES users(id)
);

-- SHORTLISTS
CREATE TABLE shortlists (
    id INT PRIMARY KEY AUTO_INCREMENT,
    application_id INT NOT NULL UNIQUE,
    job_id INT NOT NULL,
    shortlisted_by INT NOT NULL,
    shortlisted_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    ranking INT,
    FOREIGN KEY (application_id) REFERENCES applications(id),
    FOREIGN KEY (job_id) REFERENCES job_postings(id),
    FOREIGN KEY (shortlisted_by) REFERENCES users(id)
);

-- INTERVIEWS
CREATE TABLE interviews (
    id INT PRIMARY KEY AUTO_INCREMENT,
    application_id INT NOT NULL,
    scheduled_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    location VARCHAR(500) NOT NULL,
    interview_type ENUM('in_person','video','phone') DEFAULT 'in_person',
    panel JSON,
    feedback TEXT,
    score FLOAT,
    status ENUM('scheduled','completed','cancelled','no_show') DEFAULT 'scheduled',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (application_id) REFERENCES applications(id)
);

-- OFFERS
CREATE TABLE offers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    application_id INT NOT NULL UNIQUE,
    offer_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    salary_offered VARCHAR(100) NOT NULL,
    start_date_proposed DATE NOT NULL,
    terms TEXT,
    status ENUM('pending','accepted','declined','expired') DEFAULT 'pending',
    response_deadline DATETIME,
    accepted_date DATETIME,
    sharepoint_document_url VARCHAR(1000),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (application_id) REFERENCES applications(id)
);

-- AUDIT LOGS
CREATE TABLE audit_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id INT,
    old_values JSON,
    new_values JSON,
    description TEXT,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
