import React, { useState, useEffect } from 'react';
import { Info } from 'lucide-react';
import type { Course, CourseCategory, GenEdDimension, CourseProgram } from '../types';
import { CATEGORY_LABELS, GEN_ED_LABELS, PROGRAM_LABELS } from '../constants';

interface CourseModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (course: Course) => void;
  editingCourse: Course | null;
}

export const CourseModal: React.FC<CourseModalProps> = ({ isOpen, onClose, onSave, editingCourse }) => {
  const [formName, setFormName] = useState('');
  const [formCredits, setFormCredits] = useState(3);
  const [formCategory, setFormCategory] = useState<CourseCategory>('compulsory');
  const [formProgram, setFormProgram] = useState<CourseProgram>('home');
  const [formDimension, setFormDimension] = useState<GenEdDimension>('None');

  const supportsProgram = (category: CourseCategory) =>
    category === 'compulsory' || category === 'elective' || category === 'other' || category === 'unclassified';

  useEffect(() => {
    if (editingCourse) {
      setFormName(editingCourse.name);
      setFormCredits(editingCourse.credits);
      setFormCategory(editingCourse.category);
      setFormProgram(editingCourse.program || 'home');
      setFormDimension(editingCourse.dimension || 'None');
    } else {
      setFormName('');
      setFormCredits(3);
      setFormCategory('compulsory');
      setFormProgram('home');
      setFormDimension('None');
    }
  }, [editingCourse, isOpen]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newCourse: Course = {
      id: editingCourse ? editingCourse.id : Date.now().toString(),
      name: formName,
      credits: Number(formCredits),
      category: formCategory,
      program: supportsProgram(formCategory) ? formProgram : 'home',
      dimension: formCategory === 'gen_ed' ? formDimension : undefined
    };
    onSave(newCourse);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 bg-slate-50 flex justify-between items-center">
          <h3 className="text-lg font-bold text-slate-800">
            {editingCourse ? '編輯課程' : '新增課程'}
          </h3>
          <button 
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600"
          >
            ✕
          </button>
        </div>
        
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">課程名稱</label>
            <input 
              type="text" 
              required
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all"
              placeholder="例如：微積分(一)"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">學分數</label>
              <input 
                type="number" 
                min="0"
                step="0.5"
                value={formCredits}
                onChange={(e) => setFormCredits(Number(e.target.value))}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
              />
              {formCategory === 'pe' && <p className="text-xs text-gray-500 mt-1">體育課通常為 0 學分</p>}
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">類別</label>
              <select 
                value={formCategory}
                onChange={(e) => {
                  const nextCategory = e.target.value as CourseCategory;
                  setFormCategory(nextCategory);
                  if (nextCategory === 'pe') setFormCredits(0);
                  if (!supportsProgram(nextCategory)) setFormProgram('home');
                }}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none bg-white"
              >
                {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>
            </div>
          </div>

          {supportsProgram(formCategory) && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">課程歸屬</label>
              <select
                value={formProgram}
                onChange={(e) => setFormProgram(e.target.value as CourseProgram)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none bg-white"
              >
                {Object.entries(PROGRAM_LABELS).map(([key, label]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>
              <p className="text-xs text-slate-500 mt-1">
                用來區分本系、雙主修與輔修，不影響共同必修與通識統計。
              </p>
            </div>
          )}

          {formCategory === 'gen_ed' && (
            <div className="bg-purple-50 p-4 rounded-lg border border-purple-100">
              <label className="block text-sm font-medium text-purple-800 mb-1">通識向度</label>
              <select 
                value={formDimension}
                onChange={(e) => setFormDimension(e.target.value as GenEdDimension)}
                className="w-full px-3 py-2 border border-purple-200 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none bg-white"
              >
                {Object.entries(GEN_ED_LABELS).map(([key, label]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>
              <p className="text-xs text-purple-600 mt-2 flex items-start">
                <Info className="h-3 w-3 mr-1 mt-0.5 flex-shrink-0" />
                根據規定，A~F 六向度中，至少擇四向度，各修習一門課，請盡量選修不同向度的課程。
              </p>
            </div>
          )}

          <div className="pt-2">
            <button 
              type="submit"
              className="w-full py-2.5 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors shadow-sm active:scale-[0.98]"
            >
              {editingCourse ? '儲存變更' : '新增課程'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
