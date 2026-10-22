const CACHE_NAME = 'sabuj-boi-v2';
const urlsToCache = [
  '/',
  '/static/style.css',
  '/static/search.js',
  '/static/script.js',
  '/static/icon-192x192.png',
  '/static/icon-512x512.png'
];

// Install event - cache files
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
  // নতুন সার্ভিস ওয়ার্কারকে সাথে সাথে অ্যাক্টিভ হতে বাধ্য করা
  self.skipWaiting();
});

// Fetch event - serve from cache if offline
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Return cache response if found, else fetch from network
        return response || fetch(event.request);
      })
  );
});

// Activate event - clear old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  // নতুন সার্ভিস ওয়ার্কারকে সাথে সাথে কন্ট্রোল নিতে বাধ্য করা
  return self.clients.claim();
});