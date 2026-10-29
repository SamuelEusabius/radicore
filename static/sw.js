const CACHE_NAME = 'racodcore-v1';
const ASSETS_TO_CACHE = [
    '/',
    '/static/css/design-tokens.css',
    '/static/css/components.css',
    '/static/css/utilities.css',
    '/static/images/graduation-cap-books.png'
];

// Install event - cache assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
    self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cache) => {
                    if (cache !== CACHE_NAME) {
                        return caches.delete(cache);
                    }
                })
            );
        })
    );
});

// Fetch event - serve from cache or network
self.addEventListener('fetch', (event) => {
    // Only cache GET requests
    if (event.request.method !== 'GET') return;
    
    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            if (cachedResponse) {
                return cachedResponse;
            }
            return fetch(event.request).then((networkResponse) => {
                // Don't cache dashboard/admin URLs to protect private data
                if (event.request.url.includes('/dashboard/') || 
                    event.request.url.includes('/accounts/') || 
                    event.request.url.includes('/api/')) {
                    return networkResponse;
                }
                
                return caches.open(CACHE_NAME).then((cache) => {
                    cache.put(event.request, networkResponse.clone());
                    return networkResponse;
                });
            });
        }).catch(() => {
            // If both cache and network fail (offline)
            return caches.match('/');
        })
    );
});