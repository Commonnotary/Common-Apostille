# Personal Outreach Agent

A CLI tool for managing attorney outreach campaigns for Common Notary Apostille. This system helps generate qualified attorney relationships through personalized, respectful outreach.

## Overview

The Personal Outreach Agent helps you:
- **Find Leads**: Import attorney leads from various sources (manual entry, CSV, JSON)
- **Segment & Classify**: Automatically categorize leads by practice area and region
- **Personalize**: Extract relevant snippets from firm websites for personalized outreach
- **Generate Emails**: Create three email variants (intro + 2 follow-ups) per lead
- **Plan Outreach**: Manage daily queues with priority ordering
- **Track Progress**: Monitor pipeline status and activity history

## Target Market

- **Practice Areas**: Estate Planning, Probate, Elder Law, Family Law
- **Regions**: Washington DC, Northern Virginia (Alexandria, Arlington, Fairfax), Southwest Virginia (Roanoke, Christiansburg, Blacksburg)

## Core Services Promoted

1. **Mobile Notarization**: Estate documents (POA, trusts, wills) - including offsite visits to homes, hospitals, care facilities
2. **Apostille Facilitation**: Northern VA, Southwest VA, and Federal documents
3. **Loan Signing**: Available on request (not primary focus)

## Installation

### Prerequisites

- Python 3.10 or higher
- pip

### Setup

1. Clone the repository:
```bash
cd personal-outreach-agent
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install the package in development mode:
```bash
pip install -e .
```

5. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your settings
```

## Quick Start

### Run the Demo

The fastest way to see the system in action:

```bash
outreach-agent demo
```

This will:
- Initialize the database
- Load 10 sample attorney leads
- Segment and classify them
- Generate personalized outreach emails
- Display the daily outreach plan

### Basic Commands

```bash
# Initialize the database
outreach-agent init

# List all leads
outreach-agent leads list

# Show a specific lead
outreach-agent leads show 1

# Add a lead manually
outreach-agent leads add \
    --firm "Smith Estate Law" \
    --attorney "John Smith" \
    --email "jsmith@smithlaw.com" \
    --phone "(202) 555-0100" \
    --city "Washington" \
    --state "DC" \
    --practice-areas "Estate Planning, Trusts"

# Import leads from file
outreach-agent leads import leads.json
outreach-agent leads import leads.csv

# Generate outreach emails
outreach-agent outreach generate

# Preview an email
outreach-agent outreach preview 1 --variant intro

# View today's outreach plan
outreach-agent outreach plan

# Approve a message (human-in-the-loop)
outreach-agent outreach approve 1

# Mark message as sent
outreach-agent outreach mark-sent 1

# View statistics
outreach-agent outreach stats

# Export data
outreach-agent export leads.json --format json
```

## Folder Structure

```
personal-outreach-agent/
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── setup.py              # Package installation
├── .env.example          # Environment variable template
├── .env                  # Your configuration (not in git)
├── src/
│   ├── __init__.py
│   ├── config.py         # Configuration management
│   ├── database.py       # Database connection
│   ├── cli.py            # Command-line interface
│   ├── models/
│   │   ├── lead.py       # Lead data model
│   │   ├── outreach.py   # Outreach message model
│   │   └── activity.py   # Activity log model
│   ├── services/
│   │   ├── lead_finder.py      # Lead discovery
│   │   ├── segmenter.py        # Classification
│   │   ├── personalizer.py     # Personalization extraction
│   │   ├── outreach_writer.py  # Email generation
│   │   └── planner.py          # Queue management
│   └── utils/
│       ├── deduplicator.py     # Lead deduplication
│       ├── rate_limiter.py     # Respectful scraping
│       └── robots_checker.py   # robots.txt compliance
├── tests/
│   ├── test_deduplicator.py
│   ├── test_segmenter.py
│   └── test_planner.py
└── data/
    └── outreach.db       # SQLite database
```

## Configuration

Edit `.env` to customize:

```bash
# Database
DATABASE_URL=sqlite:///data/outreach.db

# Scraping (respectful defaults)
SCRAPE_DELAY_SECONDS=2.0
MAX_REQUESTS_PER_MINUTE=20

# Outreach limits
DAILY_OUTREACH_LIMIT=15
FOLLOWUP_1_DAYS=4   # Days after intro for follow-up 1
FOLLOWUP_2_DAYS=9   # Days after intro for follow-up 2

# Your business info (used in emails)
BUSINESS_NAME=Common Notary Apostille
BUSINESS_PHONE=(202) 555-0100
BUSINESS_EMAIL=hello@commonnotaryapostille.com
BUSINESS_WEBSITE=https://commonnotaryapostille.com
CONTACT_NAME=Your Name
```

## Data Import Formats

### JSON Format

```json
[
  {
    "firm_name": "Smith Estate Law",
    "attorney_name": "John Smith",
    "email": "jsmith@smithlaw.com",
    "phone": "(202) 555-0100",
    "practice_areas": ["Estate Planning", "Trusts"],
    "city": "Washington",
    "state": "DC",
    "website": "https://smithestatelaw.com",
    "source_name": "DC Bar Directory",
    "notes": "Specializes in high-net-worth clients"
  }
]
```

### CSV Format

```csv
firm_name,attorney_name,email,phone,practice_areas,city,state,website
Smith Estate Law,John Smith,jsmith@smithlaw.com,(202) 555-0100,"Estate Planning, Trusts",Washington,DC,https://smithestatelaw.com
```

## Email Templates

The system generates three email variants per lead:

### 1. Intro Email
- Personalized opening based on website content
- Brief service mention relevant to practice area
- Soft call-to-action ("Worth a 10-minute call?")

### 2. Follow-up #1 (Day 4-5)
- References initial email
- Highlights mobile/flexible service
- Short and respectful

### 3. Follow-up #2 (Day 9-10)
- Polite close-the-loop
- Offers to check back later
- Very brief

## Human-in-the-Loop

**Important**: This system does NOT auto-send emails. All messages require human approval:

1. Generate emails with `outreach generate`
2. Preview with `outreach preview <id>`
3. Approve with `outreach approve <id>`
4. Manually send the email
5. Record as sent with `outreach mark-sent <id>`

## Compliance Features

- **Rate Limiting**: Configurable delays between requests (default: 2 seconds)
- **robots.txt**: Respects website crawling policies
- **No Login Scraping**: Never scrapes gated/authenticated content
- **Deduplication**: Intelligent matching to avoid duplicate outreach
- **Low Volume**: Default 15 leads/day to avoid spam-like patterns

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_deduplicator.py -v
```

## Development

### Adding New Lead Sources

1. Add source-specific parser to `services/lead_finder.py`
2. Implement data extraction
3. Return `ScrapedLead` objects
4. The system handles deduplication and segmentation

### Customizing Email Templates

Edit `services/outreach_writer.py` to modify:
- Subject line variations
- Email body templates
- Call-to-action options

## Troubleshooting

### "No leads found matching criteria"
- Check lead status with `leads list --status new`
- Ensure leads have email addresses
- Generate emails with `outreach generate`

### "Database not found"
- Run `outreach-agent init` to create the database

### "robots.txt disallows"
- The target website doesn't allow scraping
- Use manual data entry instead

## License

Proprietary - Common Notary Apostille

## Support

For issues or questions, contact the development team.
