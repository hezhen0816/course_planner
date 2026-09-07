#!/usr/bin/env python3
"""
Move monitor users' school credentials from user_settings (Fernet with ENCRYPTION_KEY)
into app_private.school_credentials (Compass store, SCHOOL_CREDENTIALS_ENCRYPTION_SECRET).

Run from the repo root with the project venv:
  python scripts/monitor/migrate_monitor_credentials.py            # dry run
  python scripts/monitor/migrate_monitor_credentials.py --apply    # write

Existing app_private rows are never overwritten.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, '.env'))

from supabase import create_client  # noqa: E402

from backend.credentials import get_school_credentials_status, put_school_credentials  # noqa: E402
from backend.monitor.crypto import CryptoManager  # noqa: E402


def main() -> int:
    apply = '--apply' in sys.argv
    url = os.getenv('SUPABASE_URL') or os.getenv('VITE_SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    if not (url and key):
        print('缺少 SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY', file=sys.stderr)
        return 1
    crypto = CryptoManager()
    if crypto.fernet is None:
        print('缺少 ENCRYPTION_KEY', file=sys.stderr)
        return 1
    client = create_client(url, key)
    rows = client.table('user_settings').select('user_id,student_id,student_password,is_encrypted').execute().data
    todo = []
    for row in rows:
        uid = row['user_id']
        sid = (row.get('student_id') or '').strip()
        pw = row.get('student_password') or ''
        if not sid or not pw:
            continue
        status = get_school_credentials_status(uid)
        if status.get('hasPassword'):
            print(f'{uid[:8]} 已有 app_private 帳密，略過')
            continue
        plain = crypto.decrypt(pw) if row.get('is_encrypted') else pw
        todo.append((uid, sid, plain))
    print(f'待搬移 {len(todo)} 位使用者')
    if not apply:
        print('（dry run，加 --apply 才寫入）')
        return 0
    for uid, sid, plain in todo:
        put_school_credentials(uid, sid, plain)
        print(f'{uid[:8]} -> app_private.school_credentials（{sid[:3]}…）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
