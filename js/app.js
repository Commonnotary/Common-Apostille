/**
 * Common Notary Apostille - CRM Dashboard
 * Lightweight case management system with CRUD operations
 */

// Status Pipeline Configuration
const STATUS_PIPELINE = [
    'Received',
    'Reviewed',
    'Payment Collected',
    'In Process',
    'Shipped/Walk-in',
    'Returned',
    'Delivered',
    'Closed'
];

// Storage key
const STORAGE_KEY = 'commonApostilleCases';

// Current update tab (email or text)
let currentUpdateTab = 'email';
let currentUpdateCase = null;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    loadCases();
    updatePipelineCounts();
    populateRegionFilter();

    // Add click handlers to pipeline stages
    document.querySelectorAll('.pipeline-stage').forEach(stage => {
        stage.addEventListener('click', function() {
            const status = this.dataset.status;
            document.getElementById('statusFilter').value = status;
            filterCases();

            // Update active state
            document.querySelectorAll('.pipeline-stage').forEach(s => s.classList.remove('active'));
            this.classList.add('active');
        });
    });
});

// Generate unique case ID
function generateCaseId() {
    const prefix = 'CNA';
    const timestamp = Date.now().toString(36).toUpperCase();
    const random = Math.random().toString(36).substring(2, 5).toUpperCase();
    return `${prefix}-${timestamp}${random}`;
}

// Get cases from localStorage
function getCases() {
    const data = localStorage.getItem(STORAGE_KEY);
    return data ? JSON.parse(data) : [];
}

// Save cases to localStorage
function saveCases(cases) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cases));
}

// Load and display cases
function loadCases() {
    const cases = getCases();
    displayCases(cases);
    updatePipelineCounts();
}

// Display cases in the table
function displayCases(cases) {
    const tbody = document.getElementById('casesTableBody');
    const emptyState = document.getElementById('emptyState');

    if (cases.length === 0) {
        tbody.innerHTML = '';
        emptyState.classList.add('show');
        return;
    }

    emptyState.classList.remove('show');

    // Sort by created date (newest first)
    cases.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));

    tbody.innerHTML = cases.map(c => {
        const statusClass = getStatusClass(c.status);
        const dueDateClass = getDueDateClass(c.dueDate);
        const formattedDueDate = c.dueDate ? formatDate(c.dueDate) : '-';
        const formattedPrice = c.price ? `$${parseFloat(c.price).toFixed(2)}` : '-';

        return `
            <tr>
                <td><span class="case-id">${c.id}</span></td>
                <td><span class="client-name">${escapeHtml(c.clientName)}</span></td>
                <td>${escapeHtml(c.documentType)}</td>
                <td>${escapeHtml(c.region)}</td>
                <td><span class="status-badge ${statusClass}">${c.status}</span></td>
                <td><span class="due-date ${dueDateClass}">${formattedDueDate}</span></td>
                <td><span class="price">${formattedPrice}</span></td>
                <td>${c.trackingNumber ? `<span class="tracking-link">${escapeHtml(c.trackingNumber)}</span>` : '-'}</td>
                <td class="actions-cell">
                    <button class="action-btn view" onclick="viewCase('${c.id}')" title="View Details">View</button>
                    <button class="action-btn edit" onclick="editCase('${c.id}')" title="Edit Case">Edit</button>
                    <button class="action-btn update" onclick="openClientUpdate('${c.id}')" title="Send Client Update">Update</button>
                    <button class="action-btn delete" onclick="deleteCase('${c.id}')" title="Delete Case">Delete</button>
                </td>
            </tr>
        `;
    }).join('');
}

// Get CSS class for status badge
function getStatusClass(status) {
    return 'status-' + status.toLowerCase().replace(/[\s\/]/g, '-');
}

// Get CSS class for due date based on urgency
function getDueDateClass(dueDate) {
    if (!dueDate) return '';

    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const due = new Date(dueDate);
    const diffDays = Math.ceil((due - today) / (1000 * 60 * 60 * 24));

    if (diffDays < 0) return 'overdue';
    if (diffDays <= 3) return 'due-soon';
    return '';
}

