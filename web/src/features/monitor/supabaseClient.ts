import { supabase as client } from '../../shared/supabase';

if (!client) throw new Error('Supabase 未設定');

export const supabase = client;
