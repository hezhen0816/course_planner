import React, { useState } from 'react';
import { GraduationCap, AlertCircle, User, ShieldCheck } from 'lucide-react'; // 加入 User icon
import { supabase } from '../supabase';
import { PrivacyPolicyModal } from './PrivacyPolicyModal';

// 新增 Props 定義
interface AuthPageProps {
  onDemoLogin: () => void;
}

export const AuthPage: React.FC<AuthPageProps> = ({ onDemoLogin }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [authMode, setAuthMode] = useState<'login' | 'signup'>('login');
  const [loading, setLoading] = useState(false);
  const [isPrivacyOpen, setIsPrivacyOpen] = useState(false);

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!supabase) return;
    setLoading(true);
    if (authMode === 'login') {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) alert(error.message);
    } else {
      const { error } = await supabase.auth.signUp({ email, password });
      if (error) alert(error.message);
      else alert('註冊成功！請檢查信箱驗證連結 (或直接登入)');
    }
    setLoading(false);
  };

  if (!supabase) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8 text-center">
          <AlertCircle className="w-12 h-12 text-red-600 mx-auto mb-4" />
          <h1 className="text-xl font-bold text-gray-900 mb-2">尚未設定 Supabase</h1>
          <p className="text-gray-600 mb-4">
            請確認專案根目錄下的 <code>.env</code> 檔案已正確設定 Supabase URL 與 Anon Key。
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8">
        <div className="text-center mb-8">
          <GraduationCap className="w-12 h-12 text-blue-600 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-gray-900">修課規劃助手</h1>
          <p className="text-gray-600 mt-2">請先登入以儲存資料，或使用功能演示快速體驗</p>
        </div>
        
        <form onSubmit={handleAuth} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Email</label>
            <input
              type="email"
              required
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 border p-2"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">密碼</label>
            <input
              type="password"
              required
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 border p-2"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
          >
            {loading ? '處理中...' : (authMode === 'login' ? '登入' : '註冊')}
          </button>
        </form>

        <div className="mt-4">
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-300" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-white text-gray-500">或</span>
            </div>
          </div>

          <button
            onClick={onDemoLogin}
            className="mt-4 w-full flex justify-center items-center gap-2 py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <User className="w-4 h-4" />
            進入功能演示 (不儲存資料)
          </button>
        </div>

        <div className="mt-4 text-center space-y-3">
          <button
            onClick={() => setAuthMode(authMode === 'login' ? 'signup' : 'login')}
            className="text-sm text-blue-600 hover:text-blue-500 block w-full"
          >
            {authMode === 'login' ? '沒有帳號？點此註冊' : '已有帳號？點此登入'}
          </button>

          <button
            onClick={() => setIsPrivacyOpen(true)}
            className="text-xs text-gray-400 hover:text-gray-600 flex items-center justify-center gap-1 w-full"
          >
            <ShieldCheck className="w-3 h-3" />
            隱私權與安全說明
          </button>
        </div>
      </div>

      <PrivacyPolicyModal 
        isOpen={isPrivacyOpen} 
        onClose={() => setIsPrivacyOpen(false)} 
      />
    </div>
  );
};
