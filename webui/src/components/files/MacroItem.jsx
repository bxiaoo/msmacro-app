import * as React from 'react'
import {FileEdit, FolderEdit, Trash2, ChevronDown, Check} from 'lucide-react'
import { ActionButton } from '../ui/action-button';

const Checkbox = React.memo(function Checkbox({ checked, indeterminate, onChange }) {
  return (
    <button 
      onClick={() => onChange?.(!checked)}
      className="box-border content-stretch flex gap-2.5 items-center justify-start overflow-clip p-[10px] relative shrink-0"
    >
      <div className={`relative rounded-[4px] shrink-0 size-5 ${checked || indeterminate ? 'bg-gray-900' : 'bg-white'}`}>
        {!checked && !indeterminate && (
          <div aria-hidden="true" className="absolute border-2 border-gray-900 border-solid inset-0 pointer-events-none rounded-[4px]" />
        )}
        {checked && !indeterminate && (
          <div className="absolute left-1/2 size-3.5 top-1/2 translate-x-[-50%] translate-y-[-50%] flex items-center justify-center">
            <Check size={14} className="text-white" />
          </div>
        )}
        {indeterminate && (
          <div className="absolute left-1/2 top-1/2 translate-x-[-50%] translate-y-[-50%] w-2.5 h-0.5 bg-white rounded-sm" />
        )}
      </div>
    </button>
  );
})

const FolderName = React.memo(function FolderName({ name, isExpanded, onToggle }) {
  return (
    <button 
      onClick={onToggle}
      className="basis-0 content-stretch flex gap-1 grow items-center justify-start min-h-px min-w-px relative shrink-0"
    >
      <div className="content-stretch flex gap-2.5 items-center justify-center relative shrink-0">
        <div className="font-['Roboto:Bold',_sans-serif] font-bold leading-[0] relative shrink-0 text-[16px] text-black text-nowrap" style={{ fontVariationSettings: "'wdth' 100" }}>
          <p className="leading-[normal] whitespace-pre">{name}</p>
        </div>
      </div>
      <div className={`relative shrink-0 size-5 transition-transform flex items-center justify-center ${isExpanded ? 'rotate-180' : ''}`}>
        <ChevronDown size={16} className="text-gray-600" />
      </div>
    </button>
  );
})

const FileName = React.memo(function FileName({ name }) {
  return (
    <div className="basis-0 content-stretch flex gap-2.5 grow items-center justify-start min-h-px min-w-px relative shrink-0">
      <div className="font-['Roboto:Regular',_sans-serif] font-normal leading-[0] relative shrink-0 text-[16px] text-gray-900 text-nowrap" style={{ fontVariationSettings: "'wdth' 100" }}>
        <p className="leading-[normal] whitespace-pre">{name}</p>
      </div>
    </div>
  );
})

export const MacroItem = React.memo(function MacroItem({ 
  name, 
  type = 'file',
  checked, 
  indeterminate,
  isExpanded,
  onCheckChange, 
  onToggleExpand,
  onEdit, 
  onDelete 
}) {
  return (
    <div className="relative rounded-[4px] shrink-0 w-full">
      <div className="flex flex-row items-center relative size-full">
        <div className="box-border content-stretch flex items-center justify-between p-[6px] relative w-full">
          <Checkbox 
            checked={checked} 
            indeterminate={indeterminate} 
            onChange={onCheckChange} 
          />
          {type === 'folder' ? (
            <FolderName 
              name={name} 
              isExpanded={isExpanded}
              onToggle={onToggleExpand}
            />
          ) : (
            <FileName name={name} />
          )}
          <ActionButton Icon={type === 'file' ? FileEdit : FolderEdit} onClick={onEdit} />
          <ActionButton Icon={Trash2} onClick={onDelete} />
        </div>
      </div>
    </div>
  );
})