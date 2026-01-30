# CLAUDE.md - AI Assistant Development Guide

This document provides guidance for AI assistants working on the Common-Apostille codebase.

## Project Overview

**Project:** Common-Apostille
**Purpose:** A web application and internal tools platform for Common Notary Apostille services.

### Core Features
- **Intake Management** - Client onboarding and information collection
- **Quoting System** - Price quotes for apostille services
- **Document Uploads** - Secure document handling and storage
- **Case Tracking** - Status tracking for apostille requests
- **Client Updates** - Communication and notification system

## Repository Status

This repository is in its **initial setup phase**. Currently contains:
- `README.md` - Project description
- `CLAUDE.md` - This file (AI assistant guide)

## Project Structure

### Current Structure
```
Common-Apostille/
├── README.md           # Project overview
└── CLAUDE.md           # AI assistant development guide
```

### Expected Structure (Future Development)
```
Common-Apostille/
├── src/
│   ├── frontend/       # Client-facing web application
│   ├── backend/        # API server and business logic
│   └── shared/         # Shared types, utilities, constants
├── internal-tools/     # Admin and staff tools
├── tests/              # Test suites
├── docs/               # Documentation
├── config/             # Configuration files
├── scripts/            # Build and deployment scripts
├── .github/            # GitHub Actions and templates
├── README.md           # Project overview
├── CLAUDE.md           # AI assistant guide
├── package.json        # Dependencies (if Node.js)
└── .gitignore          # Git ignore rules
```

## Technology Stack

**Note:** Technology choices are to be determined. Recommendations based on project requirements:

### Suggested Stack
- **Frontend:** React/Next.js or Vue.js for web application
- **Backend:** Node.js/Express or Python/FastAPI for API
- **Database:** PostgreSQL for relational data, S3-compatible storage for documents
- **Authentication:** OAuth 2.0 / JWT for secure access
- **File Storage:** Secure cloud storage with encryption for document uploads

## Development Guidelines

### Git Workflow

1. **Branch Naming Convention:**
   - Feature branches: `feature/<description>`
   - Bug fixes: `fix/<description>`
   - Documentation: `docs/<description>`
   - AI assistant work: `claude/<description>-<session-id>`

2. **Commit Messages:**
   - Use clear, descriptive commit messages
   - Format: `<type>: <description>`
   - Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

3. **Pull Requests:**
   - Provide clear description of changes
   - Reference any related issues
   - Ensure all tests pass before merging

### Code Conventions

1. **General Principles:**
   - Write clean, readable, and maintainable code
   - Follow DRY (Don't Repeat Yourself) principles
   - Add meaningful comments for complex logic
   - Use descriptive variable and function names

2. **Security Best Practices:**
   - Never commit sensitive data (API keys, credentials, etc.)
   - Validate all user inputs
   - Use parameterized queries to prevent SQL injection
   - Implement proper authentication and authorization
   - Encrypt sensitive data at rest and in transit

3. **Document Handling:**
   - All uploaded documents must be handled securely
   - Implement virus scanning for uploads
   - Use secure, signed URLs for document access
   - Maintain audit logs for document operations

### Testing Requirements

- Unit tests for business logic
- Integration tests for API endpoints
- E2E tests for critical user flows
- Security testing for document handling

## Key Domain Concepts

### Apostille Services
- **Apostille:** A certification for authenticating documents for international use
- **Authentication:** Verifying document signatures and seals
- **Notarization:** Witnessing and certifying document signing

### User Roles
- **Clients:** End users submitting documents for apostille
- **Staff:** Internal users processing requests
- **Admin:** System administrators with full access

### Document States
- `submitted` - Document uploaded by client
- `in_review` - Being reviewed by staff
- `processing` - Apostille process in progress
- `completed` - Apostille completed, ready for pickup/delivery
- `returned` - Returned to client

## AI Assistant Instructions

### When Working on This Codebase

1. **Before Making Changes:**
   - Read and understand existing code
   - Check for existing patterns and conventions
   - Review related tests

2. **Making Changes:**
   - Follow established code conventions
   - Write tests for new functionality
   - Update documentation as needed
   - Keep changes focused and minimal

3. **Security Considerations:**
   - This application handles sensitive legal documents
   - Always validate and sanitize inputs
   - Never expose sensitive data in logs or errors
   - Follow principle of least privilege

4. **Documentation:**
   - Update CLAUDE.md when adding new patterns or conventions
   - Document API endpoints and data models
   - Keep README.md current with setup instructions

### Common Tasks

1. **Adding a New Feature:**
   - Create feature branch
   - Implement with tests
   - Update documentation
   - Submit PR for review

2. **Fixing a Bug:**
   - Reproduce the issue first
   - Write a failing test
   - Fix the bug
   - Verify test passes
   - Check for similar issues elsewhere

3. **Refactoring:**
   - Ensure test coverage exists
   - Make incremental changes
   - Run tests frequently
   - Document significant architectural changes

## Environment Setup

### Prerequisites (Expected)
- Node.js (LTS version) or Python 3.10+
- Database (PostgreSQL recommended)
- Cloud storage credentials (for document storage)

### Local Development (To Be Configured)
```bash
# Clone repository
git clone <repository-url>
cd Common-Apostille

# Install dependencies
npm install  # or pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Start development server
npm run dev  # or python manage.py runserver
```

## Configuration

### Environment Variables (Expected)
```
# Application
NODE_ENV=development
PORT=3000

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/apostille

# Authentication
JWT_SECRET=<secret-key>
SESSION_SECRET=<session-secret>

# File Storage
STORAGE_BUCKET=<bucket-name>
STORAGE_KEY=<access-key>
STORAGE_SECRET=<secret-key>

# Email Service
SMTP_HOST=<smtp-host>
SMTP_USER=<smtp-user>
SMTP_PASS=<smtp-password>
```

## Contact

**Maintainer:** Commonnotary
**Email:** admin@commonapostille.com

---

*Last Updated: January 2026*
*Repository Status: Initial Setup Phase*
