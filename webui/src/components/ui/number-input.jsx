import * as React from "react";
import { Plus, Minus } from "lucide-react";
import { cn } from "./utils";

const NumberInput = React.forwardRef(({ 
  className, 
  label,
  value = 0,
  onChange,
  step = 1,
  min = 0,
  max,
  disabled = false,
  id,
  ...props 
}, ref) => {
  const inputId = id || React.useId();
  
  const handleIncrement = () => {
    const newValue = Math.min(max !== undefined ? max : Infinity, value + step);
    onChange?.(newValue);
  };

  const handleDecrement = () => {
    const newValue = Math.max(min, value - step);
    onChange?.(newValue);
  };

  const handleInputChange = (e) => {
    const newValue = parseFloat(e.target.value);
    if (!isNaN(newValue)) {
      const clampedValue = Math.max(
        min, 
        max !== undefined ? Math.min(max, newValue) : newValue
      );
      onChange?.(clampedValue);
    }
  };

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {label && (
        <label 
          htmlFor={inputId}
          className="text-sm font-medium text-foreground"
        >
          {label}
        </label>
      )}
      <div className="relative bg-gray-100 rounded-sm flex h-12 w-full">
        {/* Decrement button */}
        <button
          type="button"
          onClick={handleDecrement}
          disabled={disabled || value <= min}
          className={cn(
            "flex h-12 w-12 items-center justify-center rounded-l-sm border border-r-0 text-muted-foreground transition-colors",
            "hover:bg-accent hover:text-accent-foreground",
            "focus-visible:z-10 focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] focus-visible:outline-none",
            "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
            "border-input"
          )}
          aria-label="Decrease value"
        >
          <Minus size={16} />
        </button>

        {/* Input field */}
        <input
          ref={ref}
          id={inputId}
          type="number"
          value={value}
          onChange={handleInputChange}
          step={step}
          min={min}
          max={max}
          disabled={disabled}
          className={cn(
            "flex h-12 w-full border-y border-input px-3 py-1 text-center text-base transition-[color,box-shadow]",
            "placeholder:text-muted-foreground selection:bg-primary selection:text-primary-foreground",
            "focus-visible:z-10 focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] focus-visible:outline-none",
            "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
            "aria-invalid:border-destructive aria-invalid:ring-destructive/20",
            "md:text-sm",
            // Remove default number input arrows
            "[appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
          )}
          {...props}
        />

        {/* Increment button */}
        <button
          type="button"
          onClick={handleIncrement}
          disabled={disabled || (max !== undefined && value >= max)}
          className={cn(
            "flex h-12 w-12 items-center justify-center rounded-r-sm border border-l-0 text-muted-foreground transition-colors",
            "hover:bg-accent hover:text-accent-foreground",
            "focus-visible:z-10 focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] focus-visible:outline-none",
            "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
            "border-input"
          )}
          aria-label="Increase value"
        >
          <Plus size={16} />
        </button>
      </div>
    </div>
  );
});

NumberInput.displayName = "NumberInput";

export { NumberInput };