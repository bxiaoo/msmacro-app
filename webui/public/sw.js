// MS Macro Service Worker
// Handles push notifications and basic caching for PWA

const CACHE_NAME = 'msmacro-v1';

// Install event - cache essential assets
self.addEventListener('install', (event) => {
  console.log('[SW] Installing service worker');
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating service worker');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

// Push event - show notification when push received
self.addEventListener('push', (event) => {
  console.log('[SW] Push received:', event);

  let data = {
    title: 'MS Macro',
    body: 'New notification',
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    tag: 'msmacro-notification',
    priority: 'info'
  };

  if (event.data) {
    try {
      data = { ...data, ...event.data.json() };
    } catch (e) {
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body,
    icon: data.icon || '/icon-192.png',
    badge: data.badge || '/icon-192.png',
    tag: data.tag || 'msmacro-notification',
    vibrate: data.priority === 'critical' ? [200, 100, 200, 100, 200] : [100, 50, 100],
    requireInteraction: data.priority === 'critical',
    data: {
      url: data.url || '/',
      timestamp: Date.now(),
      priority: data.priority
    }
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Notification click - open app or focus existing window
self.addEventListener('notificationclick', (event) => {
  console.log('[SW] Notification clicked:', event);
  event.notification.close();

  const urlToOpen = event.notification.data?.url || '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // Try to focus existing window
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          return client.focus();
        }
      }
      // Open new window if none exists
      if (clients.openWindow) {
        return clients.openWindow(urlToOpen);
      }
    })
  );
});

// Message event - handle messages from main thread
self.addEventListener('message', (event) => {
  console.log('[SW] Message received:', event.data);

  if (event.data.type === 'SHOW_NOTIFICATION') {
    const { title, body, priority, tag } = event.data;

    self.registration.showNotification(title || 'MS Macro', {
      body: body || '',
      icon: '/icon-192.png',
      badge: '/icon-192.png',
      tag: tag || 'msmacro-' + Date.now(),
      vibrate: priority === 'critical' ? [200, 100, 200, 100, 200] : [100, 50, 100],
      requireInteraction: priority === 'critical',
      data: {
        url: '/',
        timestamp: Date.now(),
        priority: priority || 'info'
      }
    });
  }
});

// Fetch event - network first, fallback to cache
self.addEventListener('fetch', (event) => {
  // Skip non-GET requests and API calls (we want fresh data)
  if (event.request.method !== 'GET' || event.request.url.includes('/api/')) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Cache successful responses
        if (response.ok) {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone);
          });
        }
        return response;
      })
      .catch(() => {
        // Fallback to cache if network fails
        return caches.match(event.request);
      })
  );
});