// Format date for display
function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

// Escape HTML to prevent XSS
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Update pipeline stage counts
function updatePipelineCounts() {
    const cases = getCases();

    STATUS_PIPELINE.forEach(status => {
        const count = cases.filter(c => c.status === status).length;
        const countId = 'count-' + status.toLowerCase().replace(/[\s\/]/g, '-');
        const element = document.getElementById(countId);
        if (element) {
            element.textContent = count;
        }
    });
}

// Populate region filter with unique regions from cases
function populateRegionFilter() {
    const cases = getCases();
    const regions = [...new Set(cases.map(c => c.region).filter(Boolean))];
    const select = document.getElementById('regionFilter');

    // Keep the "All Regions" option
    select.innerHTML = '<option value="">All Regions</option>';

    regions.sort().forEach(region => {
        const option = document.createElement('option');
        option.value = region;
        option.textContent = region;
        select.appendChild(option);
    });
}

// Filter cases based on search and filters
function filterCases() {
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    const statusFilter = document.getElementById('statusFilter').value;
    const regionFilter = document.getElementById('regionFilter').value;

    let cases = getCases();

    if (searchTerm) {
        cases = cases.filter(c =>
            c.clientName.toLowerCase().includes(searchTerm) ||
            c.documentType.toLowerCase().includes(searchTerm) ||
            (c.trackingNumber && c.trackingNumber.toLowerCase().includes(searchTerm)) ||
            c.id.toLowerCase().includes(searchTerm) ||
            (c.notes && c.notes.toLowerCase().includes(searchTerm))
        );
    }

    if (statusFilter) {
        cases = cases.filter(c => c.status === statusFilter);
    }

    if (regionFilter) {
        cases = cases.filter(c => c.region === regionFilter);
    }

    displayCases(cases);

    // Update active pipeline stage
    document.querySelectorAll('.pipeline-stage').forEach(stage => {
        stage.classList.toggle('active', stage.dataset.status === statusFilter);
    });
}

// Open modal for adding or editing a case
function openModal(mode, caseData = null) {
    const modal = document.getElementById('caseModal');
    const title = document.getElementById('modalTitle');
    const form = document.getElementById('caseForm');

    form.reset();

    if (mode === 'edit' && caseData) {
        title.textContent = 'Edit Case';
        document.getElementById('caseId').value = caseData.id;
        document.getElementById('clientName').value = caseData.clientName || '';
        document.getElementById('clientEmail').value = caseData.clientEmail || '';
        document.getElementById('clientPhone').value = caseData.clientPhone || '';
        document.getElementById('documentType').value = caseData.documentType || '';
        document.getElementById('region').value = caseData.region || '';
        document.getElementById('status').value = caseData.status || 'Received';
        document.getElementById('dueDate').value = caseData.dueDate || '';
        document.getElementById('price').value = caseData.price || '';
        document.getElementById('trackingNumber').value = caseData.trackingNumber || '';
        document.getElementById('returnTrackingNumber').value = caseData.returnTrackingNumber || '';
        document.getElementById('notes').value = caseData.notes || '';
    } else {
        title.textContent = 'Add New Case';
        document.getElementById('caseId').value = '';
        document.getElementById('status').value = 'Received';
    }

    modal.classList.add('show');
}

// Close the add/edit modal
function closeModal() {
    document.getElementById('caseModal').classList.remove('show');
}

// Save a case (create or update)
function saveCase(event) {
    event.preventDefault();

    const caseId = document.getElementById('caseId').value;
    const isEdit = Boolean(caseId);

    const caseData = {
        id: caseId || generateCaseId(),
        clientName: document.getElementById('clientName').value.trim(),
        clientEmail: document.getElementById('clientEmail').value.trim(),
        clientPhone: document.getElementById('clientPhone').value.trim(),
        documentType: document.getElementById('documentType').value,
        region: document.getElementById('region').value,
        status: document.getElementById('status').value,
        dueDate: document.getElementById('dueDate').value,
        price: document.getElementById('price').value,
        trackingNumber: document.getElementById('trackingNumber').value.trim(),
        returnTrackingNumber: document.getElementById('returnTrackingNumber').value.trim(),
        notes: document.getElementById('notes').value.trim(),
        updatedAt: new Date().toISOString()
    };

    let cases = getCases();

    if (isEdit) {
        const index = cases.findIndex(c => c.id === caseId);
        if (index !== -1) {
            caseData.createdAt = cases[index].createdAt;
            cases[index] = caseData;
        }
    } else {
        caseData.createdAt = new Date().toISOString();
        cases.push(caseData);
    }

    saveCases(cases);
    closeModal();
    loadCases();
    populateRegionFilter();

    showToast(isEdit ? 'Case updated successfully!' : 'Case created successfully!', 'success');
}

