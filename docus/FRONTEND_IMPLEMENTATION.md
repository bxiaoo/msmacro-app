# Frontend Implementation Guide

**Document Version**: 1.0
**Last Updated**: 2025-01-07
**Purpose**: Common patterns and guidelines for msmacro web UI development

---

## Overview

This document provides implementation patterns, component structures, and best practices used in the msmacro web UI. It serves as a reference for maintaining consistency and accelerating future feature development.

**Tech Stack**:
- React (functional components with hooks)
- File extension: `.jsx` (not `.tsx`)
- Styling: TailwindCSS + utility classes
- UI Components: Custom components in `components/ui/`
- Icons: `lucide-react`
- API: `fetch` with custom wrapper in `api.js`

---

## Project Structure

```
webui/
├── src/
│   ├── api.js                  # API client functions
│   ├── App.jsx                 # Main app component with routing
│   ├── components/
│   │   ├── ui/                 # Reusable UI components
│   │   │   ├── button.jsx      # Button with variants
│   │   │   ├── input.jsx       # Text input
│   │   │   ├── checkbox.jsx    # Checkbox component
│   │   │   └── utils.js        # cn() utility for classNames
│   │   ├── CVConfiguration.jsx # CV config page (map configs)
│   │   └── ...                 # Other feature components
│   └── ...
├── package.json
└── vite.config.js
```

---

## API Integration Pattern

### API Client Structure (`api.js`)

**Core Helper Function**:
```javascript
async function API(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });

  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { error: text || "non-json response" };
  }

  if (!res.ok) {
    const msg = (data && (data.error || data.message)) || `HTTP ${res.status}`;
    const err = new Error(msg);
    err.status = res.status;
    err.body = data;
    throw err;
  }
  return data;
}
```

**Usage Pattern**:
```javascript
// GET request
export function getResource() {
  return API("/api/resource");
}

// POST request with body
export function createResource(name, value) {
  return API("/api/resource", {
    method: "POST",
    body: JSON.stringify({ name, value }),
  });
}

// DELETE request with URL param
export function deleteResource(name) {
  return API(`/api/resource/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
}
```

**Error Handling in Components**:
```javascript
try {
  const data = await someAPIFunction()
  // Handle success
} catch (err) {
  // err.message contains user-friendly error
  alert(`Failed: ${err.message}`)
  // or set error state for UI display
}
```

---

## Component Patterns

### State Management Pattern

**Example: CV Configuration Component**

```javascript
export function CVConfiguration() {
  // Group related state
  const [mapConfigs, setMapConfigs] = useState([])
  const [activeConfig, setActiveConfig] = useState(null)
  const [isCreating, setIsCreating] = useState(false)
  const [showSaveDialog, setShowSaveDialog] = useState(false)
  const [configName, setConfigName] = useState('')
  const [coords, setCoords] = useState({ x: 68, y: 56, width: 340, height: 86 })

  // Load data on mount
  useEffect(() => {
    loadMapConfigs()
  }, [])

  // Handler functions
  const loadMapConfigs = async () => {
    try {
      const data = await listMapConfigs()
      setMapConfigs(data.configs || [])
      const active = data.configs?.find(c => c.is_active)
      setActiveConfig(active || null)
    } catch (err) {
      console.error('Failed to load:', err)
    }
  }

  const handleCreateConfig = () => {
    setIsCreating(true)
    setCoords({ x: 68, y: 56, width: 340, height: 86 })
  }

  const handleSaveConfig = async () => {
    if (!configName.trim()) {
      alert('Please enter a name')
      return
    }

    try {
      await createMapConfig(configName, coords.x, coords.y, coords.width, coords.height)
      await loadMapConfigs() // Refresh list
      setIsCreating(false)
      setShowSaveDialog(false)
    } catch (err) {
      alert(`Failed to save: ${err.message}`)
    }
  }

  // Render functions for complex UI sections
  const renderConfigList = () => (
    <div className="space-y-2">
      {mapConfigs.map((config) => (
        <div key={config.name} className="bg-gray-50 rounded-lg p-4">
          {/* Config item UI */}
        </div>
      ))}
    </div>
  )

  return (
    <div className="flex flex-col h-full">
      {/* Component JSX */}
      {renderConfigList()}
    </div>
  )
}
```

**Key Patterns**:
- Group related state variables together
- Use descriptive names (`isCreating`, not `creating`)
- Extract complex sections into `renderX()` functions
- Load data in `useEffect` with empty dependency array
- Always refresh data after mutations (create/update/delete)

---

## UI Component Usage

### Button Component

**Location**: `components/ui/button.jsx`

**Variants**:
- `default` - Dark gray button (primary action)
- `primary` - Blue button (important action like Save)
- `play` - Green button (start/execute actions like Resample)
- `ghost` - Transparent button (secondary actions)

**Sizes**:
- `sm` - Small (h-8)
- `default` - Default (h-16)
- `lg` - Large (h-10)

**Usage**:
```javascript
import { Button } from './ui/button'

