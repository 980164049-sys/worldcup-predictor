// Service Worker — 缓存静态资源，加速二次加载
const CACHE = 'worldcup-v1';
const ASSETS = [
    '/',
    '/static/style.css',
    '/static/script.js',
    '/static/manifest.json'
];

self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE).then(c => c.addAll(ASSETS))
    );
});

self.addEventListener('fetch', e => {
    e.respondWith(
        caches.match(e.request).then(r => r || fetch(e.request))
    );
});
