import * as React from 'react'
import { Check } from 'lucide-react'

export const Checkbox = React.memo(function Checkbox({
  checked,
  indeterminate,
  onChange,
  className = ""
}) {
  return (
    <button
      onClick={() => onChange?.(!checked)}
      className={`box-border content-stretch flex gap-2.5 items-center justify-start overflow-clip p-[10px] relative shrink-0 ${className}`}
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
