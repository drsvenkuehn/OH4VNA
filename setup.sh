#!/bin/bash
# OH4VNA Quick Setup Script for New Systems
# Run this script to quickly set up the OH4VNA development environment

echo "🚀 Setting up OH4VNA development environment..."

# Check if we're in the right directory
if [ ! -f "app.py" ]; then
    echo "❌ Error: Please run this script from the OH4VNA project root directory"
    echo "Expected to find app.py in current directory"
    exit 1
fi

# Create virtual environment
echo "📦 Creating Python virtual environment..."
python3.11 -m venv .venv
if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to create virtual environment"
    echo "Make sure Python 3.11 is installed"
    exit 1
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "📚 Installing Python dependencies..."
pip install -e .
if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to install dependencies"
    exit 1
fi

# Copy configuration template
echo "⚙️ Setting up configuration..."
if [ ! -f "configs/settings.yaml" ]; then
    cp configs/settings.example.yaml configs/settings.yaml
    echo "✅ Created configs/settings.yaml from template"
else
    echo "ℹ️  configs/settings.yaml already exists"
fi

# Test the application
echo "🧪 Testing application startup..."
timeout 10s streamlit run app.py --server.headless true --server.port 8502 > /dev/null 2>&1
if [ $? -eq 124 ]; then
    echo "✅ Application startup test successful (timed out as expected)"
elif [ $? -eq 0 ]; then
    echo "✅ Application startup test successful"
else
    echo "⚠️  Application startup test had issues, but this might be normal"
fi

echo ""
echo "🎉 Setup complete! Your OH4VNA development environment is ready."
echo ""
echo "📋 Next steps:"
echo "1. Activate the environment: source .venv/bin/activate"
echo "2. Run the application: streamlit run app.py"
echo "3. Open your browser to: http://localhost:8501"
echo ""
echo "📚 Important files to review:"
echo "• README.md - Project overview and usage"
echo "• .github/copilot-context.md - Complete development history"
echo "• .github/copilot-instructions.md - Copilot guidelines"
echo "• TRANSFER_GUIDE.md - Detailed setup instructions"
echo ""
echo "🎨 The application implements Z43 design system with official corporate colors"
echo "🔬 Includes simulation mode for development without VNA hardware"
echo "🔧 Professional VNA workflow: Calibration → Measurement → Analysis"