// Edit a case
function editCase(caseId) {
    const cases = getCases();
    const caseData = cases.find(c => c.id === caseId);

    if (caseData) {
        openModal('edit', caseData);
    }
}

// Delete a case
function deleteCase(caseId) {
    if (!confirm('Are you sure you want to delete this case? This action cannot be undone.')) {
        return;
    }

    let cases = getCases();
    cases = cases.filter(c => c.id !== caseId);
    saveCases(cases);
    loadCases();
    populateRegionFilter();

    showToast('Case deleted successfully!', 'success');
}

// View case details
function viewCase(caseId) {
    const cases = getCases();
    const caseData = cases.find(c => c.id === caseId);

    if (!caseData) return;

    const statusIndex = STATUS_PIPELINE.indexOf(caseData.status);

    const detailsHtml = `
        <div class="case-detail-header">
            <div class="case-detail-title">
                <h3>${escapeHtml(caseData.clientName)}</h3>
                <span class="case-detail-id">${caseData.id}</span>
            </div>
            <span class="status-badge ${getStatusClass(caseData.status)}">${caseData.status}</span>
        </div>

        <div class="status-timeline">
            ${STATUS_PIPELINE.map((status, index) => {
                const isCompleted = index < statusIndex;
                const isCurrent = index === statusIndex;
                return `
                    <div class="timeline-step">
                        <span class="timeline-dot ${isCompleted ? 'completed' : ''} ${isCurrent ? 'current' : ''}" title="${status}"></span>
                        ${index < STATUS_PIPELINE.length - 1 ? `<span class="timeline-line ${isCompleted ? 'completed' : ''}"></span>` : ''}
                    </div>
                `;
            }).join('')}
        </div>

        <div class="detail-grid">
            <div class="detail-item">
                <div class="detail-label">Document Type</div>
                <div class="detail-value">${escapeHtml(caseData.documentType) || '-'}</div>
            </div>
            <div class="detail-item">
                <div class="detail-label">Destination Region</div>
                <div class="detail-value">${escapeHtml(caseData.region) || '-'}</div>
            </div>
            <div class="detail-item">
                <div class="detail-label">Client Email</div>
                <div class="detail-value">${caseData.clientEmail ? `<a href="mailto:${escapeHtml(caseData.clientEmail)}">${escapeHtml(caseData.clientEmail)}</a>` : '-'}</div>
            </div>
            <div class="detail-item">
                <div class="detail-label">Client Phone</div>
                <div class="detail-value">${caseData.clientPhone ? `<a href="tel:${escapeHtml(caseData.clientPhone)}">${escapeHtml(caseData.clientPhone)}</a>` : '-'}</div>
            </div>
            <div class="detail-item">
                <div class="detail-label">Due Date</div>
                <div class="detail-value ${getDueDateClass(caseData.dueDate)}">${caseData.dueDate ? formatDate(caseData.dueDate) : '-'}</div>
            </div>
            <div class="detail-item">
                <div class="detail-label">Price</div>
                <div class="detail-value">${caseData.price ? '$' + parseFloat(caseData.price).toFixed(2) : '-'}</div>
            </div>
            <div class="detail-item">
                <div class="detail-label">Outgoing Tracking #</div>
                <div class="detail-value">${escapeHtml(caseData.trackingNumber) || '-'}</div>
            </div>
            <div class="detail-item">
                <div class="detail-label">Return Tracking #</div>
                <div class="detail-value">${escapeHtml(caseData.returnTrackingNumber) || '-'}</div>
            </div>
            <div class="detail-item">
                <div class="detail-label">Created</div>
                <div class="detail-value">${caseData.createdAt ? formatDate(caseData.createdAt) : '-'}</div>
            </div>
            <div class="detail-item">
                <div class="detail-label">Last Updated</div>
                <div class="detail-value">${caseData.updatedAt ? formatDate(caseData.updatedAt) : '-'}</div>
            </div>
        </div>

        ${caseData.notes ? `
            <div class="detail-notes">
                <h4>Notes</h4>
                <p>${escapeHtml(caseData.notes)}</p>
            </div>
        ` : ''}

        <div class="detail-actions">
            <button class="btn btn-secondary" onclick="closeViewModal()">Close</button>
            <button class="btn btn-success" onclick="closeViewModal(); openClientUpdate('${caseData.id}')">
                <span class="icon">&#9993;</span> Send Client Update
            </button>
            <button class="btn btn-primary" onclick="closeViewModal(); editCase('${caseData.id}')">
                <span class="icon">&#9998;</span> Edit Case
            </button>
        </div>
    `;

    document.getElementById('caseDetails').innerHTML = detailsHtml;
    document.getElementById('viewModal').classList.add('show');
}

