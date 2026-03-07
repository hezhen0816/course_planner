import React, { useState } from 'react';
import { Plus, Edit2, Trash2, Info, ArrowUp, ArrowDown, ListFilter, MoreHorizontal } from 'lucide-react';
import type { AppData, Course, CourseCategory } from '../types';
import { CATEGORY_LABELS, PROGRAM_LABELS } from '../constants';

interface SemesterGridProps {
  data: AppData;
  onEdit: (semesterId: string, course: Course) => void;
  onDelete: (semesterId: string, courseId: string) => void;
  onAdd: (semesterId: string) => void;
  onOpenDetail: (semesterId: string, course: Course) => void;
  onMoveCourse: (semesterId: string, courseId: string, direction: 'up' | 'down') => void;
  onSortByCategory: (semesterId: string) => void;
}

export const SemesterGrid: React.FC<SemesterGridProps> = ({
  data,
  onEdit,
  onDelete,
  onAdd,
  onOpenDetail,
  onMoveCourse,
  onSortByCategory
}) => {
  const [openActionMenuId, setOpenActionMenuId] = useState<string | null>(null);
  
  const getCategoryColor = (cat: CourseCategory) => {
    switch (cat) {
      case 'compulsory': return 'bg-red-100 text-red-800 border-red-200';
      case 'elective': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'gen_ed': return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'pe': return 'bg-green-100 text-green-800 border-green-200';
      case 'chinese': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'english': return 'bg-indigo-100 text-indigo-800 border-indigo-200';
      case 'social': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'unclassified': return 'bg-gray-200 text-gray-800 border-gray-400 border-dashed';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  return (
    <div className="lg:col-span-9">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {data.semesters.map((semester) => {
          const semesterCredits = semester.courses.reduce((acc, c) => c.category === 'pe' ? acc : acc + c.credits, 0);
          
          return (
            <div key={semester.id} className="bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col h-full">
              {/* Semester Header */}
              <div className="px-5 py-3 border-b border-slate-100 bg-slate-50 rounded-t-xl flex justify-between items-center">
                <h3 className="font-bold text-slate-700">{semester.name}</h3>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => onSortByCategory(semester.id)}
                    className="text-xs font-medium bg-white px-2 py-1 rounded border border-slate-200 text-slate-600 hover:text-blue-600 hover:border-blue-200 transition-colors flex items-center gap-1"
                    title="依課程類型自動排序"
                  >
                    <ListFilter className="h-3 w-3" />
                    類型排序
                  </button>
                  <span className="text-xs font-medium bg-white px-2 py-1 rounded border border-slate-200 text-slate-500">
                    {semesterCredits} 學分
                  </span>
                </div>
              </div>

              {/* Course List */}
              <div className="p-4 flex-grow space-y-2 min-h-[120px]">
                {semester.courses.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-slate-300 text-sm italic py-4">
                      尚未安排課程
                  </div>
                ) : (
                  semester.courses.map((course, index) => (
                    <div 
                      key={course.id} 
                      className={`group relative p-3 rounded-lg border flex justify-between items-center transition-all hover:shadow-md ${getCategoryColor(course.category)}`}
                    >
                      <div className="flex-1 min-w-0 mr-2">
                        <div className="flex items-center">
                          <h4 className="font-semibold text-sm truncate">{course.name}</h4>
                        </div>
                        <div className="flex items-center mt-1 space-x-2">
                          <span className="text-xs opacity-75 px-1.5 py-0.5 rounded bg-black/5">
                            {course.category === 'pe' ? '0 學分' : `${course.credits} 學分`}
                          </span>
                          <span className="text-xs opacity-75">
                            {CATEGORY_LABELS[course.category]}
                          </span>
                          {course.program && course.program !== 'home' && (
                            <span className="text-xs font-medium bg-white/50 px-1.5 py-0.5 rounded">
                              {PROGRAM_LABELS[course.program]}
                            </span>
                          )}
                          {course.category === 'gen_ed' && course.dimension && course.dimension !== 'None' && (
                            <span className="text-xs font-bold bg-white/40 px-1 rounded">
                              {course.dimension}
                            </span>
                          )}
                        </div>
                      </div>
                      
                      {/* Actions */}
                      <div className="relative flex space-x-1 opacity-100">
                        <button
                          onClick={() => onMoveCourse(semester.id, course.id, 'up')}
                          disabled={index === 0}
                          className="p-1.5 rounded-full hover:bg-black/10 text-slate-700 disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed"
                          title="上移"
                        >
                          <ArrowUp className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => onMoveCourse(semester.id, course.id, 'down')}
                          disabled={index === semester.courses.length - 1}
                          className="p-1.5 rounded-full hover:bg-black/10 text-slate-700 disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed"
                          title="下移"
                        >
                          <ArrowDown className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => setOpenActionMenuId(prev => (prev === course.id ? null : course.id))}
                          className="p-1.5 rounded-full hover:bg-black/10 text-slate-700"
                          title="更多操作"
                        >
                          <MoreHorizontal className="h-3.5 w-3.5" />
                        </button>

                        {openActionMenuId === course.id && (
                          <div className="absolute right-0 top-9 z-20 w-36 bg-white border border-slate-200 rounded-lg shadow-lg py-1">
                            <button
                              onClick={() => {
                                onOpenDetail(semester.id, course);
                                setOpenActionMenuId(null);
                              }}
                              className="w-full px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                            >
                              <Info className="h-3.5 w-3.5" />
                              詳細資訊
                            </button>
                            <button
                              onClick={() => {
                                onEdit(semester.id, course);
                                setOpenActionMenuId(null);
                              }}
                              className="w-full px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                            >
                              <Edit2 className="h-3.5 w-3.5" />
                              編輯
                            </button>
                            <button
                              onClick={() => {
                                onDelete(semester.id, course.id);
                                setOpenActionMenuId(null);
                              }}
                              className="w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                              刪除
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Add Button */}
              <div className="p-3 border-t border-slate-100">
                <button 
                  onClick={() => onAdd(semester.id)}
                  className="w-full py-2 rounded-lg border border-dashed border-slate-300 text-slate-500 text-sm hover:bg-slate-50 hover:text-blue-600 hover:border-blue-300 transition-colors flex items-center justify-center"
                >
                  <Plus className="h-4 w-4 mr-1" /> 新增課程
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
