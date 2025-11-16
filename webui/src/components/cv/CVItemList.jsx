import { useState, useEffect } from 'react'
import { CirclePlus } from 'lucide-react'
import { listCVItems, activateCVItem, deactivateCVItem, deleteCVItem } from '../../api'
import { CVItemCard } from './CVItemCard'
import { CVItemDrawer } from './CVItemDrawer'
import {AddButton} from "../ui/add-button.jsx";

export function CVItemList() {
  const [items, setItems] = useState([])
  const [activeItemName, setActiveItemName] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showDrawer, setShowDrawer] = useState(false)
  const [editingItem, setEditingItem] = useState(null)

  // Load CV items from API
  const loadCVItems = async () => {
    try {
      const data = await listCVItems()
      setItems(data.items || [])
      setActiveItemName(data.active_item || null)
      setLoading(false)
    } catch (error) {
      console.error('Failed to load CV Items:', error)
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCVItems()
  }, [])

  const handleActivate = async (name) => {
    try {
      // If clicking on already active item, deactivate it
      if (name === activeItemName) {
        await deactivateCVItem()
        setActiveItemName(null)
      } else {
        // Activate the selected item
        await activateCVItem(name)
        setActiveItemName(name)
      }
      // Reload items to get updated state
      await loadCVItems()
    } catch (error) {
      alert(`Failed to ${name === activeItemName ? 'deactivate' : 'activate'} CV Item: ${error.message}`)
    }
  }

  const handleEdit = (item) => {
    setEditingItem(item)
    setShowDrawer(true)
  }

  const handleDelete = async (name) => {
    try {
      await deleteCVItem(name)
      await loadCVItems()
    } catch (error) {
      alert(`Failed to delete CV Item: ${error.message}`)
    }
  }

  const handleAdd = () => {
    setEditingItem(null)
    setShowDrawer(true)
  }

  const handleDrawerClose = () => {
    setShowDrawer(false)
    setEditingItem(null)
  }

  const handleDrawerSave = () => {
    setShowDrawer(false)
    setEditingItem(null)
    loadCVItems()
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <p className="text-gray-500">Loading...</p>
      </div>
    )
  }

  // Empty state
  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-4 rounded-lg">

          <AddButton onClick={handleAdd} />

        {showDrawer && (
          <CVItemDrawer
            isOpen={showDrawer}
            onClose={handleDrawerClose}
            onSave={handleDrawerSave}
            editingItem={editingItem}
          />
        )}
      </div>
    )
  }

  // List view
  return (
    <div className="flex flex-col gap-2 px-3 py-0">
      {/* CV Items list */}
      {items.map((item) => (
        <CVItemCard
          key={item.name}
          item={item}
          isActive={item.name === activeItemName}
          onActivate={handleActivate}
          onEdit={handleEdit}
          onDelete={handleDelete}
          showDeparturePoints={false}
        />
      ))}

        <AddButton onClick={handleAdd} />

      {/* Drawer */}
      {showDrawer && (
        <CVItemDrawer
          isOpen={showDrawer}
          onClose={handleDrawerClose}
          onSave={handleDrawerSave}
          editingItem={editingItem}
        />
      )}
    </div>
  )
}