// Close view modal
function closeViewModal() {
    document.getElementById('viewModal').classList.remove('show');
}

// Open client update modal
function openClientUpdate(caseId) {
    const cases = getCases();
    currentUpdateCase = cases.find(c => c.id === caseId);

    if (!currentUpdateCase) return;

    currentUpdateTab = 'email';
    updateTabButtons();
    generateUpdateMessage();

    document.getElementById('updateModal').classList.add('show');
}

// Close update modal
function closeUpdateModal() {
    document.getElementById('updateModal').classList.remove('show');
    currentUpdateCase = null;
}

// Switch between email and text tabs
function switchUpdateTab(tab) {
    currentUpdateTab = tab;
    updateTabButtons();
    generateUpdateMessage();
}

// Update tab button states
function updateTabButtons() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.textContent.toLowerCase().includes(currentUpdateTab));
    });

    const sendBtn = document.getElementById('sendEmailBtn');
    if (currentUpdateTab === 'email') {
        sendBtn.innerHTML = '<span class="icon">&#9993;</span> Open Email Client';
        sendBtn.onclick = openEmailClient;
    } else {
        sendBtn.innerHTML = '<span class="icon">&#128241;</span> Open SMS';
        sendBtn.onclick = openSMS;
    }
}

// Generate update message based on status
function generateUpdateMessage() {
    if (!currentUpdateCase) return;

    const c = currentUpdateCase;
    const firstName = c.clientName.split(' ')[0];

    let message = '';
    let subject = '';

    // Status-specific messages
    const statusMessages = {
        'Received': {
            subject: `Document Received - Case ${c.id}`,
            email: `Dear ${firstName},

Thank you for choosing Common Notary Apostille for your document authentication needs.

We have received your ${c.documentType} for ${c.region} processing. Your case reference number is ${c.id}.

We will begin reviewing your documents shortly and will keep you updated on the progress.

If you have any questions, please don't hesitate to reach out.

Best regards,
Common Notary Apostille Team`,
            text: `Hi ${firstName}, Common Notary Apostille here. We've received your ${c.documentType} (Case ${c.id}). We'll update you once reviewed. Questions? Reply to this message.`
        },
        'Reviewed': {
            subject: `Documents Reviewed - Case ${c.id}`,
            email: `Dear ${firstName},

Good news! We have reviewed your ${c.documentType} for ${c.region} and everything looks in order.

Case Reference: ${c.id}
${c.price ? `Total Amount Due: $${parseFloat(c.price).toFixed(2)}` : ''}

Please proceed with payment so we can begin processing your documents. Once payment is received, we will expedite your request.

Best regards,
Common Notary Apostille Team`,
            text: `Hi ${firstName}, your ${c.documentType} has been reviewed and approved (Case ${c.id}).${c.price ? ` Amount due: $${parseFloat(c.price).toFixed(2)}.` : ''} Please complete payment to proceed.`
        },
        'Payment Collected': {
            subject: `Payment Confirmed - Case ${c.id}`,
            email: `Dear ${firstName},

Thank you! We have received your payment for Case ${c.id}.

Your ${c.documentType} is now in our processing queue for ${c.region}. We will begin the authentication process immediately.

${c.dueDate ? `Estimated completion: ${formatDate(c.dueDate)}` : 'We will notify you of the expected completion date shortly.'}

Best regards,
Common Notary Apostille Team`,
            text: `Hi ${firstName}, payment received for Case ${c.id}! Your ${c.documentType} is now being processed.${c.dueDate ? ` Est. completion: ${formatDate(c.dueDate)}.` : ''}`
        },
        'In Process': {
            subject: `Processing Update - Case ${c.id}`,
            email: `Dear ${firstName},

Your ${c.documentType} is currently being processed for ${c.region} authentication.

Case Reference: ${c.id}
${c.dueDate ? `Expected Completion: ${formatDate(c.dueDate)}` : ''}

We are working diligently to complete your request. You will receive an update once your documents have been authenticated and are ready for shipping.

Best regards,
Common Notary Apostille Team`,
            text: `Hi ${firstName}, update on Case ${c.id}: Your ${c.documentType} is in process for ${c.region}.${c.dueDate ? ` Expected by ${formatDate(c.dueDate)}.` : ''} Stay tuned!`
        },
        'Shipped/Walk-in': {
            subject: `Documents Shipped - Case ${c.id}`,
            email: `Dear ${firstName},

Great news! Your authenticated ${c.documentType} has been shipped!

Case Reference: ${c.id}
${c.trackingNumber ? `Tracking Number: ${c.trackingNumber}` : ''}
${c.returnTrackingNumber ? `Return Tracking: ${c.returnTrackingNumber}` : ''}

You can track your package using the tracking number above. Please allow 1-2 business days for tracking information to update.

Best regards,
Common Notary Apostille Team`,
            text: `Hi ${firstName}, your documents have shipped! Case ${c.id}.${c.trackingNumber ? ` Track: ${c.trackingNumber}` : ''} Contact us with any questions!`
        },
        'Returned': {
            subject: `Documents Returned to Us - Case ${c.id}`,
            email: `Dear ${firstName},

We wanted to let you know that the documents for Case ${c.id} have been returned to our office.

We are currently reviewing the situation and will contact you shortly with next steps.

If you have any immediate questions, please don't hesitate to reach out.

Best regards,
Common Notary Apostille Team`,
            text: `Hi ${firstName}, Case ${c.id}: Your documents have been returned to us. We'll contact you shortly with details. Questions? Reply here.`
        },
        'Delivered': {
            subject: `Documents Delivered - Case ${c.id}`,
            email: `Dear ${firstName},

Your authenticated ${c.documentType} has been delivered!

Case Reference: ${c.id}

We hope everything is in order. If you have any questions or need any additional services in the future, please don't hesitate to contact us.

Thank you for choosing Common Notary Apostille. We appreciate your business!

Best regards,
Common Notary Apostille Team`,
            text: `Hi ${firstName}, your ${c.documentType} has been delivered (Case ${c.id})! Thank you for choosing Common Notary Apostille. Need help? Contact us anytime!`
        },
        'Closed': {
            subject: `Case Completed - ${c.id}`,
            email: `Dear ${firstName},

Your case ${c.id} has been completed and closed.

Document Type: ${c.documentType}
Destination: ${c.region}

Thank you for trusting Common Notary Apostille with your document authentication needs. We look forward to serving you again in the future!

For your records, please keep this case number: ${c.id}

Best regards,
Common Notary Apostille Team`,
            text: `Hi ${firstName}, Case ${c.id} is now closed. Thank you for choosing Common Notary Apostille! Save this case # for your records. See you next time!`
        }
    };

    const templates = statusMessages[c.status] || statusMessages['Received'];

    if (currentUpdateTab === 'email') {
        message = `<div class="subject-line">Subject: ${templates.subject}</div>${templates.email}`;
        subject = templates.subject;
    } else {
        message = templates.text;
    }

    document.getElementById('updatePreview').innerHTML = message;
}

