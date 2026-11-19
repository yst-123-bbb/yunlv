const STATIC_CACHE = "cloudtrip-static-v2";
const API_CACHE = "cloudtrip-api-v2";
const PRECACHE_URLS = ["/", "/index.html", "/manifest.json"];

// 只缓存带指纹的构建产物与图标；源码目录 /src/ 一律不拦截
const ASSET_PATH = /^\/(assets\/|icon-|manifest\.json)/;

// 单个行程详情是离线主力数据源；分享页与其它接口按需缓存
const PLAN_DETAIL_PATH = /^\/api\/plan\/[^/]+$/;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  const keep = new Set([STATIC_CACHE, API_CACHE]);
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => !keep.has(key)).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;

  const response = await fetch(request);
  if (response.ok) cache.put(request, response.clone());
  return response;
}

async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw error;
  }
}

async function offlineShell() {
  const cached = await caches.match("/index.html");
  if (cached) return cached;
  return new Response("离线且无缓存页面", {
    status: 503,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(networkFirst(request, STATIC_CACHE).catch(offlineShell));
    return;
  }

  if (PLAN_DETAIL_PATH.test(url.pathname)) {
    event.respondWith(cacheFirst(request, API_CACHE));
    return;
  }

  if (url.pathname.startsWith("/api/")) {
    event.respondWith(networkFirst(request, API_CACHE));
    return;
  }

  // 仅缓存带指纹的构建产物，其余同源请求交给网络（避免缓存住源码模块）
  if (ASSET_PATH.test(url.pathname)) {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
  }
});