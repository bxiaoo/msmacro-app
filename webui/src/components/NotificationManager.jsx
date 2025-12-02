import { useState, useEffect } from 'react'
import { Bell, BellOff, BellRing, CheckCircle, XCircle } from 'lucide-react'

/**
 * NotificationManager - Handles push notification permissions and settings
 *
 * This component provides:
 * - Permission request button for push notifications
 * - Status display (granted, denied, not supported)
 * - Toggle for enabling/disabling notifications
 *
 * For iOS PWA:
 * - Must be installed to home screen first
 * - Permission request must come from user gesture (button tap)
 */
export function NotificationManager() {
  const [permission, setPermission] = useState('default')
  const [notificationsEnabled, setNotificationsEnabled] = useState(false)
  const [isPWA, setIsPWA] = useState(false)
  const [isSupported, setIsSupported] = useState(false)

  useEffect(() => {
    // Check if notifications are supported
    const supported = 'Notification' in window && 'serviceWorker' in navigator
    setIsSupported(supported)

    // Check if running as PWA (standalone mode)
    const standalone = window.matchMedia('(display-mode: standalone)').matches ||
                       window.navigator.standalone === true
    setIsPWA(standalone)

    // Get current permission status
    if (supported) {
      setPermission(Notification.permission)
      setNotificationsEnabled(Notification.permission === 'granted')
    }

    // Load saved preference
    const saved = localStorage.getItem('msmacro-notifications-enabled')
    if (saved !== null) {
      setNotificationsEnabled(saved === 'true')
    }
  }, [])

  const requestPermission = async () => {
    if (!isSupported) {
      console.error('Notifications not supported')
      return
    }

    try {
      const result = await Notification.requestPermission()
      setPermission(result)
      setNotificationsEnabled(result === 'granted')
      localStorage.setItem('msmacro-notifications-enabled', result === 'granted' ? 'true' : 'false')

      if (result === 'granted') {
        // Send test notification
        showTestNotification()
      }
    } catch (error) {
      console.error('Failed to request notification permission:', error)
    }
  }

  const toggleNotifications = () => {
    const newValue = !notificationsEnabled
    setNotificationsEnabled(newValue)
    localStorage.setItem('msmacro-notifications-enabled', newValue ? 'true' : 'false')
  }

  const showTestNotification = () => {
    if (!navigator.serviceWorker?.controller) {
      // Fallback to regular notification
      new Notification('MS Macro', {
        body: 'Notifications enabled successfully!',
        icon: '/icon-192.png'
      })
    } else {
      // Use service worker for notification
      navigator.serviceWorker.controller.postMessage({
        type: 'SHOW_NOTIFICATION',
        title: 'MS Macro',
        body: 'Notifications enabled successfully!',
        priority: 'info'
      })
    }
  }

  // Not supported
  if (!isSupported) {
    return (
      <div className="bg-gray-100 rounded-lg p-4 border border-gray-200">
        <div className="flex items-center gap-3">
          <BellOff className="text-gray-400" size={24} />
          <div>
            <p className="font-semibold text-gray-900">Notifications Not Supported</p>
            <p className="text-sm text-gray-600">
              Your browser doesn't support push notifications
            </p>
          </div>
        </div>
      </div>
    )
  }

  // iOS but not PWA
  if (!isPWA && /iPhone|iPad|iPod/.test(navigator.userAgent)) {
    return (
      <div className="bg-yellow-50 rounded-lg p-4 border border-yellow-200">
        <div className="flex items-center gap-3">
          <Bell className="text-yellow-600" size={24} />
          <div>
            <p className="font-semibold text-yellow-900">Install App for Notifications</p>
            <p className="text-sm text-yellow-700">
              To enable notifications on iOS:
            </p>
            <ol className="text-sm text-yellow-700 mt-2 ml-4 list-decimal">
              <li>Tap the Share button in Safari</li>
              <li>Select "Add to Home Screen"</li>
              <li>Open the app from your home screen</li>
            </ol>
          </div>
        </div>
      </div>
    )
  }

  // Permission denied
  if (permission === 'denied') {
    return (
      <div className="bg-red-50 rounded-lg p-4 border border-red-200">
        <div className="flex items-center gap-3">
          <XCircle className="text-red-500" size={24} />
          <div>
            <p className="font-semibold text-red-900">Notifications Blocked</p>
            <p className="text-sm text-red-700">
              Notifications are blocked. Please enable them in your browser/device settings.
            </p>
          </div>
        </div>
      </div>
    )
  }

  // Permission granted
  if (permission === 'granted') {
    return (
      <div className="bg-emerald-50 rounded-lg p-4 border border-emerald-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CheckCircle className="text-emerald-500" size={24} />
            <div>
              <p className="font-semibold text-emerald-900">Notifications Enabled</p>
              <p className="text-sm text-emerald-700">
                You'll receive alerts for important events
              </p>
            </div>
          </div>
          <button
            onClick={toggleNotifications}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              notificationsEnabled
                ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            {notificationsEnabled ? 'On' : 'Off'}
          </button>
        </div>
      </div>
    )
  }

  // Permission not yet requested
  return (
    <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BellRing className="text-blue-500" size={24} />
          <div>
            <p className="font-semibold text-blue-900">Enable Notifications</p>
            <p className="text-sm text-blue-700">
              Get alerts for rune detection, errors, and more
            </p>
          </div>
        </div>
        <button
          onClick={requestPermission}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
        >
          Enable
        </button>
      </div>
    </div>
  )
}

/**
 * Send a notification via the service worker
 * Call this from anywhere in the app to trigger a push notification
 */
export function sendNotification({ title, body, priority = 'info', tag }) {
  // Check if notifications are enabled
  const enabled = localStorage.getItem('msmacro-notifications-enabled') === 'true'
  if (!enabled) {
    console.log('[Notifications] Disabled by user preference')
    return
  }

  if (Notification.permission !== 'granted') {
    console.log('[Notifications] Permission not granted')
    return
  }

  if (navigator.serviceWorker?.controller) {
    navigator.serviceWorker.controller.postMessage({
      type: 'SHOW_NOTIFICATION',
      title,
      body,
      priority,
      tag
    })
  } else {
    // Fallback for when SW not ready
    new Notification(title, {
      body,
      icon: '/icon-192.png',
      tag
    })
  }
}
