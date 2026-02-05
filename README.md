# Common Apostille Code Review Bot

A comprehensive, self-improving code review and website audit bot for Common Notary Apostille. This bot ensures code quality is at 100%, identifies issues before they become problems, and continuously improves itself based on feedback.

## Features

### Code Analysis & Review
- **Error Detection**: Catch syntax errors, bugs, and potential runtime issues
- **Security Scanning**: Identify vulnerabilities (SQL injection, XSS, hardcoded credentials)
- **Code Quality**: Measure complexity, maintainability, and technical debt
- **Style Checking**: Enforce consistent code style across the project
- **Auto-fixing**: Automatically fix common issues with one command

### Website Auditing
- **Performance Analysis**: Core Web Vitals, load times, resource optimization
- **SEO Analysis**: Meta tags, heading structure, content quality, structured data
- **Accessibility (WCAG 2.1)**: Full accessibility compliance checking
- **Security Headers**: Verify HTTPS, CSP, HSTS, and other security measures

### Self-Improvement
- **Learning from Feedback**: Bot improves based on your feedback
- **Pattern Recognition**: Learns new code patterns over time
- **Accuracy Tracking**: Automatically adjusts based on false positives
- **Continuous Training**: Regular training cycles to improve detection

### Automated CI/CD Integration
- **GitHub Actions**: Automatic code review on every PR
- **Quality Gates**: Block merges that don't meet standards
- **Weekly Website Audits**: Scheduled monitoring of your website

## Installation

```bash
# Clone the repository
git clone https://github.com/Commonnotary/Common-Apostille.git
cd Common-Apostille

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install the package
pip install -e .
```

## Quick Start

### Analyze Your Code

```bash
# Run full code analysis
apostille-bot code analyze .

# Get detailed metrics
apostille-bot code metrics .

# Ensure 100% quality
apostille-bot code ensure-quality .
```

### Audit Your Website

```bash
# Full website audit
apostille-bot website audit https://commonapostille.com

# SEO analysis
apostille-bot website seo https://commonapostille.com

# Accessibility check
apostille-bot website accessibility https://commonapostille.com

# Performance analysis
apostille-bot website performance https://commonapostille.com
```

### Auto-Fix Issues

```bash
# Preview fixes
apostille-bot code fix .

# Auto-apply fixes
apostille-bot code fix . --auto
```

### Generate Recommendations

```bash
# Get improvement recommendations
apostille-bot recommend generate .

# Include website analysis
apostille-bot recommend generate . --website https://commonapostille.com
```

### Full Analysis

```bash
# Run everything at once
apostille-bot full-analysis . --website https://commonapostille.com
```

## Self-Improvement

The bot learns and improves over time. Help it get better!

### Provide Feedback

```bash
# Positive feedback for accurate detection
apostille-bot learn feedback --type issue --id SEC001 --feedback positive

# Report false positive
apostille-bot learn feedback --type issue --id CODE001 --feedback negative --inaccurate

# Suggest improvement
apostille-bot learn feedback --type recommendation --id PERF001 --feedback suggestion \
  --comment "Should also check for lazy loading"
```

### View Learning Status

```bash
apostille-bot learn status .
```

### Train the Bot

```bash
apostille-bot train .
```

## CLI Commands Reference

### Code Commands

| Command | Description |
|---------|-------------|
| `code analyze [PATH]` | Analyze code for errors and issues |
| `code review [PATH]` | Perform comprehensive code review |
| `code ensure-quality [PATH]` | Check if code meets 100% quality |
| `code metrics [PATH]` | Calculate code metrics |
| `code fix [PATH]` | Auto-fix code issues |

### Website Commands

| Command | Description |
|---------|-------------|
| `website audit URL` | Full website audit |
| `website seo URL` | SEO analysis |
| `website accessibility URL` | WCAG 2.1 compliance check |
| `website performance URL` | Performance analysis |

### Learning Commands

| Command | Description |
|---------|-------------|
| `learn status` | Show learning metrics |
| `learn feedback` | Provide feedback |
| `learn train` | Run training cycle |
| `learn export` | Export learning data |

### Other Commands

| Command | Description |
|---------|-------------|
| `full-analysis` | Run complete analysis |
| `watch` | Watch for changes and auto-review |
| `recommend generate` | Generate recommendations |

## GitHub Actions Integration

### Automatic Code Review

Every pull request triggers automatic code review:

1. Code analysis with quality scoring
2. Security vulnerability scanning
3. Recommendations posted as PR comments
4. Quality gates to prevent merging poor code

### Weekly Website Audits

Scheduled weekly audits create GitHub issues with:

- Performance scores
- SEO recommendations
- Accessibility issues
- Security concerns

### Manual Triggers

You can manually trigger audits from the GitHub Actions tab.

## Configuration

### Bot Configuration

Create `config.yaml` in your project root:

```yaml
# Code analysis settings
analysis:
  ignore_patterns:
    - __pycache__
    - node_modules
    - .git
    - venv
  severity_threshold: low
  max_line_length: 100
  enable_security_scan: true

# Quality standards
standards:
  min_score_for_approval: 85
  max_critical_issues: 0
  max_high_issues: 2
  require_tests: true

# Website audit settings
website:
  max_pages: 50
  timeout: 30
  check_accessibility: true
  check_seo: true

# Self-improvement settings
learning:
  min_confidence_threshold: 0.6
  auto_adjust_severity: true
  learn_new_patterns: true
```

## Quality Scores

The bot uses a 0-100 scoring system:

| Score | Grade | Status |
|-------|-------|--------|
| 90-100 | A | Excellent |
| 80-89 | B | Good |
| 70-79 | C | Acceptable |
| 60-69 | D | Needs Work |
| 0-59 | F | Poor |

### Issue Severity

- **Critical**: Must fix immediately (security vulnerabilities, crashes)
- **High**: Should fix soon (bugs, major issues)
- **Medium**: Should address (code smells, minor issues)
- **Low**: Nice to fix (style, minor improvements)
- **Info**: Informational only

## Architecture

```
bot/
├── core/                 # Code analysis modules
│   ├── analyzer.py       # Main code analyzer
│   ├── reviewer.py       # Code review system
│   ├── metrics.py        # Code metrics calculation
│   └── fixer.py          # Auto-fix functionality
├── web/                  # Website analysis modules
│   ├── auditor.py        # Website auditor
│   ├── seo.py            # SEO analyzer
│   ├── accessibility.py  # WCAG checker
│   └── performance.py    # Performance analyzer
├── engine/               # Intelligence modules
│   ├── recommendations.py # Recommendation engine
│   └── self_improve.py   # Self-improvement system
└── cli.py                # Command-line interface
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run the bot on your changes: `apostille-bot code ensure-quality .`
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

For issues and feature requests, please use the [GitHub Issues](https://github.com/Commonnotary/Common-Apostille/issues) page.

---

**Common Notary Apostille** - Quality code, quality service.