// Copy message to clipboard
function copyToClipboard() {
    const preview = document.getElementById('updatePreview');
    let text = preview.innerText;

    // Remove "Subject: " prefix for cleaner copy
    text = text.replace(/^Subject: .+\n/, '');

    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard!', 'success');
    }).catch(() => {
        // Fallback for older browsers
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        showToast('Copied to clipboard!', 'success');
    });
}

// Open email client with pre-filled message
function openEmailClient() {
    if (!currentUpdateCase || !currentUpdateCase.clientEmail) {
        showToast('No email address available for this client.', 'error');
        return;
    }

    const c = currentUpdateCase;
    const statusMessages = getStatusMessages(c);
    const subject = encodeURIComponent(statusMessages.subject);
    const body = encodeURIComponent(statusMessages.email);

    window.location.href = `mailto:${c.clientEmail}?subject=${subject}&body=${body}`;
}

// Open SMS with pre-filled message
function openSMS() {
    if (!currentUpdateCase || !currentUpdateCase.clientPhone) {
        showToast('No phone number available for this client.', 'error');
        return;
    }

    const c = currentUpdateCase;
    const statusMessages = getStatusMessages(c);
    const body = encodeURIComponent(statusMessages.text);

    // Use sms: protocol (works on mobile devices)
    window.location.href = `sms:${c.clientPhone}?body=${body}`;
}

