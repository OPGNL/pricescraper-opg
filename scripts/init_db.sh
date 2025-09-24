#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting database initialization...${NC}"

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo -e "${RED}❌ This script is for macOS only. Please use init_db.bat on Windows.${NC}"
    exit 1
fi

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo -e "${BLUE}📦 Installing Homebrew...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for Apple Silicon Macs
    if [[ $(uname -m) == 'arm64' ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    
    # Configure Homebrew
    echo -e "${BLUE}🔄 Configuring Homebrew...${NC}"
    eval "$(homebrew/bin/brew shellenv)"
    brew update --force --quiet
    chmod -R go-w "$(brew --prefix)/share/zsh"
    
    if ! command -v brew &> /dev/null; then
        echo -e "${RED}❌ Failed to install Homebrew. Please install it manually from https://brew.sh${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Homebrew installed and configured successfully!${NC}"
fi

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo -e "${BLUE}📦 Installing PostgreSQL...${NC}"
    brew install postgresql@14
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Failed to install PostgreSQL${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ PostgreSQL installed successfully!${NC}"
fi

# Start PostgreSQL service
echo -e "${BLUE}🔄 Starting PostgreSQL service...${NC}"
brew services start postgresql@14

# Wait for PostgreSQL to start
echo -e "${BLUE}⏳ Waiting for PostgreSQL to start...${NC}"
sleep 5

# Create database if it doesn't exist
if ! psql -lqt | cut -d \| -f 1 | grep -qw competitor_price_watcher; then
    echo -e "${BLUE}🔄 Creating database 'competitor_price_watcher'...${NC}"
    createdb competitor_price_watcher
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Database created successfully!${NC}"
    else
        echo -e "${RED}❌ Failed to create database.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ Database 'competitor_price_watcher' already exists.${NC}"
fi

# Verify connection
echo -e "${BLUE}🔄 Verifying database connection...${NC}"
if psql competitor_price_watcher -c '\q' 2>/dev/null; then
    echo -e "${GREEN}✅ Successfully connected to database!${NC}"
else
    echo -e "${RED}❌ Could not connect to database.${NC}"
    exit 1
fi

# Run database migrations
echo -e "${BLUE}🔄 Running database migrations...${NC}"
alembic upgrade head

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Database initialization completed successfully!${NC}"
else
    echo -e "${RED}❌ Failed to run migrations.${NC}"
    exit 1
fi

echo -e "${GREEN}✨ Setup complete! Your database is ready to use.${NC}" 