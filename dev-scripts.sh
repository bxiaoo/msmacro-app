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

    echo -e "${GREEN}✅ All system dependencies found${NC}"
}

setup_python_venv() {
    echo -e "${YELLOW}Setting up Python virtual environment...${NC}"

    # Check if venv exists
    if [ ! -d ".venv" ]; then
        echo -e "${YELLOW}Creating virtual environment...${NC}"
        python3 -m venv .venv
    fi

    # Activate venv
    source .venv/bin/activate

    # Check and install Python dependencies
    echo -e "${YELLOW}Checking Python dependencies...${NC}"

    # Required packages for mock backend
    REQUIRED_PACKAGES=("aiohttp" "numpy" "Pillow")
    MISSING_PACKAGES=()

    for pkg in "${REQUIRED_PACKAGES[@]}"; do
        pkg_lower=$(echo "$pkg" | tr '[:upper:]' '[:lower:]')
        if ! python3 -c "import $pkg_lower" 2>/dev/null; then
            MISSING_PACKAGES+=("$pkg")
        fi
    done

    if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
        echo -e "${YELLOW}Installing missing packages: ${MISSING_PACKAGES[*]}${NC}"
        pip install "${MISSING_PACKAGES[@]}"
    fi

    echo -e "${GREEN}✅ Python environment ready${NC}"
}