// Get status-specific messages for a case
function getStatusMessages(c) {
    const firstName = c.clientName.split(' ')[0];

    const messages = {
        'Received': {
            subject: `Document Received - Case ${c.id}`,
            email: `Dear ${firstName},\n\nThank you for choosing Common Notary Apostille for your document authentication needs.\n\nWe have received your ${c.documentType} for ${c.region} processing. Your case reference number is ${c.id}.\n\nWe will begin reviewing your documents shortly and will keep you updated on the progress.\n\nIf you have any questions, please don't hesitate to reach out.\n\nBest regards,\nCommon Notary Apostille Team`,
            text: `Hi ${firstName}, Common Notary Apostille here. We've received your ${c.documentType} (Case ${c.id}). We'll update you once reviewed.`
        },
        'Reviewed': {
            subject: `Documents Reviewed - Case ${c.id}`,
            email: `Dear ${firstName},\n\nGood news! We have reviewed your ${c.documentType} for ${c.region} and everything looks in order.\n\nCase Reference: ${c.id}\n${c.price ? `Total Amount Due: $${parseFloat(c.price).toFixed(2)}` : ''}\n\nPlease proceed with payment so we can begin processing your documents.\n\nBest regards,\nCommon Notary Apostille Team`,
            text: `Hi ${firstName}, your ${c.documentType} has been reviewed (Case ${c.id}).${c.price ? ` Amount due: $${parseFloat(c.price).toFixed(2)}.` : ''} Please complete payment.`
        },
        'Payment Collected': {
            subject: `Payment Confirmed - Case ${c.id}`,
            email: `Dear ${firstName},\n\nThank you! We have received your payment for Case ${c.id}.\n\nYour ${c.documentType} is now in our processing queue for ${c.region}.\n\n${c.dueDate ? `Estimated completion: ${formatDate(c.dueDate)}` : ''}\n\nBest regards,\nCommon Notary Apostille Team`,
            text: `Hi ${firstName}, payment received for Case ${c.id}! Your ${c.documentType} is now being processed.${c.dueDate ? ` Est. completion: ${formatDate(c.dueDate)}.` : ''}`
        },
        'In Process': {
            subject: `Processing Update - Case ${c.id}`,
            email: `Dear ${firstName},\n\nYour ${c.documentType} is currently being processed for ${c.region} authentication.\n\nCase Reference: ${c.id}\n${c.dueDate ? `Expected Completion: ${formatDate(c.dueDate)}` : ''}\n\nBest regards,\nCommon Notary Apostille Team`,
            text: `Hi ${firstName}, Case ${c.id}: Your ${c.documentType} is in process for ${c.region}.${c.dueDate ? ` Expected by ${formatDate(c.dueDate)}.` : ''}`
        },
        'Shipped/Walk-in': {
            subject: `Documents Shipped - Case ${c.id}`,
            email: `Dear ${firstName},\n\nGreat news! Your authenticated ${c.documentType} has been shipped!\n\nCase Reference: ${c.id}\n${c.trackingNumber ? `Tracking Number: ${c.trackingNumber}` : ''}\n\nBest regards,\nCommon Notary Apostille Team`,
            text: `Hi ${firstName}, your documents have shipped! Case ${c.id}.${c.trackingNumber ? ` Track: ${c.trackingNumber}` : ''}`
        },
        'Returned': {
            subject: `Documents Returned - Case ${c.id}`,
            email: `Dear ${firstName},\n\nThe documents for Case ${c.id} have been returned to our office. We will contact you shortly with next steps.\n\nBest regards,\nCommon Notary Apostille Team`,
            text: `Hi ${firstName}, Case ${c.id}: Documents returned to us. We'll contact you shortly with details.`
        },
        'Delivered': {
            subject: `Documents Delivered - Case ${c.id}`,
            email: `Dear ${firstName},\n\nYour authenticated ${c.documentType} has been delivered!\n\nCase Reference: ${c.id}\n\nThank you for choosing Common Notary Apostille!\n\nBest regards,\nCommon Notary Apostille Team`,
            text: `Hi ${firstName}, your ${c.documentType} has been delivered (Case ${c.id})! Thank you for choosing Common Notary Apostille!`
        },
        'Closed': {
            subject: `Case Completed - ${c.id}`,
            email: `Dear ${firstName},\n\nYour case ${c.id} has been completed and closed.\n\nThank you for trusting Common Notary Apostille!\n\nBest regards,\nCommon Notary Apostille Team`,
            text: `Hi ${firstName}, Case ${c.id} is now closed. Thank you for choosing Common Notary Apostille!`
        }
    };

    return messages[c.status] || messages['Received'];
}

