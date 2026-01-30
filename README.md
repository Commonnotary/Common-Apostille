# Common-Apostille

Common Notary Apostille web app & internal tools for intake, quoting, document uploads, case tracking, and client updates.

## CRM Dashboard

A lightweight case management system for tracking notary and apostille document processing.

### Features

- **Case Management (CRUD)**: Create, read, update, and delete cases with full client and document details
- **Status Pipeline**: Visual pipeline showing case counts across 8 stages:
  - Received
  - Reviewed
  - Payment Collected
  - In Process
  - Shipped/Walk-in
  - Returned
  - Delivered
  - Closed

- **Case Details**:
  - Client name, email, and phone
  - Document type (Birth Certificate, Marriage Certificate, Diploma, etc.)
  - Destination region (Hague/Non-Hague countries)
  - Due date with overdue highlighting
  - Price tracking
  - Outgoing and return tracking numbers
  - Notes field

- **Send Client Update**: Generate professional email or text message templates based on current case status. Messages are customized with case details and can be:
  - Copied to clipboard
  - Opened directly in email client
  - Opened in SMS app (mobile)

- **Search & Filter**: Find cases by client name, document type, tracking number, or notes. Filter by status or region.

- **Data Persistence**: All data stored locally in browser localStorage

### Usage

1. Open `index.html` in a web browser
2. Click "New Case" to add a case
3. Use the pipeline to filter by status
4. Click "Update" on any case to generate client communication

### Keyboard Shortcuts

- `Ctrl/Cmd + N`: New case
- `Escape`: Close modals

### File Structure

```
Common-Apostille/
├── index.html          # Main dashboard page
├── css/
│   └── styles.css      # Dashboard styling
├── js/
│   └── app.js          # Application logic and CRUD operations
└── README.md
```

### Browser Support

Works in all modern browsers (Chrome, Firefox, Safari, Edge).
