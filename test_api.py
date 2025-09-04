#!/usr/bin/env python3
"""
Debug Helper for MSMacro Mock Backend Issues
This script helps debug the specific issues you mentioned:
1. Folder/subfolder display
2. Rename operations
3. Delete operations
4. Play button mode changes
5. Save recording visibility
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, Any

BASE_URL = "http://127.0.0.1:8787"

class DebugHelper:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip('/')
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request and return JSON response."""
        url = f"{self.base_url}{path}"

        print(f"→ {method.upper()} {path}")

        try:
            async with self.session.request(method, url, **kwargs) as resp:
                text = await resp.text()

                try:
                    data = json.loads(text) if text else {}
                except json.JSONDecodeError:
                    data = {"raw_response": text}

                if resp.status >= 400:
                    print(f"  ❌ HTTP {resp.status}: {data}")
                    return {"error": f"HTTP {resp.status}", "data": data}

                print(f"  ✅ HTTP {resp.status}")
                return data

        except Exception as e:
            print(f"  ❌ Request failed: {e}")
            return {"error": str(e)}

    def print_tree_structure(self, tree, indent=0):
        """Print tree structure for debugging."""
        prefix = "  " * indent
        for item in tree:
            if item.get("type") == "dir":
                print(f"{prefix}📁 {item['name']} ({item['rel']})")
                children = item.get("children", [])
                if children:
                    self.print_tree_structure(children, indent + 1)
                else:
                    print(f"{prefix}  (empty)")
            elif item.get("type") == "file":
                print(f"{prefix}📄 {item['name']} ({item['rel']}) - {item.get('size', 0)} bytes")

    def print_files_list(self, files):
        """Print files list for debugging."""
        print("Files list:")
        for f in files:
            print(f"  📄 {f['rel']} - {f['size']} bytes, mtime: {f['mtime']}")

    async def debug_tree_structure(self):
        """Debug Issue 1: Folder/subfolder display problems."""
        print("\n🔍 DEBUGGING: Tree Structure")
        print("=" * 50)

        status = await self.request("GET", "/api/status")
        if "error" in status:
            print("❌ Failed to get status")
            return

        print(f"Mode: {status.get('mode')}")

        tree = status.get("tree", [])
        files = status.get("files", [])

        print(f"\n📂 Tree structure ({len(tree)} root items):")
        self.print_tree_structure(tree)

        print(f"\n📋 Files list ({len(files)} files):")
        self.print_files_list(files)

        # Check if tree matches files
        def collect_files_from_tree(nodes):
            files_in_tree = []
            for node in nodes:
                if node.get("type") == "file":
                    files_in_tree.append(node["rel"])
                elif node.get("type") == "dir":
                    files_in_tree.extend(collect_files_from_tree(node.get("children", [])))
            return files_in_tree

        tree_files = set(collect_files_from_tree(tree))
        list_files = set(f["rel"] for f in files)

        print(f"\n🔄 Consistency Check:")
        print(f"  Files in tree: {len(tree_files)}")
        print(f"  Files in list: {len(list_files)}")

        if tree_files == list_files:
            print("  ✅ Tree and file list are consistent")
        else:
            print("  ❌ Tree and file list inconsistent!")
            missing_in_tree = list_files - tree_files
            missing_in_list = tree_files - list_files
            if missing_in_tree:
                print(f"    Missing in tree: {missing_in_tree}")
            if missing_in_list:
                print(f"    Missing in list: {missing_in_list}")

    async def debug_rename_operations(self):
        """Debug Issue 2: Rename operations not working."""
        print("\n🔍 DEBUGGING: Rename Operations")
        print("=" * 50)

        # Get current files
        status = await self.request("GET", "/api/status")
        files = status.get("files", [])

        if not files:
            print("❌ No files to test rename with")
            return

        # Try to rename first file
        original_file = files[0]
        original_name = original_file["rel"]
        new_name = f"test_renamed_{int(time.time())}"

        print(f"Testing rename: {original_name} → {new_name}")

        # Perform rename
        rename_result = await self.request("POST", "/api/files/rename",
                                         json={"old": original_name, "new": new_name})

        if "error" in rename_result:
            print(f"❌ Rename failed: {rename_result}")
            return

        print("✅ Rename API call succeeded")

        # Check if file was actually renamed
        await asyncio.sleep(0.5)  # Give time for updates
        new_status = await self.request("GET", "/api/status")
        new_files = new_status.get("files", [])

        new_name_with_json = new_name if new_name.endswith(".json") else f"{new_name}.json"
        found_renamed = any(f["rel"] == new_name_with_json for f in new_files)
        found_original = any(f["rel"] == original_name for f in new_files)

        if found_renamed and not found_original:
            print("✅ File successfully renamed in backend")
            # Rename back for further testing
            await self.request("POST", "/api/files/rename",
                             json={"old": new_name_with_json, "new": original_name.replace(".json", "")})
        else:
            print("❌ File not properly renamed in backend")
            print(f"  Found renamed ({new_name_with_json}): {found_renamed}")
            print(f"  Found original ({original_name}): {found_original}")

    async def debug_delete_operations(self):
        """Debug Issue 3: Delete operations not working."""
        print("\n🔍 DEBUGGING: Delete Operations")
        print("=" * 50)

        # First create a test file to delete
        print("Creating test recording for deletion...")
        await self.request("POST", "/api/record/start")
        await asyncio.sleep(0.2)
        await self.request("POST", "/api/record/stop",
                         json={"action": "save", "name": "test_delete_me"})

        await asyncio.sleep(0.5)

        # Get updated files list
        status = await self.request("GET", "/api/status")
        files = status.get("files", [])

        # Find our test file
        test_file = None
        for f in files:
            if "test_delete_me" in f["rel"]:
                test_file = f
                break

        if not test_file:
            print("❌ Test file not found after creation")
            return

        print(f"Test file created: {test_file['rel']}")
        initial_count = len(files)

        # Try to delete it
        print(f"Attempting to delete: {test_file['rel']}")
        delete_result = await self.request("DELETE", f"/api/files/{test_file['rel']}")

        if "error" in delete_result:
            print(f"❌ Delete failed: {delete_result}")
            return

        print("✅ Delete API call succeeded")

        # Check if file was actually deleted
        await asyncio.sleep(0.5)
        new_status = await self.request("GET", "/api/status")
        new_files = new_status.get("files", [])

        final_count = len(new_files)
        still_exists = any(f["rel"] == test_file["rel"] for f in new_files)

        if not still_exists and final_count == initial_count - 1:
            print("✅ File successfully deleted")
        else:
            print("❌ File not properly deleted")
            print(f"  File still exists: {still_exists}")
            print(f"  Count: {initial_count} → {final_count}")

    async def debug_play_mode_changes(self):
        """Debug Issue 4: Play button doesn't change to play mode."""
        print("\n🔍 DEBUGGING: Play Mode Changes")
        print("=" * 50)

        # Get current status and files
        status = await self.request("GET", "/api/status")
        files = status.get("files", [])
        initial_mode = status.get("mode")

        print(f"Initial mode: {initial_mode}")

        if not files:
            print("❌ No files to test playback with")
            return

        # Try to play first file
        test_file = files[0]["rel"]
        print(f"Testing playback of: {test_file}")

        play_result = await self.request("POST", "/api/play",
                                       json={"names": [test_file], "speed": 2.0, "loop": 1})

        if "error" in play_result:
            print(f"❌ Play failed: {play_result}")
            return

        print("✅ Play API call succeeded")

        # Check mode change
        await asyncio.sleep(0.2)  # Small delay for mode change
        play_status = await self.request("GET", "/api/status")
        play_mode = play_status.get("mode")

        print(f"Mode during play: {play_mode}")

        if play_mode == "PLAYING":
            print("✅ Mode correctly changed to PLAYING")

            # Wait a bit and check if it returns to original mode
            print("Waiting for playback to finish...")
            await asyncio.sleep(3)

            final_status = await self.request("GET", "/api/status")
            final_mode = final_status.get("mode")
            print(f"Final mode: {final_mode}")

            if final_mode == initial_mode:
                print("✅ Mode correctly returned to original state")
            else:
                print("❌ Mode didn't return to original state")
        else:
            print("❌ Mode didn't change to PLAYING")

    async def debug_save_recording_visibility(self):
        """Debug Issue 5: Save recording doesn't show in file table."""
        print("\n🔍 DEBUGGING: Save Recording Visibility")
        print("=" * 50)

        # Get initial file count
        initial_status = await self.request("GET", "/api/status")
        initial_files = initial_status.get("files", [])
        initial_tree = initial_status.get("tree", [])
        initial_count = len(initial_files)

        print(f"Initial file count: {initial_count}")

        # Create a new recording
        test_name = f"debug_save_test_{int(time.time())}"
        print(f"Creating recording: {test_name}")

        # Start recording
        start_result = await self.request("POST", "/api/record/start")
        if "error" in start_result:
            print(f"❌ Failed to start recording: {start_result}")
            return

        await asyncio.sleep(0.5)

        # Stop and save recording
        stop_result = await self.request("POST", "/api/record/stop",
                                       json={"action": "save", "name": test_name})

        if "error" in stop_result:
            print(f"❌ Failed to save recording: {stop_result}")
            return

        print("✅ Recording saved via API")

        # Check if file appears
        await asyncio.sleep(1)  # Give time for updates
        final_status = await self.request("GET", "/api/status")
        final_files = final_status.get("files", [])
        final_tree = final_status.get("tree", [])
        final_count = len(final_files)

        print(f"Final file count: {final_count}")

        # Look for our file
        expected_name = test_name if test_name.endswith(".json") else f"{test_name}.json"
        found_in_files = any(f["rel"] == expected_name for f in final_files)

        def find_in_tree(nodes, target):
            for node in nodes:
                if node.get("type") == "file" and node.get("rel") == target:
                    return True
                elif node.get("type") == "dir":
                    if find_in_tree(node.get("children", []), target):
                        return True
            return False

        found_in_tree = find_in_tree(final_tree, expected_name)

        print(f"File found in files list: {found_in_files}")
        print(f"File found in tree: {found_in_tree}")

        if found_in_files and found_in_tree and final_count == initial_count + 1:
            print("✅ Recording properly saved and visible")
        else:
            print("❌ Recording not properly saved or visible")
            if found_in_files:
                print("  ✅ Found in files list")
            else:
                print("  ❌ Not found in files list")
            if found_in_tree:
                print("  ✅ Found in tree")
            else:
                print("  ❌ Not found in tree")

    async def run_all_debugging(self):
        """Run all debugging tests."""
        print("🐛 MSMacro Mock Backend Debugging")
        print("=" * 60)

        # Test backend connectivity first
        ping = await self.request("GET", "/api/ping")
        if "error" in ping:
            print("❌ Cannot connect to mock backend!")
            print("Make sure it's running on", self.base_url)
            return

        print("✅ Connected to mock backend")

        # Run all debug tests
        await self.debug_tree_structure()
        await self.debug_rename_operations()
        await self.debug_delete_operations()
        await self.debug_play_mode_changes()
        await self.debug_save_recording_visibility()

        print("\n" + "=" * 60)
        print("🏁 Debugging complete!")
        print("\nIf any issues persist:")
        print("1. Check browser developer tools network tab")
        print("2. Check mock backend console output")
        print("3. Try refreshing the frontend")

async def main():
    """Main debug runner."""
    print("Starting MSMacro Debug Session...")

    async with DebugHelper(BASE_URL) as debugger:
        await debugger.run_all_debugging()

if __name__ == "__main__":
    asyncio.run(main())