# CLAUDE.md: Price Scraper OPG

## Project Overview
This is a sophisticated web scraping application for competitor price monitoring across European plastic/plexi suppliers. The system uses **Playwright for browser automation**, **FastAPI for the web framework**, and **PostgreSQL for persistence**, with a focus on **configurable, multi-domain scraping workflows**.

## Architecture & Key Components

### Core Services (`app/services/`)
- **`PriceCalculator`**: The heart of the scraping engine. Handles dimension-based price calculations using configurable step sequences stored in the database.
- **`crud.py`**: Database operations for domain/country/package configurations with automatic versioning.
- **Browser Management**: Uses Playwright with anti-detection measures (custom user agents, storage clearing, human-like behavior simulation).

### Configuration System (Database-Driven)
- **Domain Configs**: JSON step sequences for each website (clicks, inputs, selects, price extraction)
- **Country Configs**: VAT rates, currency formatting, locale settings per country
- **Package Configs**: Shipping calculation parameters
- **Version Management**: All config changes are versioned with rollback capabilities

### API Structure (`app/routes/`)
- **Price Calculation**: `/api/calculate-smp` (square meter pricing), `/api/calculate-shipping`
- **Config Management**: CRUD endpoints for domain/country/package configurations
- **Real-time Updates**: Server-Sent Events (SSE) for live scraping status updates

## Development Workflows

### Virtual Environment Setup
**IMPORTANT**: Always activate the virtual environment before running any Python commands or scripts:
```bash
# Activate virtual environment (REQUIRED before any Python commands)
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate     # Windows
```

### Database Operations
```bash
# Activate virtual environment first!
source .venv/bin/activate

# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Initialize database (includes PostgreSQL setup on macOS)
./scripts/init_db.sh  # macOS
scripts\init_db.bat   # Windows
```

### Frontend Build Process
```bash
# Build Tailwind CSS (required after any CSS changes)
npm run build

# Watch mode for development
npm run watch
```

### Running the Application
```bash
# Activate virtual environment first!
source .venv/bin/activate

# Start development server
uvicorn app.main:app --reload --port 8080

# Production deployment uses supervisord.conf
```

## Key Patterns & Conventions

### Configuration Step Types
The scraping engine uses a step-based configuration system. Common step types:
- `click`: DOM element clicking with retry logic
- `input`: Form field filling with dimension substitution (`{thickness}`, `{length}`, `{width}`, etc.)
- `select`: Dropdown selection with intelligent value matching
- `wait`: Timing controls between actions
- `read_price`: Price extraction with change detection
- `navigate`: URL navigation with load state waiting
- `blur`: Form field focus management
- `modify`: DOM manipulation via JavaScript

### Dimension Handling
- All dimensions are stored in **millimeters** internally
- Automatic unit conversion (mm ↔ cm) based on step configuration
- Variables like `{thickness}`, `{length}`, `{width}` are replaced in step values
- Special handling for quantity and multi-product calculations

### Error Handling & Resilience
- Steps support `continue_on_error` and `skip_on_failure` flags
- Automatic retries with exponential backoff for network operations
- Browser recreation on critical failures
- Status tracking with detailed logging for debugging failed scrapes

### Database Schema Evolution
- Uses Alembic for migrations with automatic table creation
- JSON columns for flexible configuration storage
- Automatic versioning system for all configuration changes
- Composite indexes for performance optimization

## Critical Files for Understanding
- `app/services/price_calculator.py`: Core scraping logic (~2100 lines)
- `app/main.py`: FastAPI application setup and route registration
- `app/models/models.py`: SQLAlchemy database models
- `alembic/versions/`: Database migration history
- `static/js/`: Frontend JavaScript for configuration management

## Environment & Dependencies
- **Python 3.13.11** (specific version required)
- **PostgreSQL** for production, SQLite for development
- **Playwright** browsers (install with `playwright install`)
- **Node.js** for Tailwind CSS compilation
- **2Captcha** service integration (optional, configured via settings)

## Common Debugging Approaches
- Use `/api/status` SSE endpoint to monitor real-time scraping progress
- Check `app.log` for detailed execution logs
- Browser runs in non-headless mode during development (`HEADLESS=False`)
- Configuration versions allow rollback to known-working states
- Domain-specific error handling varies by website complexity

## CLAUDE Guidelines
- This is a complex project.
- The user is newly onboarded.
- The file `price_calculator.py` is very complex, and the user doesn't know 90% of how it works or how to test it.
- Be careful while changing any code.
- Take permission from the user before making changes.
- Do only what the user tells you to do.
- Do not write any test files or CLI commands.
- Never write any fallback logic; we want the original implementation to work.
- **ALWAYS activate the virtual environment (`source .venv/bin/activate`) before running any Python commands or scripts.**
