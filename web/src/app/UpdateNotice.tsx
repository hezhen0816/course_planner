import { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';

/**
 * 偵測「已部署新版但這個分頁還跑著舊的 JS」。
 *
 * 2026-09-09 連續踩到兩次：使用者長時間開著同一個分頁，部署後同步／設定看起來
 * 「沒生效」，其實是瀏覽器仍在跑載入當下的 bundle。做法是定期抓 index.html，
 * 比對裡面的 /assets/*.js 檔名與目前這個分頁載入的是否相同，不同就提示重新整理。
 */
const CHECK_INTERVAL_MS = 5 * 60 * 1000;

function currentBundleUrl(): string {
  const scripts = Array.from(document.querySelectorAll<HTMLScriptElement>('script[src]'));
  const asset = scripts.map((script) => script.src).find((src) => src.includes('/assets/'));
  return asset ? new URL(asset, location.href).pathname : '';
}

async function deployedBundleUrl(): Promise<string> {
  // cache: 'no-store' 才拿得到新的 index.html；否則會讀到快取而永遠比對相同
  const response = await fetch(`${location.origin}/?_=${Date.now()}`, { cache: 'no-store' });
  if (!response.ok) return '';
  const html = await response.text();
  return html.match(/src="(\/assets\/[^"]+\.js)"/)?.[1] || '';
}

export function UpdateNotice() {
  const [hasUpdate, setHasUpdate] = useState(false);

  useEffect(() => {
    const loaded = currentBundleUrl();
    if (!loaded) return;
    let cancelled = false;

    const check = async () => {
      try {
        const deployed = await deployedBundleUrl();
        if (!cancelled && deployed && deployed !== loaded) setHasUpdate(true);
      } catch {
        // 離線或後端不可達時不提示，避免誤報
      }
    };

    const timer = setInterval(check, CHECK_INTERVAL_MS);
    const onVisible = () => { if (document.visibilityState === 'visible') void check(); };
    document.addEventListener('visibilitychange', onVisible);
    void check();

    return () => {
      cancelled = true;
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, []);

  if (!hasUpdate) return null;

  return (
    <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
      <RefreshCw className="h-4 w-4 shrink-0 text-blue-600" />
      <span>已有新版本，重新整理後才會套用最新的功能與修正。</span>
      <button
        type="button"
        onClick={() => location.reload()}
        className="ml-auto whitespace-nowrap rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
      >
        立即重新整理
      </button>
    </div>
  );
}
