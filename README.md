# Competitor Price Scraper

A web application for scraping and comparing prices from various plastic/plexi suppliers across Europe. The application supports custom configurations for different domains and handles various types of input methods and price calculations.

## Features

- Price calculation based on dimensions (thickness, length, width)
- Support for multiple countries with different VAT rates and currencies
- Configurable scraping steps for each domain
- Interactive configuration management interface
- Comprehensive API documentation
- Captcha handling support (manual and 2Captcha service)
- Settings management for API keys and other configurations
- Database integration with SQLAlchemy
- Alembic migrations for database versioning

## Installation

### Prerequisites

#### For macOS users:
1. Install Xcode Command Line Tools:
   ```bash
   xcode-select --install
   ```
   - Click "Install" when the popup appears
   - Wait for the installation to complete (this might take a while)
   - After installation, verify it worked:
     ```bash
     xcode-select -p
     ```
   - This should output something like: `/Library/Developer/CommandLineTools`

2. PostgreSQL Setup:
   - The initialization script will handle everything automatically, including:
     - Installing Homebrew (macOS package manager) if needed
     - Installing PostgreSQL using Homebrew
     - Starting the PostgreSQL service
     - Creating and configuring the database

#### For Windows users:
1. Install PostgreSQL:
   - Download the installer from [PostgreSQL website](https://www.postgresql.org/download/windows/)
   - Run the installer and follow the setup wizard
   - Remember the password you set for the postgres user
   - Add PostgreSQL to your PATH if the installer didn't do it

### Setup Steps

1. Install Python 3.11.9:
   - Download Python 3.11.9 from [python.org](https://www.python.org/downloads/release/python-3119/)
     - For macOS: Download and run "macOS 64-bit universal2 installer"
     - For Windows: Download and run "Windows installer (64-bit)"
   - During installation, make sure to check "Add Python to PATH"
   - Verify installation by opening a terminal and running:
     ```bash
     # On macOS:
     python3 --version  # Should show Python 3.11.9

     # On Windows:
     python --version  # Should show Python 3.11.9
     ```
     If you get a "command not found" error on macOS, try using `python3` instead of `python`.

   Note: This application requires Python 3.11.9 specifically. Other versions may cause compatibility issues.

2. Clone the repository:
```bash
git clone https://github.com/yourusername/competitor-price-watcher.git
cd competitor-price-watcher
```

3. Create and activate a virtual environment:
```bash
# On macOS:
python3.11 -m venv venv
source venv/bin/activate

# On Windows:
python -m venv venv
venv\Scripts\activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```
If you get build errors on macOS, make sure you've installed the Xcode Command Line Tools as described in the prerequisites.



5. Install Playwright browsers:
```bash
playwright install
```

6. Initialize the database:
```bash
# On macOS:
chmod +x scripts/init_db.sh
./scripts/init_db.sh

# On Windows:
scripts\init_db.bat
```
The script will automatically:
- Install Homebrew (macOS only, if needed)
- Install PostgreSQL (macOS only, if needed)
- Start the PostgreSQL service
- Create and configure the database
- Run all database migrations
- Verify everything is working

## Usage

To start the application:

```bash
uvicorn api:app --reload --port 8080
```

The application will be available at:
- Web Interface: http://localhost:8080
- API Documentation: http://localhost:8080/docs
- Settings page: http://localhost:8080/settings

## API Usage

The application provides a REST API for price calculations. Example request:

```bash
curl -X POST http://localhost:8080/api/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/product",
    "dikte": 3.0,
    "lengte": 1000.0,
    "breedte": 500.0,
    "country": "nl"
  }'
```

For detailed API documentation and configuration options, visit the documentation page in the application.

## Configuration

The application uses several types of configurations:

1. Domain Configurations (`config/domains/*.json`):
   - Define scraping steps for each website
   - Support various input types (select, input, click)
   - Handle custom dropdowns and dynamic content
   - Configure captcha handling

2. Country Configurations (`config/countries.json`):
   - Define VAT rates per country
   - Set currency and formatting preferences
   - Configure regional settings

3. Application Settings:
   - Manage API keys (e.g., 2Captcha)
   - Configure application-wide settings
   - Stored in the database

## Database Migrations

The application uses Alembic for database migrations. To create a new migration:

```bash
alembic revision --autogenerate -m "description of changes"
```

To apply migrations:

```bash
alembic upgrade head
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
