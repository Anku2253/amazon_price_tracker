#!/bin/bash

# Amazon Price Tracker - Deployment Script
# This script helps set up the application for local development

set -e

echo "🚀 Amazon Price Tracker - Setup Script"
echo "======================================"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "🔧 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "🔧 Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "🔧 Installing dependencies..."
pip install -r requirements.txt

# Create instance directory
if [ ! -d "instance" ]; then
    echo "🔧 Creating instance directory..."
    mkdir -p instance
    echo "✅ Instance directory created"
fi

# Copy environment file if it doesn't exist
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "🔧 Creating .env file from example..."
        cp .env.example .env
        echo "⚠️  Please edit .env file with your configuration"
    fi
fi

# Initialize database
echo "🔧 Initializing database..."
python3 -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('✅ Database initialized successfully')
"

echo ""
echo "🎉 Setup completed successfully!"
echo ""
echo "To start the application:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Run the app: python app.py"
echo "  3. Open browser to: http://localhost:5000"
echo ""
echo "To start the scheduler (in another terminal):"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Run scheduler: python scheduler.py"
echo ""
echo "For deployment to Render/Heroku, push to your Git repository."
echo ""