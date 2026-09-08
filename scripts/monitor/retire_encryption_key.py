#!/usr/bin/env python3
"""One-off (2026-09-08): retire the worker's separate ENCRYPTION_KEY.

- smtp_password / resend_api_key in user_settings that were encrypted with the old
  Fernet ENCRYPTION_KEY are re-encrypted with SCHOOL_CREDENTIALS_ENCRYPTION_SECRET
  (the key the whole backend already uses for app_private.school_credentials).
- user_settings.student_password is cleared: every monitor user's school password
  lives in app_private.school_credentials (the script refuses to clear a row that
  has no app_private credentials).

Run from the repo root with the project venv. Dry run by default:
  PYTHONPATH=. python scripts/monitor/retire_encryption_key.py            # report only
  PYTHONPATH=. python scripts/monitor/retire_encryption_key.py --apply    # write
Requires the OLD key in env as ENCRYPTION_KEY (only for decrypting), plus SUPABASE_URL,
SUPABASE_SERVICE_ROLE_KEY and SCHOOL_CREDENTIALS_ENCRYPTION_SECRET.
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv('.env')

import requests  # noqa: E402
from cryptography.fernet import Fernet  # noqa: E402

from backend import credentials as cred  # noqa: E402

FIELDS = ('smtp_password', 'resend_api_key')


def main() -> int:
    apply = '--apply' in sys.argv
    url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    old_key = os.environ.get('ENCRYPTION_KEY', '')
    if not (url and key and old_key):
        print('缺少 SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / ENCRYPTION_KEY（舊金鑰，只用來解密）', file=sys.stderr)
        return 1
    old = Fernet(old_key.encode())
    new = cred._fernet()
    headers = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json', 'Prefer': 'return=minimal'}

    rows = requests.get(f'{url}/rest/v1/user_settings?select=user_id,student_id,is_encrypted,student_password,smtp_password,resend_api_key', headers=headers, timeout=30)
    rows.raise_for_status()
    plan: list[tuple[str, dict]] = []
    for row in rows.json():
        uid = row['user_id']
        update: dict = {}
        for field in FIELDS:
            token = row.get(field) or ''
            if not token:
                continue
            try:
                plain = old.decrypt(token.encode()).decode()
            except Exception:
                try:  # already on the new secret? then nothing to do
                    new.decrypt(token.encode())
                    print(f'{uid[:8]} {field}: 已是新密鑰，略過')
                    continue
                except Exception:
                    print(f'{uid[:8]} {field}: 兩把金鑰都解不開，跳過（請人工確認）', file=sys.stderr)
                    continue
            update[field] = new.encrypt(plain.encode()).decode()
        if row.get('student_password'):
            if not cred._load_school_credentials_row(uid):
                print(f'{uid[:8]}: user_settings 有 student_password 但 app_private 沒有帳密，拒絕清除', file=sys.stderr)
                return 2
            update['student_password'] = None
        if update:
            update['is_encrypted'] = True if any(f in update for f in FIELDS) else row.get('is_encrypted')
            plan.append((uid, update))
            print(f"{uid[:8]} ({row.get('student_id')}): " + ', '.join(
                f'{k}=清除' if v is None else f'{k}=重新加密' if k in FIELDS else f'{k}={v}' for k, v in update.items()))
    print(f'共 {len(plan)} 列要更新')
    if not apply:
        print('（dry run，加 --apply 才寫入）')
        return 0
    for uid, update in plan:
        resp = requests.patch(f'{url}/rest/v1/user_settings?user_id=eq.{uid}', headers=headers, json=update, timeout=30)
        resp.raise_for_status()
        print(f'{uid[:8]} 已更新')
    return 0


if __name__ == '__main__':
    sys.exit(main())