start_mock_backend() {
    echo -e "${YELLOW}Starting mock backend on port $MOCK_PORT...${NC}"

    # Make sure venv is activated
    if [ -z "$VIRTUAL_ENV" ]; then
        source .venv/bin/activate
    fi

    # Kill any existing backend on the port
    lsof -ti:$MOCK_PORT | xargs kill -9 2>/dev/null || true

    # Start mock backend in background with logging
    python3 mock_backend.py --port $MOCK_PORT > mock_backend.log 2>&1 &
    MOCK_PID=$!

    # Wait for server to start
    echo -e "${BLUE}Waiting for backend to start...${NC}"
    for i in {1..10}; do
        if curl -s "http://127.0.0.1:$MOCK_PORT/api/ping" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Mock backend started (PID: $MOCK_PID)${NC}"
            echo $MOCK_PID > .mock_backend.pid
            return 0
        fi
        sleep 1
    done

    # Check if process is still running
    if ! kill -0 $MOCK_PID 2>/dev/null; then
        echo -e "${RED}❌ Backend process died. Check mock_backend.log for errors:${NC}"
        tail -20 mock_backend.log
        exit 1
    fi

    echo -e "${RED}❌ Backend started but not responding on port $MOCK_PORT${NC}"
    exit 1
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

test_cv_dataflow() {
    echo -e "${YELLOW}Testing CV System Full Dataflow...${NC}"
    echo

    BASE_URL="http://127.0.0.1:$MOCK_PORT"

    # Check if jq is available
    if ! command -v jq &> /dev/null; then
        echo -e "${RED}❌ jq is required for this test. Please install jq.${NC}"
        return 1
    fi

    echo -e "${BLUE}📋 Step 1: List CV items${NC}"
    CV_ITEMS=$(curl -s "$BASE_URL/api/cv-items")
    ITEM_COUNT=$(echo "$CV_ITEMS" | jq length 2>/dev/null || echo "0")
    echo -e "   Found $ITEM_COUNT CV items"
    echo

    echo -e "${BLUE}🗺️  Step 2: List map configs${NC}"
    MAP_CONFIGS=$(curl -s "$BASE_URL/api/cv/map-configs")
    CONFIG_COUNT=$(echo "$MAP_CONFIGS" | jq '.configs | length' 2>/dev/null || echo "0")
    echo -e "   Found $CONFIG_COUNT map configs"
    if [ "$CONFIG_COUNT" -gt 0 ]; then
        echo "$MAP_CONFIGS" | jq -r '.configs[] | "   - \(.name): origin(\(.tl_x),\(.tl_y)) size(\(.width)x\(.height))"'
    fi
    echo

    echo -e "${BLUE}➕ Step 3: Create a new map config${NC}"
    MAP_NAME="test-map-$(date +%s)"
    MAP_DATA='{"name":"'$MAP_NAME'","tl_x":100,"tl_y":100,"width":200,"height":150}'
    CREATE_MAP=$(curl -s -X POST -H "Content-Type: application/json" -d "$MAP_DATA" "$BASE_URL/api/cv/map-config")

    if echo "$CREATE_MAP" | jq -e '.name' > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Map config created: $MAP_NAME${NC}"
    else
        echo -e "${RED}❌ Map creation failed${NC}"
        return 1
    fi
    echo

    echo -e "${BLUE}🖼️  Step 4: Test CV frame capture${NC}"
    FRAME_URL="$BASE_URL/api/cv/frame-lossless?tl_x=100&tl_y=100&width=200&height=150"
    FRAME_RESPONSE=$(curl -s -w "%{http_code}" -o /dev/null "$FRAME_URL")

    if [ "$FRAME_RESPONSE" = "200" ]; then
        echo -e "${GREEN}✅ Frame capture working${NC}"
    else
        echo -e "${RED}❌ Frame capture failed (HTTP $FRAME_RESPONSE)${NC}"
        return 1
    fi
    echo

    echo -e "${BLUE}📝 Step 5: Create a CV item${NC}"
    CV_ITEM_NAME="test-item-$(date +%s)"
    CV_ITEM_DATA=$(jq -n --arg name "$CV_ITEM_NAME" --arg map "$MAP_NAME" '{
        name: $name,
        map_config_name: $map,
        pathfinding_rotations: {
            near: ["test_macro.json"],
            medium: [],
            far: [],
            very_far: []
        },
        departure_points: [{
            position: {x: 150, y: 150},
            tolerance: 5,
            rotation_paths: ["test_macro.json"]
        }],
        description: "Test CV item",
        tags: ["test"]
    }')

    CREATE_ITEM=$(curl -s -X POST -H "Content-Type: application/json" -d "$CV_ITEM_DATA" "$BASE_URL/api/cv-item")

    if echo "$CREATE_ITEM" | jq -e '.name' > /dev/null 2>&1; then
        echo -e "${GREEN}✅ CV item created: $CV_ITEM_NAME${NC}"
    else
        echo -e "${RED}❌ CV item creation failed${NC}"
        echo "Response: $CREATE_ITEM"
        return 1
    fi
    echo

    echo -e "${BLUE}📊 Step 6: Verify CV item${NC}"
    CV_ITEM=$(curl -s "$BASE_URL/api/cv-item/$CV_ITEM_NAME")

    if echo "$CV_ITEM" | jq -e '.name' > /dev/null 2>&1; then
        echo -e "${GREEN}✅ CV item retrieved successfully${NC}"
        echo "$CV_ITEM" | jq -r '"   Map: \(.map_config_name), Departure points: \(.departure_points | length)"'
    else
        echo -e "${RED}❌ Failed to retrieve CV item${NC}"
        return 1
    fi
    echo

    echo -e "${BLUE}🗑️  Step 7: Cleanup - Delete test data${NC}"

    # Delete CV item
    DELETE_ITEM=$(curl -s -X DELETE "$BASE_URL/api/cv-item/$CV_ITEM_NAME")
    if echo "$DELETE_ITEM" | jq -e '.message' > /dev/null 2>&1; then
        echo -e "${GREEN}✅ CV item deleted${NC}"
    fi

    # Delete map config
    DELETE_MAP=$(curl -s -X DELETE "$BASE_URL/api/cv/map-config/$MAP_NAME")
    if echo "$DELETE_MAP" | jq -e '.message' > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Map config deleted${NC}"
    fi
    echo

    echo -e "${GREEN}🎉 CV System dataflow test passed!${NC}"
}

test_full_dataflow() {
    echo -e "${YELLOW}Testing Full Application Dataflow...${NC}"
    echo

    # Test basic connectivity
    echo -e "${BLUE}🔗 Testing connectivity${NC}"
    test_api
    echo

    # Test skills system
    echo -e "${BLUE}🎯 Testing Skills System${NC}"
    test_skills
    echo

    # Test CV system
    echo -e "${BLUE}🗺️  Testing CV System${NC}"
    test_cv_dataflow
    echo

    echo -e "${GREEN}✅ Full application dataflow test completed!${NC}"
    echo
    echo -e "${BLUE}💡 System Ready For:${NC}"
    echo -e "   ✓ Frontend development (http://127.0.0.1:$FRONTEND_PORT)"
    echo -e "   ✓ Backend API testing (http://127.0.0.1:$MOCK_PORT)"
    echo -e "   ✓ CV item creation and management"
    echo -e "   ✓ Skills CRUD operations"
    echo -e "   ✓ Macro recording and playback"
    echo
    echo -e "${YELLOW}📝 Notes for Pi Deployment:${NC}"
    echo -e "   - Ensure Python 3.10+ is installed"
    echo -e "   - Install system packages: python3-venv python3-pip"
    echo -e "   - Backend will need access to /dev/input/event* and /dev/hidg0"
    echo -e "   - Frontend will be served as static files from msmacro/web/static"
}

check_pi_readiness() {
    echo -e "${YELLOW}Checking Raspberry Pi Deployment Readiness...${NC}"
    echo

    # Check Python version
    PYTHON_VERSION=$(python3 --version | cut -d ' ' -f 2)
    echo -e "${BLUE}Python Version:${NC} $PYTHON_VERSION"

    MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
        echo -e "${GREEN}✅ Python version OK (3.10+ required)${NC}"
    else
        echo -e "${YELLOW}⚠️  Python 3.10+ recommended for Pi deployment${NC}"
    fi
    echo

    # Check required Python packages
    echo -e "${BLUE}Checking Python packages:${NC}"
    PACKAGES=("aiohttp" "evdev" "numpy" "Pillow")
    for pkg in "${PACKAGES[@]}"; do
        pkg_lower=$(echo "$pkg" | tr '[:upper:]' '[:lower:]')
        if python3 -c "import $pkg_lower" 2>/dev/null; then
            VERSION=$(python3 -c "import $pkg_lower; print($pkg_lower.__version__)" 2>/dev/null || echo "unknown")
            echo -e "  ${GREEN}✅${NC} $pkg ($VERSION)"
        else
            echo -e "  ${RED}❌${NC} $pkg (not installed)"
        fi
    done
    echo

    # Check Node/npm for frontend build
    echo -e "${BLUE}Frontend Build Tools:${NC}"
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node --version)
        echo -e "  ${GREEN}✅${NC} Node.js ($NODE_VERSION)"
    else
        echo -e "  ${YELLOW}⚠️${NC}  Node.js (not required on Pi, only for dev)"
    fi

    if command -v npm &> /dev/null; then
        NPM_VERSION=$(npm --version)
        echo -e "  ${GREEN}✅${NC} npm ($NPM_VERSION)"
    else
        echo -e "  ${YELLOW}⚠️${NC}  npm (not required on Pi, only for dev)"
    fi
    echo

    # Check virtual environment
    echo -e "${BLUE}Virtual Environment:${NC}"
    if [ -d ".venv" ]; then
        echo -e "  ${GREEN}✅${NC} .venv exists"
    else
        echo -e "  ${YELLOW}⚠️${NC}  .venv not found (will be created on first run)"
    fi
    echo

    # Check built frontend
    echo -e "${BLUE}Production Frontend:${NC}"
    if [ -d "msmacro/web/static" ] && [ -f "msmacro/web/static/index.html" ]; then
        echo -e "  ${GREEN}✅${NC} Frontend built (msmacro/web/static/)"
    else
        echo -e "  ${YELLOW}⚠️${NC}  Frontend not built (run './dev-scripts.sh build')"
    fi
    echo

    echo -e "${BLUE}📦 Pi Deployment Checklist:${NC}"
    echo -e "  1. Copy project to Pi"
    echo -e "  2. Install system packages: sudo apt install python3-venv python3-pip"
    echo -e "  3. Run: ./dev-scripts.sh setup"
    echo -e "  4. Configure USB HID gadget kernel module"
    echo -e "  5. Set up systemd service for auto-start"
    echo -e "  6. Configure udev rules for /dev/input access"
}