// Show toast notification
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toastMessage');

    toastMessage.textContent = message;
    toast.className = 'toast show ' + type;

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Quick status update from pipeline
function quickStatusUpdate(caseId, newStatus) {
    let cases = getCases();
    const index = cases.findIndex(c => c.id === caseId);

    if (index !== -1) {
        cases[index].status = newStatus;
        cases[index].updatedAt = new Date().toISOString();
        saveCases(cases);
        loadCases();
        showToast(`Status updated to "${newStatus}"`, 'success');
    }
}

// Export cases to JSON (for backup)
function exportCases() {
    const cases = getCases();
    const dataStr = JSON.stringify(cases, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);

    const link = document.createElement('a');
    link.href = url;
    link.download = `common-apostille-cases-${new Date().toISOString().split('T')[0]}.json`;
    link.click();

    URL.revokeObjectURL(url);
    showToast('Cases exported successfully!', 'success');
}

// Import cases from JSON
function importCases(file) {
    const reader = new FileReader();

    reader.onload = function(e) {
        try {
            const importedCases = JSON.parse(e.target.result);

            if (!Array.isArray(importedCases)) {
                throw new Error('Invalid format');
            }

            const existingCases = getCases();
            const mergedCases = [...existingCases];

            importedCases.forEach(imported => {
                const existingIndex = mergedCases.findIndex(c => c.id === imported.id);
                if (existingIndex === -1) {
                    mergedCases.push(imported);
                }
            });

            saveCases(mergedCases);
            loadCases();
            populateRegionFilter();
            showToast(`Imported ${importedCases.length} cases!`, 'success');
        } catch (error) {
            showToast('Error importing cases. Please check the file format.', 'error');
        }
    };

    reader.readAsText(file);
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Escape to close modals
    if (e.key === 'Escape') {
        closeModal();
        closeViewModal();
        closeUpdateModal();
    }

    // Ctrl/Cmd + N for new case
    if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault();
        openModal('add');
    }
});

// Close modals when clicking outside
document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', function(e) {
        if (e.target === this) {
            this.classList.remove('show');
        }
    });
});
