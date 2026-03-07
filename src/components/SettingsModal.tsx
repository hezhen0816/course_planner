import React, { useState, useEffect } from 'react';
import type { AppData } from '../types';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (targets: AppData['targets']) => void;
  initialSettings: AppData['targets'];
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose, onSave, initialSettings }) => {
  const [settingsForm, setSettingsForm] = useState(initialSettings);

  useEffect(() => {
    setSettingsForm(initialSettings);
  }, [initialSettings, isOpen]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(settingsForm);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 bg-slate-50 flex justify-between items-center">
          <h3 className="text-lg font-bold text-slate-800">
            設定畢業門檻
          </h3>
          <button 
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600"
          >
            ✕
          </button>
        </div>
        
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-slate-700 mb-1">畢業總學分</label>
              <input 
                type="number" 
                min="0"
                value={settingsForm.total}
                onChange={(e) => setSettingsForm({...settingsForm, total: Number(e.target.value)})}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">必修國文</label>
              <input 
                type="number" 
                min="0"
                value={settingsForm.chinese}
                onChange={(e) => setSettingsForm({...settingsForm, chinese: Number(e.target.value)})}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">共同必修英文</label>
              <input 
                type="number" 
                min="0"
                value={settingsForm.english}
                onChange={(e) => setSettingsForm({...settingsForm, english: Number(e.target.value)})}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">通識學分</label>
              <input 
                type="number" 
                min="0"
                value={settingsForm.gen_ed}
                onChange={(e) => setSettingsForm({...settingsForm, gen_ed: Number(e.target.value)})}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">社會實踐</label>
              <input 
                type="number" 
                min="0"
                value={settingsForm.social}
                onChange={(e) => setSettingsForm({...settingsForm, social: Number(e.target.value)})}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>

            <div className="col-span-2">
              <label className="block text-sm font-medium text-slate-700 mb-1">體育 (學期數)</label>
              <input 
                type="number" 
                min="0"
                value={settingsForm.pe_semesters}
                onChange={(e) => setSettingsForm({...settingsForm, pe_semesters: Number(e.target.value)})}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>
          </div>

          <div className="border-t border-slate-100 pt-4">
            <h4 className="text-sm font-semibold text-slate-600 mb-3">系所課程門檻</h4>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">本系必修</label>
                <input
                  type="number"
                  min="0"
                  value={settingsForm.home_compulsory}
                  onChange={(e) => setSettingsForm({...settingsForm, home_compulsory: Number(e.target.value)})}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">本系選修</label>
                <input
                  type="number"
                  min="0"
                  value={settingsForm.home_elective}
                  onChange={(e) => setSettingsForm({...settingsForm, home_elective: Number(e.target.value)})}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">雙主修</label>
                <input
                  type="number"
                  min="0"
                  value={settingsForm.double_major}
                  onChange={(e) => setSettingsForm({...settingsForm, double_major: Number(e.target.value)})}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">輔修</label>
                <input
                  type="number"
                  min="0"
                  value={settingsForm.minor}
                  onChange={(e) => setSettingsForm({...settingsForm, minor: Number(e.target.value)})}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                />
              </div>
            </div>
          </div>

          <div className="pt-2">
            <button 
              type="submit"
              className="w-full py-2.5 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors shadow-sm"
            >
              儲存設定
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
