// Common Notary Apostille - Quote Calculator & Intake Form

document.addEventListener('DOMContentLoaded', function() {
    // Pricing Configuration
    const PRICING = {
        // Apostille Services
        apostille: {
            nj: 447,
            dmv: 397,
            tn: 347,
            swva: 297,
            federal: 497
        },
        // Notarization Services
        poa: {
            base: 115,
            max: 150,
            perDoc: 25
        },
        trust: {
            base: 125,
            max: 175,
            perDoc: 35
        },
        loan: {
            base: 80,
            perDoc: 15
        },
        hospital: {
            base: 100,
            perDoc: 25
        },
        // Remote Proceedings
        remote: {
            base: 649, // Up to 4 hours included
            overagePerHour: 150,
            overagePerHalfHour: 75
        },
        // Digital Recording Add-ons
        recording: {
            audio: 149,
            audio_video: 199,
            timestamp: 49, // Free with audio_video
            same_day_delivery: 75,
            '24hr_delivery': 45,
            archive_monthly: 25,
            archive_yearly: 99
        },
        // Complexity/Exhibit Upsells
        complexity: {
            heavy_exhibits: 99,
            multi_party: 75,
            interpreter: 75,
            second_tech: 199
        },
        // Remote Booking Urgency
        remoteUrgency: {
            rush_booking: 125,
            same_day_booking: 199,
            after_hours: 150,
            weekend_holiday: 199
        },
        // Certified Reporter
        certified_reporter: {
            coordination: 125
        },
        // Recording Only (standalone)
        recording_only: {
            base: 0 // Just the add-ons
        },
        // Standard urgency (notary/apostille)
        urgency: {
            standard: 0,
            expedited: 75,
            rush: 150
        },
        // Delivery methods
        delivery: {
            pickup: 0,
            standard_mail: 15,
            express: 35,
            international: 75
        },
        // Location fees
        location: {
            office: 0,
            mobile: 25,
            hospital: 25
        },
        additionalDocDiscount: 0.15
    };

    // DOM Elements
    const form = document.getElementById('intakeForm');
    const steps = document.querySelectorAll('.form-step');
    const progressSteps = document.querySelectorAll('.progress-step');
    const confirmationScreen = document.getElementById('confirmationScreen');
    const progressIndicator = document.getElementById('progressIndicator');

    // Form field elements
    const serviceTypeSelect = document.getElementById('serviceType');
    const regionGroup = document.getElementById('regionGroup');
    const regionSelect = document.getElementById('region');
    const locationTypeGroup = document.getElementById('locationTypeGroup');
    const locationTypeSelect = document.getElementById('locationType');
    const numDocumentsInput = document.getElementById('numDocuments');
    const numDocumentsGroup = document.getElementById('numDocumentsGroup');

    // Remote session elements
    const sessionHoursGroup = document.getElementById('sessionHoursGroup');
    const sessionHoursSelect = document.getElementById('sessionHours');
    const recordingAddonsGroup = document.getElementById('recordingAddonsGroup');
    const recordingDeliveryGroup = document.getElementById('recordingDeliveryGroup');
    const complexityGroup = document.getElementById('complexityGroup');
    const certifiedReporterGroup = document.getElementById('certifiedReporterGroup');

    // Urgency groups
    const standardUrgencyGroup = document.getElementById('standardUrgencyGroup');
    const remoteUrgencyGroup = document.getElementById('remoteUrgencyGroup');
    const deliveryGroup = document.getElementById('deliveryGroup');

    // Upload elements
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileUpload');
    const uploadedFilesContainer = document.getElementById('uploadedFiles');

    // Quote display elements
    const baseServiceLine = document.getElementById('baseServiceLine');
    const documentsLine = document.getElementById('documentsLine');
    const sessionOverageLine = document.getElementById('sessionOverageLine');
    const recordingLine = document.getElementById('recordingLine');
    const complexityLine = document.getElementById('complexityLine');
    const urgencyLine = document.getElementById('urgencyLine');
    const bookingUrgencyLine = document.getElementById('bookingUrgencyLine');
    const deliveryLine = document.getElementById('deliveryLine');
    const locationLine = document.getElementById('locationLine');
    const totalPriceEl = document.getElementById('totalPrice');

    // Uploaded files storage
    let uploadedFiles = [];

    // Current step tracker
    let currentStep = 1;

    // Initialize form
    initializeForm();

    function initializeForm() {
        // Service type change handler
        serviceTypeSelect.addEventListener('change', handleServiceTypeChange);

        // Number of documents change handler
        numDocumentsInput.addEventListener('change', calculateQuote);

        // Session hours change handler
        if (sessionHoursSelect) {
            sessionHoursSelect.addEventListener('change', calculateQuote);
        }

        // Radio button change handlers
        document.querySelectorAll('input[name="urgency"]').forEach(radio => {
            radio.addEventListener('change', calculateQuote);
        });

        document.querySelectorAll('input[name="delivery"]').forEach(radio => {
            radio.addEventListener('change', calculateQuote);
        });

        // Checkbox change handlers for add-ons
        document.querySelectorAll('input[name="addons"]').forEach(checkbox => {
            checkbox.addEventListener('change', handleAddonChange);
        });

        // Remote urgency checkbox handlers
        document.querySelectorAll('input[name="remoteUrgency"]').forEach(checkbox => {
            checkbox.addEventListener('change', calculateQuote);
        });

        // Region change handler
        regionSelect.addEventListener('change', calculateQuote);

        // Location type change handler
        locationTypeSelect.addEventListener('change', calculateQuote);

        // Navigation buttons
        document.querySelectorAll('.btn-next').forEach(btn => {
            btn.addEventListener('click', function() {
                const nextStep = parseInt(this.dataset.next);
                if (validateCurrentStep()) {
                    goToStep(nextStep);
                }
            });
        });

        document.querySelectorAll('.btn-prev').forEach(btn => {
            btn.addEventListener('click', function() {
                const prevStep = parseInt(this.dataset.prev);
                goToStep(prevStep);
            });
        });

        // Form submission
        form.addEventListener('submit', handleFormSubmit);

        // File upload handlers
        setupFileUpload();

        // Copy case ID button
        document.getElementById('copyBtn').addEventListener('click', copyCaseId);

        // Phone number formatting
        document.getElementById('phone').addEventListener('input', formatPhoneNumber);
    }

    function handleAddonChange(e) {
        const checkbox = e.target;
        const value = checkbox.value;

        // Handle mutually exclusive options
        if (value === 'audio' && checkbox.checked) {
            // Uncheck audio_video if audio is selected
            const audioVideo = document.querySelector('input[name="addons"][value="audio_video"]');
            if (audioVideo) audioVideo.checked = false;
        } else if (value === 'audio_video' && checkbox.checked) {
            // Uncheck audio if audio_video is selected
            const audio = document.querySelector('input[name="addons"][value="audio"]');
            if (audio) audio.checked = false;
        }

        // Handle delivery options - only one can be selected
        if ((value === 'same_day_delivery' || value === '24hr_delivery') && checkbox.checked) {
            const otherDelivery = value === 'same_day_delivery' ? '24hr_delivery' : 'same_day_delivery';
            const otherCheckbox = document.querySelector(`input[name="addons"][value="${otherDelivery}"]`);
            if (otherCheckbox) otherCheckbox.checked = false;
        }

        // Handle archive options - only one can be selected
        if ((value === 'archive_monthly' || value === 'archive_yearly') && checkbox.checked) {
            const otherArchive = value === 'archive_monthly' ? 'archive_yearly' : 'archive_monthly';
            const otherCheckbox = document.querySelector(`input[name="addons"][value="${otherArchive}"]`);
            if (otherCheckbox) otherCheckbox.checked = false;
        }

        calculateQuote();
    }

    function handleServiceTypeChange() {
        const serviceType = serviceTypeSelect.value;
        const isRemoteService = ['remote', 'recording_only', 'certified_reporter'].includes(serviceType);

        // Reset all conditional groups
        regionGroup.style.display = 'none';
        regionSelect.required = false;
        locationTypeGroup.style.display = 'none';
        sessionHoursGroup.style.display = 'none';
        recordingAddonsGroup.style.display = 'none';
        recordingDeliveryGroup.style.display = 'none';
        complexityGroup.style.display = 'none';
        certifiedReporterGroup.style.display = 'none';
        numDocumentsGroup.style.display = 'block';

        // Toggle urgency display
        if (standardUrgencyGroup) standardUrgencyGroup.style.display = isRemoteService ? 'none' : 'block';
        if (remoteUrgencyGroup) remoteUrgencyGroup.style.display = isRemoteService ? 'block' : 'none';
        if (deliveryGroup) deliveryGroup.style.display = isRemoteService ? 'none' : 'block';

        // Show/hide based on service type
        switch (serviceType) {
            case 'apostille':
                regionGroup.style.display = 'block';
                regionSelect.required = true;
                break;

            case 'poa':
            case 'trust':
            case 'loan':
                locationTypeGroup.style.display = 'block';
                break;

            case 'hospital':
                // No additional options needed
                break;

            case 'remote':
                sessionHoursGroup.style.display = 'block';
                recordingAddonsGroup.style.display = 'block';
                recordingDeliveryGroup.style.display = 'block';
                complexityGroup.style.display = 'block';
                numDocumentsGroup.style.display = 'none';
                break;

            case 'recording_only':
                recordingAddonsGroup.style.display = 'block';
                recordingDeliveryGroup.style.display = 'block';
                numDocumentsGroup.style.display = 'none';
                break;

            case 'certified_reporter':
                certifiedReporterGroup.style.display = 'block';
                numDocumentsGroup.style.display = 'none';
                break;
        }

        calculateQuote();
    }

    function calculateQuote() {
        const serviceType = serviceTypeSelect.value;
        const region = regionSelect.value;
        const numDocs = parseInt(numDocumentsInput.value) || 1;
        const urgency = document.querySelector('input[name="urgency"]:checked')?.value || 'standard';
        const delivery = document.querySelector('input[name="delivery"]:checked')?.value || 'pickup';
        const locationType = locationTypeSelect.value;
        const sessionHours = parseInt(sessionHoursSelect?.value) || 4;

        let quote = {
            serviceName: '',
            basePrice: 0,
            numDocs: numDocs,
            additionalDocsPrice: 0,
            sessionOveragePrice: 0,
            recordingPrice: 0,
            complexityPrice: 0,
            urgencyPrice: 0,
            bookingUrgencyPrice: 0,
            deliveryPrice: 0,
            locationPrice: 0,
            urgency: urgency,
            delivery: delivery,
            locationType: locationType,
            isRemoteService: false
        };

        // Calculate base price based on service type
        switch (serviceType) {
            case 'apostille':
                if (region && PRICING.apostille[region]) {
                    quote.basePrice = PRICING.apostille[region];
                    if (numDocs > 1) {
                        quote.additionalDocsPrice = (numDocs - 1) * (quote.basePrice * (1 - PRICING.additionalDocDiscount));
                    }
                }
                quote.serviceName = region ? `${getRegionName(region)} Apostille` : 'Apostille';
                quote.urgencyPrice = PRICING.urgency[urgency] || 0;
                quote.deliveryPrice = PRICING.delivery[delivery] || 0;
                break;

            case 'poa':
                quote.basePrice = PRICING.poa.base;
                if (numDocs > 1) {
                    quote.additionalDocsPrice = (numDocs - 1) * PRICING.poa.perDoc;
                }
                quote.locationPrice = PRICING.location[locationType] || 0;
                quote.serviceName = 'Power of Attorney';
                quote.urgencyPrice = PRICING.urgency[urgency] || 0;
                quote.deliveryPrice = PRICING.delivery[delivery] || 0;
                break;

            case 'trust':
                quote.basePrice = PRICING.trust.base;
                if (numDocs > 1) {
                    quote.additionalDocsPrice = (numDocs - 1) * PRICING.trust.perDoc;
                }
                quote.locationPrice = PRICING.location[locationType] || 0;
                quote.serviceName = 'Trust Notarization';
                quote.urgencyPrice = PRICING.urgency[urgency] || 0;
                quote.deliveryPrice = PRICING.delivery[delivery] || 0;
                break;

            case 'loan':
                quote.basePrice = PRICING.loan.base;
                if (numDocs > 1) {
                    quote.additionalDocsPrice = (numDocs - 1) * PRICING.loan.perDoc;
                }
                quote.locationPrice = PRICING.location[locationType] || 0;
                quote.serviceName = 'Loan Signing';
                quote.urgencyPrice = PRICING.urgency[urgency] || 0;
                quote.deliveryPrice = PRICING.delivery[delivery] || 0;
                break;

            case 'hospital':
                quote.basePrice = PRICING.hospital.base;
                if (numDocs > 1) {
                    quote.additionalDocsPrice = (numDocs - 1) * PRICING.hospital.perDoc;
                }
                quote.serviceName = 'Hospital/Nursing Home Notarization';
                quote.urgencyPrice = PRICING.urgency[urgency] || 0;
                quote.deliveryPrice = PRICING.delivery[delivery] || 0;
                break;

            case 'remote':
                quote.basePrice = PRICING.remote.base;
                quote.serviceName = 'Remote Deposition Support';
                quote.isRemoteService = true;

                // Calculate session overage
                if (sessionHours > 4) {
                    quote.sessionOveragePrice = (sessionHours - 4) * PRICING.remote.overagePerHour;
                }

                // Calculate recording add-ons
                quote.recordingPrice = calculateRecordingAddons();

                // Calculate complexity add-ons
                quote.complexityPrice = calculateComplexityAddons();

                // Calculate booking urgency
                quote.bookingUrgencyPrice = calculateRemoteUrgency();
                break;

            case 'recording_only':
                quote.basePrice = 0;
                quote.serviceName = 'Digital Recording (Add-on)';
                quote.isRemoteService = true;
                quote.recordingPrice = calculateRecordingAddons();
                quote.bookingUrgencyPrice = calculateRemoteUrgency();
                break;

            case 'certified_reporter':
                quote.basePrice = PRICING.certified_reporter.coordination;
                quote.serviceName = 'Certified Reporter Coordination';
                quote.isRemoteService = true;
                quote.bookingUrgencyPrice = calculateRemoteUrgency();
                break;
        }

        updateQuoteDisplay(quote);
    }

    function calculateRecordingAddons() {
        let total = 0;
        const selectedAddons = document.querySelectorAll('input[name="addons"]:checked');
        const hasAudioVideo = Array.from(selectedAddons).some(cb => cb.value === 'audio_video');

        selectedAddons.forEach(addon => {
            const value = addon.value;

            // Recording options
            if (value === 'audio') {
                total += PRICING.recording.audio;
            } else if (value === 'audio_video') {
                total += PRICING.recording.audio_video;
            } else if (value === 'timestamp') {
                // Free with audio_video
                if (!hasAudioVideo) {
                    total += PRICING.recording.timestamp;
                }
            } else if (value === 'same_day_delivery') {
                total += PRICING.recording.same_day_delivery;
            } else if (value === '24hr_delivery') {
                total += PRICING.recording['24hr_delivery'];
            } else if (value === 'archive_monthly') {
                total += PRICING.recording.archive_monthly;
            } else if (value === 'archive_yearly') {
                total += PRICING.recording.archive_yearly;
            }
        });

        return total;
    }

    function calculateComplexityAddons() {
        let total = 0;
        const selectedAddons = document.querySelectorAll('input[name="addons"]:checked');

        selectedAddons.forEach(addon => {
            const value = addon.value;
            if (PRICING.complexity[value]) {
                total += PRICING.complexity[value];
            }
        });

        return total;
    }

    function calculateRemoteUrgency() {
        let total = 0;
        const selectedUrgency = document.querySelectorAll('input[name="remoteUrgency"]:checked');

        selectedUrgency.forEach(urgency => {
            const value = urgency.value;
            if (PRICING.remoteUrgency[value]) {
                total += PRICING.remoteUrgency[value];
            }
        });

        return total;
    }

    function getRegionName(region) {
        const regionNames = {
            nj: 'New Jersey',
            dmv: 'DMV Area',
            tn: 'Tennessee',
            swva: 'Roanoke/SWVA',
            federal: 'Federal'
        };
        return regionNames[region] || region;
    }

    function updateQuoteDisplay(quote) {
        // Base service line
        baseServiceLine.querySelector('.quote-label').textContent = quote.serviceName || 'Base Service';
        baseServiceLine.querySelector('.quote-value').textContent = formatCurrency(quote.basePrice);

        // Documents line (hide for remote services)
        if (quote.isRemoteService) {
            documentsLine.style.display = 'none';
        } else {
            documentsLine.style.display = 'flex';
            if (quote.numDocs > 1) {
                documentsLine.querySelector('.quote-label').textContent = `Additional Documents (${quote.numDocs - 1})`;
                documentsLine.querySelector('.quote-value').textContent = formatCurrency(quote.additionalDocsPrice);
            } else {
                documentsLine.querySelector('.quote-label').textContent = 'Documents (1)';
                documentsLine.querySelector('.quote-value').textContent = 'Included';
            }
        }

        // Session overage line
        if (quote.sessionOveragePrice > 0) {
            sessionOverageLine.style.display = 'flex';
            sessionOverageLine.querySelector('.quote-label').textContent = 'Session Overage';
            sessionOverageLine.querySelector('.quote-value').textContent = formatCurrency(quote.sessionOveragePrice);
        } else {
            sessionOverageLine.style.display = 'none';
        }

        // Recording add-ons line
        if (quote.recordingPrice > 0) {
            recordingLine.style.display = 'flex';
            recordingLine.querySelector('.quote-label').textContent = 'Recording Add-ons';
            recordingLine.querySelector('.quote-value').textContent = formatCurrency(quote.recordingPrice);
        } else {
            recordingLine.style.display = 'none';
        }

        // Complexity add-ons line
        if (quote.complexityPrice > 0) {
            complexityLine.style.display = 'flex';
            complexityLine.querySelector('.quote-label').textContent = 'Complexity Add-ons';
            complexityLine.querySelector('.quote-value').textContent = formatCurrency(quote.complexityPrice);
        } else {
            complexityLine.style.display = 'none';
        }

        // Standard urgency line
        if (quote.urgencyPrice > 0) {
            urgencyLine.style.display = 'flex';
            urgencyLine.querySelector('.quote-label').textContent =
                quote.urgency === 'expedited' ? 'Expedited Processing' : 'Rush Processing';
            urgencyLine.querySelector('.quote-value').textContent = formatCurrency(quote.urgencyPrice);
        } else {
            urgencyLine.style.display = 'none';
        }

        // Booking urgency line (for remote services)
        if (quote.bookingUrgencyPrice > 0) {
            bookingUrgencyLine.style.display = 'flex';
            bookingUrgencyLine.querySelector('.quote-label').textContent = 'Booking/Timing Fees';
            bookingUrgencyLine.querySelector('.quote-value').textContent = formatCurrency(quote.bookingUrgencyPrice);
        } else {
            bookingUrgencyLine.style.display = 'none';
        }

        // Delivery line
        if (quote.deliveryPrice > 0) {
            deliveryLine.style.display = 'flex';
            const deliveryNames = {
                standard_mail: 'Standard Mail',
                express: 'Express Shipping',
                international: 'International Shipping'
            };
            deliveryLine.querySelector('.quote-label').textContent = deliveryNames[quote.delivery] || 'Delivery';
            deliveryLine.querySelector('.quote-value').textContent = formatCurrency(quote.deliveryPrice);
        } else {
            deliveryLine.style.display = 'none';
        }

        // Location line
        if (quote.locationPrice > 0) {
            locationLine.style.display = 'flex';
            const locationNames = {
                mobile: 'Mobile Service Fee',
                hospital: 'Hospital/Facility Fee'
            };
            locationLine.querySelector('.quote-label').textContent = locationNames[quote.locationType] || 'Location Fee';
            locationLine.querySelector('.quote-value').textContent = formatCurrency(quote.locationPrice);
        } else {
            locationLine.style.display = 'none';
        }

        // Total
        const total = quote.basePrice + quote.additionalDocsPrice + quote.sessionOveragePrice +
                      quote.recordingPrice + quote.complexityPrice + quote.urgencyPrice +
                      quote.bookingUrgencyPrice + quote.deliveryPrice + quote.locationPrice;
        totalPriceEl.textContent = formatCurrency(total);
    }

    function formatCurrency(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD'
        }).format(amount);
    }

    function goToStep(stepNumber) {
        // Calculate quote before showing step 3
        if (stepNumber === 3) {
            calculateQuote();
        }

        // Update steps
        steps.forEach(step => {
            step.classList.remove('active');
            if (parseInt(step.dataset.step) === stepNumber) {
                step.classList.add('active');
            }
        });

        // Update progress indicator
        progressSteps.forEach(step => {
            const stepNum = parseInt(step.dataset.step);
            step.classList.remove('active', 'completed');
            if (stepNum === stepNumber) {
                step.classList.add('active');
            } else if (stepNum < stepNumber) {
                step.classList.add('completed');
            }
        });

        currentStep = stepNumber;

        // Scroll to form
        document.getElementById('quote').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function validateCurrentStep() {
        const currentStepEl = document.querySelector(`.form-step[data-step="${currentStep}"]`);
        const requiredFields = currentStepEl.querySelectorAll('[required]');
        let isValid = true;

        requiredFields.forEach(field => {
            // Skip hidden fields
            if (field.offsetParent === null) return;

            if (!field.value) {
                isValid = false;
                field.classList.add('error');
                field.addEventListener('input', function() {
                    this.classList.remove('error');
                }, { once: true });
            }
        });

        // Special validation for step 1 - apostille region
        if (currentStep === 1 && serviceTypeSelect.value === 'apostille' && !regionSelect.value) {
            isValid = false;
            regionSelect.classList.add('error');
        }

        if (!isValid) {
            showNotification('Please fill in all required fields', 'error');
        }

        return isValid;
    }

    function setupFileUpload() {
        // Click to upload
        uploadArea.addEventListener('click', () => fileInput.click());

        // Drag and drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            handleFiles(e.dataTransfer.files);
        });

        // File input change
        fileInput.addEventListener('change', (e) => {
            handleFiles(e.target.files);
        });
    }

    function handleFiles(files) {
        const maxSize = 10 * 1024 * 1024; // 10MB
        const allowedTypes = ['application/pdf', 'image/jpeg', 'image/png'];

        Array.from(files).forEach(file => {
            // Validate file type
            if (!allowedTypes.includes(file.type)) {
                showNotification(`${file.name} is not a supported format`, 'error');
                return;
            }

            // Validate file size
            if (file.size > maxSize) {
                showNotification(`${file.name} exceeds 10MB limit`, 'error');
                return;
            }

            // Check for duplicates
            if (uploadedFiles.some(f => f.name === file.name && f.size === file.size)) {
                showNotification(`${file.name} is already uploaded`, 'error');
                return;
            }

            uploadedFiles.push(file);
        });

        renderUploadedFiles();
    }

    function renderUploadedFiles() {
        uploadedFilesContainer.innerHTML = '';

        uploadedFiles.forEach((file, index) => {
            const fileEl = document.createElement('div');
            fileEl.className = 'uploaded-file';
            fileEl.innerHTML = `
                <div class="file-info">
                    <svg class="file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <div>
                        <span class="file-name">${file.name}</span>
                        <span class="file-size">${formatFileSize(file.size)}</span>
                    </div>
                </div>
                <button type="button" class="file-remove" data-index="${index}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
                        <line x1="18" y1="6" x2="6" y2="18"/>
                        <line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                </button>
            `;
            uploadedFilesContainer.appendChild(fileEl);
        });

        // Add remove handlers
        document.querySelectorAll('.file-remove').forEach(btn => {
            btn.addEventListener('click', function() {
                const index = parseInt(this.dataset.index);
                uploadedFiles.splice(index, 1);
                renderUploadedFiles();
            });
        });
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function handleFormSubmit(e) {
        e.preventDefault();

        if (!validateCurrentStep()) {
            return;
        }

        // Generate case ID
        const caseId = generateCaseId();
        document.getElementById('caseNumber').textContent = caseId;

        // Collect form data
        const formData = collectFormData();
        formData.caseId = caseId;
        formData.files = uploadedFiles.map(f => f.name);
        formData.submittedAt = new Date().toISOString();

        // Log form data (in production, this would be sent to a server)
        console.log('Form submitted:', formData);

        // Store in localStorage for demo purposes
        storeSubmission(formData);

        // Show confirmation screen
        form.style.display = 'none';
        progressIndicator.style.display = 'none';
        confirmationScreen.style.display = 'block';

        // Scroll to top of section
        document.getElementById('quote').scrollIntoView({ behavior: 'smooth', block: 'start' });

        showNotification('Request submitted successfully!', 'success');
    }

    function generateCaseId() {
        const prefix = 'CNA';
        const timestamp = Date.now().toString(36).toUpperCase();
        const random = Math.random().toString(36).substring(2, 6).toUpperCase();
        return `${prefix}-${timestamp}${random}`;
    }

    function collectFormData() {
        // Collect selected add-ons
        const selectedAddons = Array.from(document.querySelectorAll('input[name="addons"]:checked'))
            .map(cb => cb.value);

        // Collect remote urgency options
        const remoteUrgencyOptions = Array.from(document.querySelectorAll('input[name="remoteUrgency"]:checked'))
            .map(cb => cb.value);

        return {
            serviceType: serviceTypeSelect.value,
            region: regionSelect.value,
            locationType: locationTypeSelect.value,
            numDocuments: numDocumentsInput.value,
            sessionHours: sessionHoursSelect?.value || null,
            addons: selectedAddons,
            remoteUrgency: remoteUrgencyOptions,
            urgency: document.querySelector('input[name="urgency"]:checked')?.value,
            delivery: document.querySelector('input[name="delivery"]:checked')?.value,
            firstName: document.getElementById('firstName').value,
            lastName: document.getElementById('lastName').value,
            email: document.getElementById('email').value,
            phone: document.getElementById('phone').value,
            preferredContact: document.getElementById('preferredContact').value,
            notes: document.getElementById('notes').value,
            estimatedTotal: totalPriceEl.textContent
        };
    }

    function storeSubmission(data) {
        const submissions = JSON.parse(localStorage.getItem('cna_submissions') || '[]');
        submissions.push(data);
        localStorage.setItem('cna_submissions', JSON.stringify(submissions));
    }

    function copyCaseId() {
        const caseNumber = document.getElementById('caseNumber').textContent;
        navigator.clipboard.writeText(caseNumber).then(() => {
            showNotification('Case ID copied to clipboard!', 'success');
        }).catch(() => {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = caseNumber;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            showNotification('Case ID copied to clipboard!', 'success');
        });
    }

    function formatPhoneNumber(e) {
        let value = e.target.value.replace(/\D/g, '');
        if (value.length > 0) {
            if (value.length <= 3) {
                value = `(${value}`;
            } else if (value.length <= 6) {
                value = `(${value.slice(0, 3)}) ${value.slice(3)}`;
            } else {
                value = `(${value.slice(0, 3)}) ${value.slice(3, 6)}-${value.slice(6, 10)}`;
            }
        }
        e.target.value = value;
    }

    function showNotification(message, type = 'info') {
        // Remove existing notifications
        const existing = document.querySelector('.notification');
        if (existing) {
            existing.remove();
        }

        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <span>${message}</span>
            <button class="notification-close">&times;</button>
        `;

        // Add styles
        notification.style.cssText = `
            position: fixed;
            top: 100px;
            right: 24px;
            padding: 16px 24px;
            background: ${type === 'success' ? '#4CAF50' : type === 'error' ? '#E53935' : '#1A1A1A'};
            color: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            display: flex;
            align-items: center;
            gap: 16px;
            z-index: 10000;
            animation: slideIn 0.3s ease;
        `;

        document.body.appendChild(notification);

        // Close button handler
        notification.querySelector('.notification-close').addEventListener('click', () => {
            notification.remove();
        });

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.animation = 'slideOut 0.3s ease';
                setTimeout(() => notification.remove(), 300);
            }
        }, 5000);
    }

    // Add animation styles
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(100%);
                opacity: 0;
            }
        }
        .notification-close {
            background: none;
            border: none;
            color: white;
            font-size: 20px;
            cursor: pointer;
            opacity: 0.7;
            transition: opacity 0.3s;
        }
        .notification-close:hover {
            opacity: 1;
        }
        input.error, select.error {
            border-color: #E53935 !important;
            box-shadow: 0 0 0 3px rgba(229, 57, 53, 0.2) !important;
        }
    `;
    document.head.appendChild(style);
});
