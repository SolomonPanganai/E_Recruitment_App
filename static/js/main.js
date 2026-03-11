// E-Recruitment Portal - Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    // Theme preview for admin system settings
    const themeSelect = document.getElementById('theme');
    if (themeSelect) {
        themeSelect.addEventListener('change', function() {
            const selectedTheme = themeSelect.value;
            document.body.className = document.body.className.replace(/theme-[a-z]+/g, '').trim();
            document.body.classList.add('theme-' + selectedTheme);
        });
    }
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // File upload drag and drop
    var fileUploads = document.querySelectorAll('.file-upload');
    fileUploads.forEach(function(upload) {
        upload.addEventListener('dragover', function(e) {
            e.preventDefault();
            this.classList.add('dragover');
        });

        upload.addEventListener('dragleave', function(e) {
            e.preventDefault();
            this.classList.remove('dragover');
        });

        upload.addEventListener('drop', function(e) {
            e.preventDefault();
            this.classList.remove('dragover');
            var input = this.querySelector('input[type="file"]');
            if (input && e.dataTransfer.files.length) {
                input.files = e.dataTransfer.files;
                updateFileLabel(input);
            }
        });
    });

    // File input change handler
    document.querySelectorAll('input[type="file"]').forEach(function(input) {
        input.addEventListener('change', function() {
            updateFileLabel(this);
        });
    });

    // Confirm delete actions
    document.querySelectorAll('[data-confirm]').forEach(function(element) {
        element.addEventListener('click', function(e) {
            if (!confirm(this.dataset.confirm || 'Are you sure?')) {
                e.preventDefault();
            }
        });
    });

    // Form validation
    var forms = document.querySelectorAll('.needs-validation');
    forms.forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });

    // Search debounce for live search
    var searchInputs = document.querySelectorAll('[data-live-search]');
    searchInputs.forEach(function(input) {
        var timeout;
        input.addEventListener('input', function() {
            clearTimeout(timeout);
            timeout = setTimeout(function() {
                input.form.submit();
            }, 500);
        });
    });

    // Character counter for textareas
    document.querySelectorAll('textarea[maxlength]').forEach(function(textarea) {
        var maxLength = textarea.getAttribute('maxlength');
        var counter = document.createElement('small');
        counter.className = 'text-muted float-end';
        counter.textContent = '0 / ' + maxLength;
        textarea.parentNode.appendChild(counter);

        textarea.addEventListener('input', function() {
            counter.textContent = this.value.length + ' / ' + maxLength;
        });
    });

    // Print button
    document.querySelectorAll('[data-print]').forEach(function(btn) {
        btn.addEventListener('click', function() {
            window.print();
        });
    });
});

// Update file input label with selected filename
function updateFileLabel(input) {
    var label = input.nextElementSibling;
    if (label && label.classList.contains('form-label')) {
        if (input.files.length > 1) {
            label.textContent = input.files.length + ' files selected';
        } else if (input.files.length === 1) {
            label.textContent = input.files[0].name;
        }
    }
}

// Show loading spinner
function showLoading() {
    var overlay = document.createElement('div');
    overlay.className = 'spinner-overlay';
    overlay.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div>';
    document.body.appendChild(overlay);
}

// Hide loading spinner
function hideLoading() {
    var overlay = document.querySelector('.spinner-overlay');
    if (overlay) {
        overlay.remove();
    }
}

// Show toast notification
function showToast(message, type) {
    type = type || 'info';
    var container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    var toast = document.createElement('div');
    toast.className = 'toast show bg-' + type + ' text-white';
    toast.innerHTML = '<div class="toast-body">' + message + '</div>';
    container.appendChild(toast);

    setTimeout(function() {
        toast.remove();
    }, 3000);
}

// AJAX form submission
function submitFormAjax(form, callback) {
    var formData = new FormData(form);
    
    showLoading();
    
    fetch(form.action, {
        method: form.method,
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(function(response) {
        return response.json();
    })
    .then(function(data) {
        hideLoading();
        if (callback) {
            callback(data);
        }
    })
    .catch(function(error) {
        hideLoading();
        showToast('An error occurred. Please try again.', 'danger');
        console.error('Error:', error);
    });
}

// Table row selection
function initTableSelection(tableId) {
    var table = document.getElementById(tableId);
    if (!table) return;

    var selectAll = table.querySelector('input[data-select-all]');
    var checkboxes = table.querySelectorAll('input[data-row-select]');

    if (selectAll) {
        selectAll.addEventListener('change', function() {
            checkboxes.forEach(function(checkbox) {
                checkbox.checked = selectAll.checked;
            });
        });
    }

    checkboxes.forEach(function(checkbox) {
        checkbox.addEventListener('change', function() {
            var allChecked = Array.from(checkboxes).every(function(cb) {
                return cb.checked;
            });
            if (selectAll) {
                selectAll.checked = allChecked;
            }
        });
    });
}

// Date formatting helper
function formatDate(date, format) {
    format = format || 'dd MMM yyyy';
    var d = new Date(date);
    var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    
    return format
        .replace('dd', String(d.getDate()).padStart(2, '0'))
        .replace('MMM', months[d.getMonth()])
        .replace('yyyy', d.getFullYear());
}