<Button onClick={handleSave} variant="primary" size="sm">
  Save
</Button>

<Button onClick={handleDelete} variant="ghost" size="sm" disabled={isActive}>
  <Trash2 size={16} />
</Button>
```

### Input Component

**Location**: `components/ui/input.jsx`

**Usage**:
```javascript
import { Input } from './ui/input'

<Input
  type="text"
  placeholder="Enter name"
  value={name}
  onChange={(e) => setName(e.target.value)}
  className="mb-4"
/>

<Input
  type="number"
  value={coords.x}
  onChange={(e) => setCoords({ ...coords, x: parseInt(e.target.value) || 0 })}
  className="text-center"
/>
```

### Checkbox Component

**Location**: `components/ui/checkbox.jsx`

**Usage**:
```javascript
import { Checkbox } from './ui/checkbox'

<Checkbox
  checked={isActive}
  onChange={() => handleToggle()}
/>
```

**Note**: Checkbox is already a button, no need to wrap it.

---

## Common UI Patterns

### Empty State Pattern

**When to use**: No data exists yet, encourage user action

```javascript
const renderEmptyState = () => (
  <div className="bg-gray-50 rounded-lg p-8 text-center">
    <IconComponent size={48} className="mx-auto mb-3 text-gray-400" />
    <p className="text-sm text-gray-700 mb-2">No items found</p>
    <p className="text-xs text-gray-500 mb-4">
      Get started by creating your first item.
    </p>
    <Button onClick={handleCreate} variant="primary" size="sm">
      <Plus size={16} />
      Create Item
    </Button>
  </div>
)
```

### List/Grid Pattern

**When to use**: Display multiple items with actions

```javascript
const renderList = () => (
  <div className="space-y-4">
    <div className="flex items-center justify-between">
      <h3 className="text-sm font-medium text-gray-700">Items</h3>
      <Button onClick={handleCreate} variant="primary" size="sm">
        <Plus size={16} />
        New
      </Button>
    </div>
    <div className="space-y-2">
      {items.map((item) => (
        <div
          key={item.id}
          className="bg-gray-50 rounded-lg p-4 flex items-center justify-between"
        >
          <div className="flex items-center gap-3">
            <Checkbox
              checked={item.isActive}
              onChange={() => handleToggle(item)}
            />
            <div>
              <div className="text-sm font-medium text-gray-900">{item.name}</div>
              <div className="text-xs text-gray-500">{item.description}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              onClick={() => handleEdit(item)}
              variant="ghost"
              size="sm"
            >
              <Settings size={16} />
            </Button>
            <Button
              onClick={() => handleDelete(item.id)}
              variant="ghost"
              size="sm"
              disabled={item.isActive}
            >
              <Trash2 size={16} />
            </Button>
          </div>
        </div>
      ))}
    </div>
  </div>
)
```

### Form Pattern with Coordinate Controls

**When to use**: Numeric input with increment/decrement buttons

```javascript
const [coords, setCoords] = useState({ x: 0, y: 0 })

const adjustCoord = (axis, delta) => {
  setCoords(prev => ({
    ...prev,
    [axis]: Math.max(0, prev[axis] + delta)
  }))
}

