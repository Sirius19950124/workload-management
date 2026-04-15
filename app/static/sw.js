// Service Worker for Workload Management PWA
const CACHE_NAME = 'workload-v1';
const STATIC_ASSETS = [
    '/mobile',
    '/static/manifest.json',
    '/static/css/bootstrap.min.css',
    '/static/css/font-awesome.min.css'
];

// 安装事件 - 缓存静态资源
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[SW] Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .catch((err) => {
                console.log('[SW] Cache failed:', err);
            })
    );
    self.skipWaiting();
});

// 激活事件 - 清理旧缓存
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('[SW] Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

// 请求拦截 - 网络优先，缓存作为后备
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // API 请求 - 网络优先
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(request)
                .then((response) => {
                    // 缓存成功的响应
                    if (response.status === 200) {
                        const responseClone = response.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(request, responseClone);
                        });
                    }
                    return response;
                })
                .catch(() => {
                    // 网络失败时返回缓存
                    return caches.match(request);
                })
        );
        return;
    }

    // 静态资源 - 缓存优先
    event.respondWith(
        caches.match(request)
            .then((cachedResponse) => {
                if (cachedResponse) {
                    return cachedResponse;
                }
                return fetch(request).then((response) => {
                    if (response.status === 200) {
                        const responseClone = response.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(request, responseClone);
                        });
                    }
                    return response;
                });
            })
    );
});

// 后台同步（如果支持）
self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-records') {
        console.log('[SW] Background sync triggered');
    }
});
