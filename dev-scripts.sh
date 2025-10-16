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

    # Wait for frontend to be ready
    sleep 3
    
    # Check if frontend is running
    if curl -s "http://127.0.0.1:$FRONTEND_PORT" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Frontend server started (PID: $FRONTEND_PID)${NC}"
        echo $FRONTEND_PID > .frontend.pid
    else
        echo -e "${YELLOW}⏳ Frontend starting... (PID: $FRONTEND_PID)${NC}"
        echo $FRONTEND_PID > .frontend.pid
    fi
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

    # Test skills
    if curl -s "$BASE_URL/api/skills" | grep -q "\["; then
        echo -e "${GREEN}✅ /api/skills${NC}"
    else
        echo -e "${RED}❌ /api/skills${NC}"
    fi
}

test_skills() {
    echo -e "${YELLOW}Testing CD Skills CRUD operations...${NC}"

    BASE_URL="http://127.0.0.1:$MOCK_PORT"

    # Test 1: List skills
    echo -e "${BLUE}📋 Testing skills list...${NC}"
    SKILLS_RESPONSE=$(curl -s "$BASE_URL/api/skills")
    if echo "$SKILLS_RESPONSE" | grep -q "Thunder Hit"; then
        echo -e "${GREEN}✅ Skills list working - found sample skills${NC}"
        SKILL_COUNT=$(echo "$SKILLS_RESPONSE" | jq length 2>/dev/null || echo "unknown")
        echo -e "   Found $SKILL_COUNT skills"
    else
        echo -e "${RED}❌ Skills list failed${NC}"
        return 1
    fi

    # Test 2: Create new skill
    echo -e "${BLUE}➕ Testing skill creation...${NC}"
    NEW_SKILL_DATA='{"name":"Test Skill","keystroke":"t","cooldown":5.0,"afterKeyConstraints":false,"isSelected":true}'
    CREATE_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d "$NEW_SKILL_DATA" "$BASE_URL/api/skills/save")

    if echo "$CREATE_RESPONSE" | grep -q "Test Skill"; then
        echo -e "${GREEN}✅ Skill creation successful${NC}"
        SKILL_ID=$(echo "$CREATE_RESPONSE" | jq -r '.id' 2>/dev/null)
        echo -e "   Created skill with ID: $SKILL_ID"
    else
        echo -e "${RED}❌ Skill creation failed${NC}"
        echo "Response: $CREATE_RESPONSE"
        return 1
    fi

    # Test 3: Update skill
    echo -e "${BLUE}✏️  Testing skill update...${NC}"
    UPDATE_DATA='{"name":"Updated Test Skill","cooldown":7.5}'
    UPDATE_RESPONSE=$(curl -s -X PUT -H "Content-Type: application/json" -d "$UPDATE_DATA" "$BASE_URL/api/skills/$SKILL_ID")

    if echo "$UPDATE_RESPONSE" | grep -q "Updated Test Skill"; then
        echo -e "${GREEN}✅ Skill update successful${NC}"
    else
        echo -e "${RED}❌ Skill update failed${NC}"
        echo "Response: $UPDATE_RESPONSE"
        return 1
    fi

    # Test 4: Get selected skills
    echo -e "${BLUE}🎯 Testing selected skills...${NC}"
    SELECTED_RESPONSE=$(curl -s "$BASE_URL/api/skills/selected")

    if echo "$SELECTED_RESPONSE" | grep -q "\["; then
        echo -e "${GREEN}✅ Selected skills endpoint working${NC}"
        SELECTED_COUNT=$(echo "$SELECTED_RESPONSE" | jq length 2>/dev/null || echo "unknown")
        echo -e "   Found $SELECTED_COUNT selected skills"
    else
        echo -e "${RED}❌ Selected skills failed${NC}"
        return 1
    fi

    # Test 5: Delete skill
    echo -e "${BLUE}🗑️  Testing skill deletion...${NC}"
    DELETE_RESPONSE=$(curl -s -X DELETE "$BASE_URL/api/skills/$SKILL_ID")

    if echo "$DELETE_RESPONSE" | grep -q "success"; then
        echo -e "${GREEN}✅ Skill deletion successful${NC}"
    else
        echo -e "${RED}❌ Skill deletion failed${NC}"
        echo "Response: $DELETE_RESPONSE"
        return 1
    fi

    # Test 6: Test play with skills
    echo -e "${BLUE}🎮 Testing play with skills integration...${NC}"
    SELECTED_SKILLS=$(curl -s "$BASE_URL/api/skills/selected")
    PLAY_DATA=$(jq -n --argjson skills "$SELECTED_SKILLS" '{
        "names": ["test_macro.json"],
        "speed": 1.0,
        "loop": 1,
        "active_skills": $skills
    }')

    PLAY_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d "$PLAY_DATA" "$BASE_URL/api/play")

    if echo "$PLAY_RESPONSE" | grep -q "ok"; then
        echo -e "${GREEN}✅ Play with skills integration working${NC}"
        echo -e "   Check server console for skill logging"
    else
        echo -e "${RED}❌ Play with skills failed${NC}"
        echo "Response: $PLAY_RESPONSE"
        return 1
    fi

    echo -e "${GREEN}🎉 All CD Skills tests passed!${NC}"
}