show_help() {
    echo "Usage: $0 [command]"
    echo
    echo "Commands:"
    echo "  ${GREEN}Development:${NC}"
    echo "    setup         - Set up Python venv and install dependencies"
    echo "    start         - Start both mock backend and frontend dev server"
    echo "    stop          - Stop all development services"
    echo "    backend       - Start only the mock backend"
    echo "    frontend      - Start only the frontend dev server"
    echo "    build         - Build frontend for production"
    echo "    status        - Show status of development services"
    echo
    echo "  ${BLUE}Testing:${NC}"
    echo "    test          - Test basic mock API endpoints"
    echo "    test-skills   - Test CD Skills CRUD operations"
    echo "    test-drag     - Test drag-and-drop skill reordering"
    echo "    test-cv       - Test CV system dataflow (map configs, items, frame capture)"
    echo "    test-all      - Run all dataflow tests (skills + CV)"
    echo
    echo "  ${YELLOW}Pi Deployment:${NC}"
    echo "    check-pi      - Check readiness for Raspberry Pi deployment"
    echo "    help          - Show this help message"
    echo
    echo "Environment Variables:"
    echo "  MOCK_PORT       - Mock backend port (default: 8787)"
    echo "  FRONTEND_PORT   - Frontend dev server port (default: 3000)"
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
    "setup")
        print_header
        check_dependencies
        setup_python_venv
        echo
        echo -e "${GREEN}✅ Setup complete!${NC}"
        echo -e "   Run './dev-scripts.sh start' to begin development"
        ;;
    "start")
        print_header
        check_dependencies
        setup_python_venv
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
        setup_python_venv
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
    "test-cv")
        test_cv_dataflow
        ;;
    "test-all")
        test_full_dataflow
        ;;
    "check-pi")
        check_pi_readiness
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