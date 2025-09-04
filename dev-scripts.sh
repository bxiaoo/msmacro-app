#!/bin/bash
# dev-scripts.sh - Helper scripts for development

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default ports
MOCK_PORT=8787
FRONTEND_PORT=3000

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  MSMacro Development Helper${NC}"
    echo -e "${BLUE}================================${NC}"
    echo
}

check_dependencies() {
    echo -e "${YELLOW}Checking dependencies...${NC}"

    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 not found${NC}"
        exit 1
    fi

    # Check Node
    if ! command -v node &> /dev/null; then
        echo -e "${RED}❌ Node.js not found${NC}"
        exit 1
    fi

    # Check npm
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}❌ npm not found${NC}"
        exit 1
    fi

    echo -e "${GREEN}✅ All dependencies found${NC}"
}

start_mock_backend() {
    echo -e "${YELLOW}Starting mock backend on port $MOCK_PORT...${NC}"

    if ! python3 -c "import aiohttp" 2>/dev/null; then
        echo -e "${YELLOW}📦 Installing aiohttp...${NC}"
        pip3 install aiohttp
    fi

    # Start mock backend in background
    python3 mock_backend.py --port $MOCK_PORT &
    MOCK_PID=$!

    # Wait a moment for server to start
    sleep 2

    # Check if server is running
    if curl -s "http://127.0.0.1:$MOCK_PORT/api/ping" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Mock backend started (PID: $MOCK_PID)${NC}"
        echo $MOCK_PID > .mock_backend.pid
    else
        echo -e "${RED}❌ Failed to start mock backend${NC}"
        exit 1
    fi
}

start_frontend() {
    echo -e "${YELLOW}Starting frontend development server...${NC}"

    cd webui

    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}📦 Installing frontend dependencies...${NC}"
        npm install
    fi

    # Start frontend dev server
    npm run dev &
    FRONTEND_PID=$!
    cd ..

    echo -e "${GREEN}✅ Frontend server started (PID: $FRONTEND_PID)${NC}"
    echo $FRONTEND_PID > .frontend.pid
}

stop_services() {
    echo -e "${YELLOW}Stopping services...${NC}"

    # Stop mock backend
    if [ -f ".mock_backend.pid" ]; then
        MOCK_PID=$(cat .mock_backend.pid)
        if kill -0 $MOCK_PID 2>/dev/null; then
            kill $MOCK_PID
            echo -e "${GREEN}✅ Mock backend stopped${NC}"
        fi
        rm -f .mock_backend.pid
    fi

    # Stop frontend
    if [ -f ".frontend.pid" ]; then
        FRONTEND_PID=$(cat .frontend.pid)
        if kill -0 $FRONTEND_PID 2>/dev/null; then
            kill $FRONTEND_PID
            echo -e "${GREEN}✅ Frontend server stopped${NC}"
        fi
        rm -f .frontend.pid
    fi

    # Kill any remaining processes on our ports
    lsof -ti:$MOCK_PORT | xargs kill -9 2>/dev/null || true
    lsof -ti:$FRONTEND_PORT | xargs kill -9 2>/dev/null || true
}

build_frontend() {
    echo -e "${YELLOW}Building frontend for production...${NC}"

    cd webui
    npm run build
    cd ..

    echo -e "${GREEN}✅ Frontend built to msmacro/web/static${NC}"
}

test_api() {
    echo -e "${YELLOW}Testing mock API endpoints...${NC}"

    BASE_URL="http://127.0.0.1:$MOCK_PORT"

    # Test ping
    if curl -s "$BASE_URL/api/ping" | grep -q "ok"; then
        echo -e "${GREEN}✅ /api/ping${NC}"
    else
        echo -e "${RED}❌ /api/ping${NC}"
    fi

    # Test status
    if curl -s "$BASE_URL/api/status" | grep -q "mode"; then
        echo -e "${GREEN}✅ /api/status${NC}"
    else
        echo -e "${RED}❌ /api/status${NC}"
    fi

    # Test files
    if curl -s "$BASE_URL/api/files" | grep -q "files"; then
        echo -e "${GREEN}✅ /api/files${NC}"
    else
        echo -e "${RED}❌ /api/files${NC}"
    fi
}

show_help() {
    echo "Usage: $0 [command]"
    echo
    echo "Commands:"
    echo "  start     - Start both mock backend and frontend dev server"
    echo "  stop      - Stop all development services"
    echo "  backend   - Start only the mock backend"
    echo "  frontend  - Start only the frontend dev server"
    echo "  build     - Build frontend for production"
    echo "  test      - Test mock API endpoints"
    echo "  status    - Show status of development services"
    echo "  help      - Show this help message"
}

show_status() {
    echo -e "${YELLOW}Service Status:${NC}"

    # Check mock backend
    if curl -s "http://127.0.0.1:$MOCK_PORT/api/ping" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Mock Backend: Running on port $MOCK_PORT${NC}"
    else
        echo -e "${RED}❌ Mock Backend: Not running${NC}"
    fi

    # Check frontend
    if curl -s "http://127.0.0.1:$FRONTEND_PORT" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Frontend: Running on port $FRONTEND_PORT${NC}"
    else
        echo -e "${RED}❌ Frontend: Not running${NC}"
    fi

    echo
    echo -e "${BLUE}URLs:${NC}"
    echo -e "  Frontend: http://127.0.0.1:$FRONTEND_PORT"
    echo -e "  Mock API: http://127.0.0.1:$MOCK_PORT/api/"
    echo -e "  SSE Events: http://127.0.0.1:$MOCK_PORT/api/events"
}

# Cleanup on exit
trap 'stop_services' EXIT INT TERM

# Main command handling
case "$1" in
    "start")
        print_header
        check_dependencies
        start_mock_backend
        start_frontend
        echo
        show_status
        echo
        echo -e "${GREEN}🚀 Development environment ready!${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
        wait
        ;;
    "stop")
        stop_services
        ;;
    "backend")
        print_header
        check_dependencies
        start_mock_backend
        echo -e "${GREEN}🚀 Mock backend running!${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
        wait
        ;;
    "frontend")
        print_header
        check_dependencies
        start_frontend
        echo -e "${GREEN}🚀 Frontend dev server running!${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
        wait
        ;;
    "build")
        build_frontend
        ;;
    "test")
        test_api
        ;;
    "status")
        show_status
        ;;
    "help"|"--help"|"-h"|"")
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo
        show_help
        exit 1
        ;;
esac