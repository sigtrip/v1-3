#!/usr/bin/env bash
#
# deploy.sh - One-command ARGOS deployment script
#
# Usage:
#   ./deploy.sh                    # Interactive deployment
#   ./deploy.sh --auto             # Automatic deployment
#   ./deploy.sh --docker           # Docker deployment
#   ./deploy.sh --android          # Build Android APK
#

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_command() {
    if command -v $1 &> /dev/null; then
        print_success "$1 is installed"
        return 0
    else
        print_error "$1 is not installed"
        return 1
    fi
}

# Main deployment
deploy_interactive() {
    print_header "ARGOS Universal OS - Interactive Deployment"
    
    echo ""
    echo "This script will:"
    echo "  1. Check system requirements"
    echo "  2. Install dependencies"
    echo "  3. Generate secrets"
    echo "  4. Initialize database"
    echo "  5. Run health check"
    echo "  6. Start ARGOS"
    echo ""
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Deployment cancelled"
        exit 0
    fi
    
    # Step 1: Check requirements
    print_header "Step 1: Checking Requirements"
    check_command python3 || exit 1
    check_command pip || exit 1
    check_command git || exit 1
    
    # Check Python version
    python_version=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    if (( $(echo "$python_version >= 3.10" | bc -l) )); then
        print_success "Python $python_version"
    else
        print_error "Python $python_version is too old (need >= 3.10)"
        exit 1
    fi
    
    # Step 2: Install dependencies
    print_header "Step 2: Installing Dependencies"
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        print_success "Dependencies installed"
    else
        print_error "requirements.txt not found"
        exit 1
    fi
    
    # Step 3: Generate secrets
    print_header "Step 3: Generating Secrets"
    if [ ! -f ".env" ]; then
        python3 setup_secrets.py --auto
        print_success "Secrets generated"
        print_warning "Please edit .env and add your API keys"
    else
        print_warning ".env already exists, skipping"
    fi
    
    # Step 4: Initialize
    print_header "Step 4: Initializing ARGOS"
    if [ -f "genesis.py" ]; then
        python3 genesis.py
        print_success "Initialization complete"
    else
        print_warning "genesis.py not found, skipping"
    fi
    
    # Step 5: Health check
    print_header "Step 5: Running Health Check"
    if [ -f "check_readiness.py" ]; then
        python3 check_readiness.py --quick
    else
        python3 health_check.py || true
    fi
    
    # Step 6: Ready to start
    print_header "Deployment Complete!"
    echo ""
    print_success "ARGOS is ready to start"
    echo ""
    echo "Start ARGOS with:"
    echo "  python main.py              # Desktop GUI"
    echo "  python main.py --no-gui     # Headless"
    echo "  python main.py --dashboard  # With web dashboard"
    echo ""
    read -p "Start ARGOS now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python3 main.py
    fi
}

deploy_auto() {
    print_header "ARGOS Universal OS - Automatic Deployment"
    
    # Silent installation
    pip install -q -r requirements.txt
    python3 setup_secrets.py --auto
    python3 genesis.py
    
    print_success "Automatic deployment complete"
    print_warning "Don't forget to configure .env with your API keys"
}

deploy_docker() {
    print_header "ARGOS Universal OS - Docker Deployment"
    
    check_command docker || exit 1
    
    # Build image
    print_success "Building Docker image..."
    docker build -t argos:latest .
    
    # Check .env
    if [ ! -f ".env" ]; then
        print_warning ".env not found, creating from template"
        python3 setup_secrets.py --auto
    fi
    
    # Run container
    print_success "Starting container..."
    docker run -d \
        --name argos \
        --env-file .env \
        -p 8080:8080 \
        -p 55771:55771 \
        -v $(pwd)/logs:/app/logs \
        -v $(pwd)/config:/app/config \
        argos:latest
    
    print_success "ARGOS running in Docker"
    echo ""
    echo "View logs: docker logs -f argos"
    echo "Stop: docker stop argos"
    echo "Remove: docker rm argos"
}

deploy_android() {
    print_header "ARGOS Universal OS - Android Build"
    
    check_command buildozer || {
        print_error "Buildozer not installed"
        echo "Install with: pip install buildozer"
        exit 1
    }
    
    print_success "Building Android APK..."
    buildozer android debug
    
    print_success "APK built successfully"
    ls -lh bin/*.apk
}

# Parse arguments
case "${1:-}" in
    --auto)
        deploy_auto
        ;;
    --docker)
        deploy_docker
        ;;
    --android)
        deploy_android
        ;;
    --help|-h)
        echo "ARGOS Deployment Script"
        echo ""
        echo "Usage:"
        echo "  ./deploy.sh           Interactive deployment"
        echo "  ./deploy.sh --auto    Automatic deployment"
        echo "  ./deploy.sh --docker  Docker deployment"
        echo "  ./deploy.sh --android Build Android APK"
        echo "  ./deploy.sh --help    Show this help"
        ;;
    *)
        deploy_interactive
        ;;
esac
