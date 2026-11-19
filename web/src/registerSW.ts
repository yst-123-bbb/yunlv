function registerServiceWorker(): void {
  if (!("serviceWorker" in navigator)) return;

  // 只在生产构建注册：Vite dev 按需编译 /src 源码模块，而 sw.js 对同源资源走
  // cache-first，会把源码模块永久缓存住，导致改动不生效、HMR 失效。
  if (!import.meta.env.PROD) return;

  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((error) => {
      // 注册失败只降级为在线模式，不影响页面功能
      console.warn("service_worker_registration_failed", error);
    });
  });
}

registerServiceWorker();