const renderCoordControl = (axis, label) => (
  <div>
    <label className="block text-sm font-medium text-gray-700 mb-2">{label}</label>
    <div className="flex items-center gap-2">
      <Button onClick={() => adjustCoord(axis, -10)} variant="default" size="sm">
        <Minus size={16} />
      </Button>
      <Input
        type="number"
        value={coords[axis]}
        onChange={(e) => setCoords({ ...coords, [axis]: parseInt(e.target.value) || 0 })}
        className="text-center"
      />
      <Button onClick={() => adjustCoord(axis, 10)} variant="default" size="sm">
        <Plus size={16} />
      </Button>
    </div>
  </div>
)
```

### Modal Dialog Pattern

**When to use**: Secondary action requiring user input

```javascript
const [showDialog, setShowDialog] = useState(false)
const [inputValue, setInputValue] = useState('')

const handleSubmit = async () => {
  if (!inputValue.trim()) {
    alert('Please enter a value')
    return
  }

  try {
    await someAPICall(inputValue)
    setShowDialog(false)
    setInputValue('')
    // Refresh data
  } catch (err) {
    alert(`Failed: ${err.message}`)
  }
}

const renderDialog = () => {
  if (!showDialog) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Dialog Title</h2>
        <Input
          type="text"
          placeholder="Enter value"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          className="mb-4"
        />
        <div className="flex gap-2 justify-end">
          <Button onClick={() => setShowDialog(false)} variant="ghost">
            Cancel
          </Button>
          <Button onClick={handleSubmit} variant="primary">
            Submit
          </Button>
        </div>
      </div>
    </div>
  )
}

// In main JSX:
return (
  <div>
    {/* Main content */}
    {renderDialog()}
  </div>
)
```

---

## Conditional Rendering Pattern

### Show/Hide Based on State

```javascript
// Hide section when condition not met
{activeConfig && (
  <div className="space-y-3">
    <h2>Section Title</h2>
    {/* Section content */}
  </div>
)}

// Switch between different views
const renderContent = () => {
  if (isCreating) {
    return renderCreateForm()
  }

  if (items.length === 0) {
    return renderEmptyState()
  }

  return renderList()
}
```

---

## Styling Conventions

### Spacing Utilities

```javascript
// Container spacing
className="space-y-4"  // Vertical spacing between children (1rem)
className="space-y-6"  // Larger vertical spacing (1.5rem)
className="gap-2"      // Gap in flex/grid (0.5rem)
className="gap-4"      // Larger gap (1rem)

// Padding
className="p-4"        // All sides padding (1rem)
className="px-6 py-4"  // Horizontal 1.5rem, vertical 1rem
className="p-8"        // All sides padding (2rem)

// Margin
className="mb-4"       // Bottom margin (1rem)
className="mt-2"       // Top margin (0.5rem)
```

### Layout Classes

```javascript
// Flex layouts
className="flex items-center gap-3"              // Horizontal flex, centered vertically
className="flex items-center justify-between"   // Horizontal flex, space between
className="flex flex-col"                        // Vertical flex

// Grid layouts
className="grid grid-cols-2 gap-4"               // 2 columns
className="grid grid-cols-1 md:grid-cols-2 gap-4" // Responsive: 1 col mobile, 2 cols desktop
```

### Color Schemes

**Background colors**:
```javascript
className="bg-gray-50"      // Light gray background
className="bg-gray-100"     // Slightly darker gray
className="bg-white"        // White background
className="bg-blue-50"      // Light blue (info)
className="bg-red-50"       // Light red (error)
className="bg-green-50"     // Light green (success)
```

**Text colors**:
```javascript
className="text-gray-900"   // Dark text (primary)
className="text-gray-700"   // Medium dark (secondary)
className="text-gray-500"   // Light text (tertiary)
className="text-blue-700"   // Blue text (info)
className="text-red-700"    // Red text (error)
```

### Border and Rounding

```javascript
className="rounded-lg"                    // Large border radius
className="rounded-sm"                    // Small border radius
className="border border-gray-200"        // Light gray border
className="border-b border-gray-200"      // Bottom border only
```

---

## Icons

**Library**: `lucide-react`

**Common Icons**:
```javascript
import { Plus, Minus, Trash2, Settings, Camera, AlertCircle, CheckCircle, XCircle } from 'lucide-react'

