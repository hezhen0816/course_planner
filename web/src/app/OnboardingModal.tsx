import React, { useState } from 'react';
import { X, Upload, Calculator, LayoutDashboard, ChevronRight, ChevronLeft, Check } from 'lucide-react';

interface OnboardingModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const OnboardingModal: React.FC<OnboardingModalProps> = ({ isOpen, onClose }) => {
  const [currentStep, setCurrentStep] = useState(0);

  if (!isOpen) return null;

  const steps = [
    {
      title: "歡迎使用修課羅盤",
      description: "這是一個幫助你規劃大學修課路徑的工具。透過視覺化介面，你可以輕鬆管理未來的課程安排。",
      icon: <LayoutDashboard className="w-16 h-16 text-blue-500" />,
      color: "bg-blue-50"
    },
    {
      title: "快速匯入課程",
      description: "使用「匯入成績」功能，上傳從學校系統下載的 HTML 檔案，工具會自動解析並填入你已修習的課程。",
      icon: <Upload className="w-16 h-16 text-green-500" />,
      color: "bg-green-50"
    },
    {
      title: "靈活管理課程",
      description: "你可以手動新增、編輯、刪除課程，調整課程類別與學分，讓規劃更符合自己的需求。",
      icon: <Calculator className="w-16 h-16 text-purple-500" />,
      color: "bg-purple-50"
    },
    {
      title: "畢業門檻追蹤",
      description: "側邊欄會即時顯示你的學分統計與各項畢業門檻進度，幫助你掌握修課狀況。",
      icon: <div className="text-5xl font-bold text-orange-500">133</div>,
      color: "bg-orange-50"
    }
  ];

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(prev => prev + 1);
    } else {
      onClose();
    }
  };

  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep(prev => prev - 1);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden flex flex-col relative animate-in fade-in zoom-in duration-200">
        
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-full hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors z-10"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Content */}
        <div className="p-8 flex flex-col items-center text-center pt-12">
          <div className={`w-32 h-32 rounded-full flex items-center justify-center mb-6 ${steps[currentStep].color}`}>
            {steps[currentStep].icon}
          </div>
          
          <h2 className="text-2xl font-bold text-slate-800 mb-3">
            {steps[currentStep].title}
          </h2>
          
          <p className="text-slate-500 leading-relaxed mb-8">
            {steps[currentStep].description}
          </p>

          {/* Dots Indicator */}
          <div className="flex space-x-2 mb-8">
            {steps.map((_, index) => (
              <div 
                key={index}
                className={`w-2 h-2 rounded-full transition-all duration-300 ${
                  index === currentStep ? 'w-6 bg-blue-600' : 'bg-slate-200'
                }`}
              />
            ))}
          </div>
        </div>

        {/* Footer Buttons */}
        <div className="p-4 border-t bg-slate-50 flex justify-between items-center">
          <button
            onClick={handlePrev}
            disabled={currentStep === 0}
            className={`flex items-center px-4 py-2 text-slate-600 font-medium rounded-lg hover:bg-slate-200 transition-colors ${
              currentStep === 0 ? 'opacity-0 pointer-events-none' : ''
            }`}
          >
            <ChevronLeft className="w-4 h-4 mr-1" /> 上一步
          </button>

          <button
            onClick={handleNext}
            className={`flex items-center px-6 py-2.5 rounded-lg font-bold text-white shadow-lg shadow-blue-500/20 transition-all transform active:scale-95 ${
              currentStep === steps.length - 1 
                ? 'bg-slate-900 hover:bg-slate-800' 
                : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            {currentStep === steps.length - 1 ? (
              <>開始使用 <Check className="w-4 h-4 ml-2" /></>
            ) : (
              <>下一步 <ChevronRight className="w-4 h-4 ml-2" /></>
            )}
          </button>
        </div>

      </div>
    </div>
  );
};
