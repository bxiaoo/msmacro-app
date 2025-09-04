import * as React from 'react'

export function ActionButton({ 
  Icon, 
  onClick, 
  active = false,
  disabled = false
}) {
  return (
    <button 
      onClick={onClick}
      className={`box-border content-stretch flex gap-[5px] items-center justify-start p-[9px] relative rounded-[4px] shrink-0 transition-colors ${
        (active && !disabled)
          ? 'bg-blue-100 hover:bg-blue-200' 
          : ''
      } ${disabled ? '' : 'hover:bg-white'}
      `}
    >
      <div className="relative shrink-0 size-[26px] flex items-center justify-center">
        <Icon size={20} className={`${(active && !disabled) ? 'text-blue-600' : 'text-gray-900'}`} />
      </div>
    </button>
  );
}