<Plus size={16} />      // Plus icon, 16px
<Trash2 size={16} />    // Trash icon
<Settings size={16} />  // Settings icon
<Camera size={48} />    // Larger icon for empty states
```

**Usage in Buttons**:
```javascript
<Button>
  <Plus size={16} />
  Create
</Button>
```

---

## Best Practices

### 1. Component Organization

**Structure**:
```javascript
export function MyComponent() {
  // 1. State declarations
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(false)

  // 2. Effects
  useEffect(() => {
    loadData()
  }, [])

  // 3. Helper functions
  const loadData = async () => { /* ... */ }
  const handleCreate = () => { /* ... */ }

  // 4. Render functions (for complex sections)
  const renderList = () => ( /* ... */ )
  const renderDialog = () => ( /* ... */ )

  // 5. Main return (keep simple, use render functions)
  return (
    <div>
      {renderList()}
      {renderDialog()}
    </div>
  )
}
```

### 2. Error Handling

**Always handle API errors**:
```javascript
try {
  await someAPICall()
  // Success: update state, close dialog, etc.
} catch (err) {
  // Show user-friendly error
  alert(`Operation failed: ${err.message}`)
  // OR set error state for UI display
  setError(err.message)
}
```

### 3. Data Refresh Pattern

**After mutations, always refresh**:
```javascript
const handleDelete = async (id) => {
  if (!confirm('Delete this item?')) return

  try {
    await deleteItem(id)
    await loadItems()  // ← Refresh the list
  } catch (err) {
    alert(`Failed: ${err.message}`)
  }
}
```

### 4. Form Validation

**Client-side validation before API call**:
```javascript
const handleSubmit = async () => {
  // Validate input
  if (!name.trim()) {
    alert('Please enter a name')
    return
  }

  if (value < 0) {
    alert('Value must be positive')
    return
  }

  // Proceed with API call
  try {
    await createItem(name, value)
    // ...
  } catch (err) {
    alert(`Failed: ${err.message}`)
  }
}
```

### 5. Loading States

**Show feedback during async operations**:
```javascript
const [loading, setLoading] = useState(false)

const handleAction = async () => {
  setLoading(true)
  try {
    await someAPICall()
    // Success
  } catch (err) {
    alert(`Failed: ${err.message}`)
  } finally {
    setLoading(false)
  }
}

// In JSX:
<Button onClick={handleAction} disabled={loading}>
  {loading ? 'Saving...' : 'Save'}
</Button>
```

---

## Common Settings for Future Features

### Config Management Pattern

**Use this pattern for any feature requiring saved configurations**:

1. **API Functions** (`api.js`):
   - `listConfigs()` - GET /api/resource/configs
   - `createConfig(...)` - POST /api/resource/configs
   - `deleteConfig(name)` - DELETE /api/resource/configs/{name}
   - `activateConfig(name)` - POST /api/resource/configs/{name}/activate
   - `deactivateConfig()` - POST /api/resource/configs/deactivate

2. **Component State**:
   - `configs` - Array of config objects
   - `activeConfig` - Currently active config (or null)
   - `isCreating` - Boolean for create form visibility
   - `showSaveDialog` - Boolean for save dialog visibility

3. **UI Flow**:
   - Empty state → Create button → Form → Save dialog → List view
   - List view: Checkbox for activation, Edit button, Delete button
   - Only allow deleting inactive configs

**Example**: See `CVConfiguration.jsx` for full implementation

---

## Testing Checklist

When implementing new features:

- [ ] Empty state renders correctly
- [ ] Create form works with validation
- [ ] Save dialog validates input
- [ ] List displays all items
- [ ] Activate/deactivate toggles work
- [ ] Delete confirmation works
- [ ] Cannot delete active item
- [ ] API errors display to user
- [ ] Data refreshes after mutations
- [ ] Loading states work (if applicable)

---

## Related Documentation

- `06_MAP_CONFIGURATION.md` - User guide for map configuration feature
- `CV_CONFIGURATION_SYSTEM.md` - Backend technical documentation
- `CV_PERFORMANCE_OPTIMIZATION_IMPLEMENTATION.md` - Implementation summary

---

**Document Version**: 1.0
**Last Updated**: 2025-01-07
**Author**: Claude Code Implementation