test_drag() {
    echo -e "${YELLOW}Testing Drag-and-Drop Skill Reordering...${NC}"
    echo

    BASE_URL="http://127.0.0.1:$MOCK_PORT"

    # Check if jq is available
    if ! command -v jq &> /dev/null; then
        echo -e "${RED}❌ jq is required for this test. Please install jq.${NC}"
        return 1
    fi

    echo -e "${BLUE}📋 Step 1: List current skills${NC}"
    SKILLS=$(curl -s "$BASE_URL/api/skills")

    echo "$SKILLS" | jq -r '.[] | "   [\(.order)] \(.name) (group: \(.group_id // "none"), delay: \(.delay_after)s)"'
    echo

    # Extract skill IDs and names
    SKILL_1_ID=$(echo "$SKILLS" | jq -r '.[0].id')
    SKILL_1_NAME=$(echo "$SKILLS" | jq -r '.[0].name')
    SKILL_2_ID=$(echo "$SKILLS" | jq -r '.[1].id')
    SKILL_2_NAME=$(echo "$SKILLS" | jq -r '.[1].name')
    SKILL_3_ID=$(echo "$SKILLS" | jq -r '.[2].id')
    SKILL_3_NAME=$(echo "$SKILLS" | jq -r '.[2].name')

    # Test 1: Reorder skills (swap first and third)
    echo -e "${BLUE}🔄 Step 2: Reordering skills (swap first and third)${NC}"
    REORDER_DATA=$(echo "$SKILLS" | jq --arg id1 "$SKILL_1_ID" --arg id3 "$SKILL_3_ID" '
        map(if .id == $id1 then .order = 2 elif .id == $id3 then .order = 0 else . end)
    ')

    REORDER_RESPONSE=$(curl -s -X PUT -H "Content-Type: application/json" -d "$REORDER_DATA" "$BASE_URL/api/skills/reorder")

    if echo "$REORDER_RESPONSE" | jq -e '.[0].name' > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Reorder successful${NC}"
        echo "$REORDER_RESPONSE" | jq -r '.[] | "   [\(.order)] \(.name)"'
    else
        echo -e "${RED}❌ Reorder failed${NC}"
        echo "Response: $REORDER_RESPONSE"
        return 1
    fi
    echo

    # Test 2: Create a group
    echo -e "${BLUE}👥 Step 3: Creating a group (grouping first two skills)${NC}"
    GROUP_ID="group-test-$(date +%s)"
    GROUP_DATA=$(echo "$REORDER_RESPONSE" | jq --arg gid "$GROUP_ID" '
        map(if .order == 0 then
            .group_id = $gid | .delay_after = 12
        elif .order == 1 then
            .group_id = $gid | .delay_after = 0
        else . end)
    ')

    GROUP_RESPONSE=$(curl -s -X PUT -H "Content-Type: application/json" -d "$GROUP_DATA" "$BASE_URL/api/skills/reorder")

    if echo "$GROUP_RESPONSE" | jq -e '.[] | select(.group_id != null)' > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Group created successfully${NC}"
        echo "$GROUP_RESPONSE" | jq -r '.[] | "   [\(.order)] \(.name) - group: \(.group_id // "none"), delay: \(.delay_after)s"'
    else
        echo -e "${RED}❌ Group creation failed${NC}"
        echo "Response: $GROUP_RESPONSE"
        return 1
    fi
    echo

    # Test 3: Update delay in group
    echo -e "${BLUE}⏱️  Step 4: Updating delay between grouped skills${NC}"
    DELAY_DATA=$(echo "$GROUP_RESPONSE" | jq '
        map(if .order == 0 then .delay_after = 5 else . end)
    ')

    DELAY_RESPONSE=$(curl -s -X PUT -H "Content-Type: application/json" -d "$DELAY_DATA" "$BASE_URL/api/skills/reorder")

    if echo "$DELAY_RESPONSE" | jq -e '.[0].delay_after == 5' > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Delay updated successfully${NC}"
        echo "$DELAY_RESPONSE" | jq -r '.[] | select(.group_id != null) | "   [\(.order)] \(.name) → wait \(.delay_after)s → next skill"'
    else
        echo -e "${RED}❌ Delay update failed${NC}"
        return 1
    fi
    echo

    # Test 4: Break group (remove group_id)
    echo -e "${BLUE}💔 Step 5: Breaking the group${NC}"
    UNGROUP_DATA=$(echo "$DELAY_RESPONSE" | jq '
        map(.group_id = null | .delay_after = 0)
    ')

    UNGROUP_RESPONSE=$(curl -s -X PUT -H "Content-Type: application/json" -d "$UNGROUP_DATA" "$BASE_URL/api/skills/reorder")

    if ! echo "$UNGROUP_RESPONSE" | jq -e '.[] | select(.group_id != null)' > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Group broken successfully${NC}"
        echo "$UNGROUP_RESPONSE" | jq -r '.[] | "   [\(.order)] \(.name) - ungrouped"'
    else
        echo -e "${RED}❌ Ungroup failed${NC}"
        return 1
    fi
    echo

    # Test 5: Restore original order
    echo -e "${BLUE}↩️  Step 6: Restoring original order${NC}"
    RESTORE_DATA=$(echo "$UNGROUP_RESPONSE" | jq --arg id1 "$SKILL_1_ID" --arg id2 "$SKILL_2_ID" --arg id3 "$SKILL_3_ID" '
        map(if .id == $id1 then .order = 0 elif .id == $id2 then .order = 1 elif .id == $id3 then .order = 2 else . end)
    ')

    RESTORE_RESPONSE=$(curl -s -X PUT -H "Content-Type: application/json" -d "$RESTORE_DATA" "$BASE_URL/api/skills/reorder")

    echo -e "${GREEN}✅ Order restored${NC}"
    echo "$RESTORE_RESPONSE" | jq -r '.[] | "   [\(.order)] \(.name)"'
    echo

    echo -e "${GREEN}🎉 All drag-and-drop tests passed!${NC}"
    echo
    echo -e "${BLUE}💡 Next steps:${NC}"
    echo -e "   1. Open http://127.0.0.1:$FRONTEND_PORT in your browser"
    echo -e "   2. Go to the 'Skills' tab"
    echo -e "   3. Long-press the menu icon (≡) on any skill"
    echo -e "   4. Drag to reorder or drop on another skill to group"
    echo -e "   5. Click the delay number to edit wait time between skills"
}

show_help() {
    echo "Usage: $0 [command]"
    echo
    echo "Commands:"
    echo "  start       - Start both mock backend and frontend dev server"
    echo "  stop        - Stop all development services"
    echo "  backend     - Start only the mock backend"
    echo "  frontend    - Start only the frontend dev server"
    echo "  build       - Build frontend for production"
    echo "  test        - Test basic mock API endpoints"
    echo "  test-skills - Test CD Skills CRUD operations and integration"
    echo "  test-drag   - Test drag-and-drop skill reordering (interactive)"
    echo "  status      - Show status of development services"
    echo "  help        - Show this help message"
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
    "test-skills")
        test_skills
        ;;
    "test-drag")
        test_drag
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