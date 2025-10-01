import * as React from "react";
import { cn } from "./utils";

const Switch = React.forwardRef(({
  className,
  checked = false,
  onCheckedChange,
  disabled = false,
  id,
  'aria-label': ariaLabel,
  ...props
}, ref) => {
  const switchId = id || React.useId();

  const handleToggle = () => {
    if (!disabled) {
      onCheckedChange?.(!checked);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      handleToggle();
    }
  };

  return (
    <button
      ref={ref}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      id={switchId}
      onClick={handleToggle}
      onKeyDown={handleKeyDown}
      disabled={disabled}
      className={cn(
        "box-border content-stretch flex gap-[10px] h-[28px] items-center justify-end overflow-clip p-[2px] relative rounded-[999px] shrink-0 w-[44px] cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        checked ? 'bg-gray-900' : 'bg-gray-400',
        disabled && 'opacity-50 cursor-not-allowed',
        className
      )}
      {...props}
    >
      <div
        className={cn(
          "aspect-[32/32] bg-white h-full rounded-[999px] shrink-0 transition-transform",
          checked ? "translate-x-0" : "-translate-x-4"
        )}
      />
    </button>
  );
});

Switch.displayName = "Switch";

export { Switch };