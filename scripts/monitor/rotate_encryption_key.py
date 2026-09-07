#!/usr/bin/env python3
"""
Rotate ENCRYPTION_KEY: re-encrypt every Fernet-encrypted secret in user_settings
with a fresh key, then write the new key into the repo-root .env.

Run from the repo root with the project venv, while the worker is STOPPED:
  python backend/scripts/rotate_encryption_key.py            # dry run (verifies only)
  python backend/scripts/rotate_encryption_key.py --apply    # rotate for real

After --apply, copy the printed ENCRYPTION_KEY line into every other .env that
runs the worker (e.g. the Windows host), then start the worker again.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, '.env'))
load_dotenv(os.path.join(ROOT, 'frontend', '.env'))

from cryptography.fernet import Fernet  # noqa: E402
from supabase import create_client  # noqa: E402

ENCRYPTED_FIELDS = ('student_password', 'smtp_password', 'resend_api_key')


def main() -> int:
    apply = '--apply' in sys.argv
    url = os.getenv('VITE_SUPABASE_URL') or os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    old_key = os.getenv('ENCRYPTION_KEY')
    if not (url and service_key and old_key):
        print('缺少 VITE_SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / ENCRYPTION_KEY', file=sys.stderr)
        return 1

    old = Fernet(old_key.encode())
    new_key = Fernet.generate_key()
    new = Fernet(new_key)
    client = create_client(url, service_key)

    rows = client.table('user_settings').select('user_id,' + ','.join(ENCRYPTED_FIELDS)).execute().data
    plan = []
    for row in rows:
        update = {}
        for field in ENCRYPTED_FIELDS:
            value = row.get(field)
            if not value:
                continue
            try:
                plaintext = old.decrypt(value.encode())
            except Exception:
                print(f"使用者 {row['user_id'][:8]} 的 {field} 無法用舊金鑰解密，中止。", file=sys.stderr)
                return 1
            update[field] = new.encrypt(plaintext).decode()
        if update:
            plan.append((row['user_id'], update))

    print(f'待重加密：{len(plan)} 位使用者，{sum(len(u) for _, u in plan)} 個欄位')
    if not apply:
        print('（dry run，未寫入；加 --apply 才會執行）')
        return 0

    for user_id, update in plan:
        client.table('user_settings').update(update).eq('user_id', user_id).execute()

    rows = client.table('user_settings').select('user_id,' + ','.join(ENCRYPTED_FIELDS)).execute().data
    for row in rows:
        for field in ENCRYPTED_FIELDS:
            if row.get(field):
                new.decrypt(row[field].encode())
    print('資料庫重加密完成，已用新金鑰驗證。')

    env_path = os.path.join(ROOT, '.env')
    content = open(env_path, encoding='utf-8').read()
    line = 'ENCRYPTION_KEY=' + new_key.decode()
    if re.search(r'^ENCRYPTION_KEY=.*$', content, flags=re.M):
        content = re.sub(r'^ENCRYPTION_KEY=.*$', line, content, flags=re.M)
    else:
        content = content.rstrip('\n') + '\n' + line + '\n'
    open(env_path, 'w', encoding='utf-8').write(content)
    print(f'已更新 {env_path}')
    print('請把下面這行放進其他執行 worker 的 .env（例如 Windows 主機），再重啟 worker：')
    print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
