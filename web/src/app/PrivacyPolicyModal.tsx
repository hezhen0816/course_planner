import React from 'react';
import { Shield, Lock, Server, EyeOff } from 'lucide-react';

interface PrivacyPolicyModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const PrivacyPolicyModal: React.FC<PrivacyPolicyModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden max-h-[90vh] flex flex-col">
        <div className="px-6 py-4 border-b border-slate-100 bg-slate-50 flex justify-between items-center">
          <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
            <Shield className="w-5 h-5 text-blue-600" />
            隱私權與安全說明
          </h3>
          <button 
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 transition-colors"
          >
            ✕
          </button>
        </div>
        
        <div className="p-6 overflow-y-auto text-slate-600 space-y-6">
          <section>
            <h4 className="font-bold text-slate-800 mb-2 flex items-center gap-2">
              <Lock className="w-4 h-4 text-green-600" />
              密碼安全
            </h4>
            <p className="text-sm leading-relaxed">
              您的密碼在傳輸與儲存過程中皆經過高強度的雜湊加密處理（Hashing）。
              系統開發者與管理員<strong>無法查看或還原您的原始密碼</strong>。
              我們使用業界標準的加密演算法，確保您的帳號安全。
            </p>
          </section>

          <section>
            <h4 className="font-bold text-slate-800 mb-2 flex items-center gap-2">
              <Server className="w-4 h-4 text-blue-600" />
              資料儲存與隔離
            </h4>
            <p className="text-sm leading-relaxed">
              本系統使用雲端資料庫與帳號隔離機制。
              我們採用列級安全性（Row Level Security, RLS）技術，
              確保只有您登入後才能存取屬於您的修課規劃資料，其他使用者無法窺探。
            </p>
          </section>

          <section>
            <h4 className="font-bold text-slate-800 mb-2 flex items-center gap-2">
              <EyeOff className="w-4 h-4 text-purple-600" />
              隱私權聲明
            </h4>
            <p className="text-sm leading-relaxed">
              本系統僅收集您的 Email 作為帳號識別，以及您自行輸入/匯入的課程資料。
              這些資料僅用於提供修課規劃功能，絕不會用於其他商業用途或提供給第三方。
              您可以隨時聯繫管理員刪除您的帳號與所有資料。
            </p>
          </section>
        </div>

        <div className="p-4 border-t border-slate-100 bg-slate-50 text-center">
          <button 
            onClick={onClose}
            className="px-6 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors"
          >
            我了解了
          </button>
        </div>
      </div>
    </div>
  );
};
