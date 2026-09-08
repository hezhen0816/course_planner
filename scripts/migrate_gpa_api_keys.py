#!/usr/bin/env python3
"""One-off (2026-09-08): move myNTUST GPA tokens out of public.user_data.

`content.settings.gpaApi.apiKey` was readable by anyone holding the user's own
Supabase session. Re-store it encrypted in app_private.gpa_api_keys and drop the
JSON field.

  PYTHONPATH=. python scripts/migrate_gpa_api_keys.py            # report only
  PYTHONPATH=. python scripts/migrate_gpa_api_keys.py --apply    # write
"""
from __future__ import annotations

import sys

from dotenv import load_dotenv

load_dotenv('.env')

from backend import credentials as cred  # noqa: E402
from backend.config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL  # noqa: E402

import requests  # noqa: E402


def main() -> int:
    apply = '--apply' in sys.argv
    if not (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY):
        print('缺少 SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY', file=sys.stderr)
        return 1
    headers = {
        'apikey': SUPABASE_SERVICE_ROLE_KEY,
        'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal',
    }
    response = requests.get(f'{SUPABASE_URL}/rest/v1/user_data?select=user_id,content', headers=headers, timeout=30)
    response.raise_for_status()

    todo = []
    for row in response.json():
        content = row.get('content') or {}
        settings = content.get('settings') or {}
        gpa_api = settings.get('gpaApi')
        if not isinstance(gpa_api, dict):
            continue
        api_key = str(gpa_api.get('apiKey') or '').strip()
        enabled = bool(gpa_api.get('enabled'))
        todo.append((row['user_id'], content, api_key, enabled))
        print(f"{row['user_id'][:8]}: key {len(api_key)} 字元, enabled={enabled} → "
              f"{'搬到 app_private 並清除' if api_key else '只清除空設定'}")

    print(f'共 {len(todo)} 位使用者')
    if not apply:
        print('（dry run，加 --apply 才寫入）')
        return 0

    for user_id, content, api_key, enabled in todo:
        if api_key:
            cred.put_gpa_api_key(user_id, api_key, enabled)
        content.setdefault('settings', {}).pop('gpaApi', None)
        patch = requests.patch(
            f'{SUPABASE_URL}/rest/v1/user_data?user_id=eq.{user_id}',
            headers=headers, json={'content': content}, timeout=30,
        )
        patch.raise_for_status()
        print(f'{user_id[:8]} 完成')
    return 0


if __name__ == '__main__':
    sys.exit(main())
