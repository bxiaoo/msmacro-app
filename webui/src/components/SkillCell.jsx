import { ChevronDown, Edit, Trash2 } from 'lucide-react'
import { Switch } from './ui/switch'
import { NumberInput } from './ui/number-input'
import { Input } from './ui/input'
import { Checkbox } from './ui/checkbox'

function KeyInput({ label, placeholder = "Keystroke", value, onChange, disabled = false }) {
  return (
    <div className="basis-0 h-18 content-stretch flex flex-col gap-[8px] grow items-start min-h-px min-w-px relative shrink-0">
      <p className={`font-['Roboto:Regular',_sans-serif] font-normal leading-[normal] relative shrink-0 text-[14px] w-full ${
        disabled ? 'text-gray-400' : 'text-gray-900'
      }`} style={{ fontVariationSettings: "'wdth' 100" }}>
        {label}
      </p>
      <Input
        type="text"
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className={`basis-0 font-['Roboto:Regular',_sans-serif] font-normal grow leading-[normal] min-h-px min-w-px relative shrink-0 text-[16px] bg-gray-100 border-none outline-none ${
          disabled ? 'text-gray-600' : 'text-gray-600'
        }`}
        style={{ fontVariationSettings: "'wdth' 100" }}
      />
    </div>
  )
}

export function SkillCell({
  skillName = "Skill #1",
  variant = "cd skill", // "cd skill" or "buff"
  isOpen = false,
  isEnabled = true,
  isSelected = false,
  onToggleSelect,
  onToggleExpand,
  onEdit,
  onDelete,
  // CD Skill specific props
  keyReplacement = false,
  onKeyReplacementChange,
  replaceRate = 0.7,
  onReplaceRateChange,
  frozenRotationDuringCasting = false,
  onFrozenRotationDuringCastingChange,
  // Buff specific props
  frozenRotation = false,
  onFrozenRotationChange,
  beforeCastingSeconds = 0.45,
  onBeforeCastingSecondsChange,
  afterCastingSeconds = 0.45,
  onAfterCastingSecondsChange
}) {
  return (
    <div className={`bg-gray-200 box-border content-stretch flex flex-col gap-[12px] items-center relative rounded-[4px] shrink-0 w-full ${
      isOpen ? 'pb-[12px] pt-0 px-0' : ''
    }`}>
      {/* Header */}
      <div className="box-border content-stretch flex items-center justify-between p-[6px] relative rounded-[4px] shrink-0 w-full">
        <Checkbox
          checked={isSelected}
          onChange={onToggleSelect}
          className="box-border content-stretch flex gap-[10px] items-center overflow-clip p-[10px] relative shrink-0"
        />
        <div className="basis-0 content-stretch flex gap-[4px] grow items-center min-h-px min-w-px relative shrink-0">
          <div className="content-stretch flex gap-[10px] items-center justify-center relative shrink-0">
            <p className="font-['Roboto:Bold',_sans-serif] font-bold leading-[normal] relative shrink-0 text-[16px] text-gray-900 text-nowrap whitespace-pre" style={{ fontVariationSettings: "'wdth' 100" }}>
              {skillName}
            </p>
          </div>
          <div
            className="overflow-clip relative shrink-0 size-[20px] cursor-pointer"
            onClick={onToggleExpand}
          >
            <ChevronDown
              size={20}
              className={`text-gray-900 transition-transform ${isOpen ? 'rotate-180' : ''}`}
            />
          </div>
        </div>
        <div className="box-border content-stretch flex gap-[10px] items-center p-[10px] relative shrink-0">
          <div className="overflow-clip relative shrink-0 size-[20px] cursor-pointer" onClick={onEdit}>
            <Edit size={20} className="text-gray-900" />
          </div>
        </div>
        <div className="box-border content-stretch flex gap-[10px] items-center p-[10px] relative shrink-0">
          <div className="overflow-clip relative shrink-0 size-[20px] cursor-pointer" onClick={onDelete}>
            <Trash2 size={20} className="text-gray-900" />
          </div>
        </div>
      </div>

      {/* Expanded Content */}
      {isOpen && (
        <div className="box-border content-stretch flex flex-col gap-[10px] items-start px-[12px] py-0 relative shrink-0 w-full">
          <div className="bg-white box-border content-stretch flex flex-col gap-[16px] items-start p-[12px] relative rounded-[4px] shadow-[0px_1px_3px_0px_rgba(0,0,0,0.1),0px_1px_2px_0px_rgba(0,0,0,0.06)] shrink-0 w-full">

            {variant === "cd skill" && (
              <>
                {/* Key replacement toggle */}
                <div className="content-stretch flex gap-[12px] items-center relative shrink-0">
                  <Switch
                    checked={keyReplacement}
                    onCheckedChange={onKeyReplacementChange}
                    disabled={!isEnabled}
                  />
                  <p className={`font-['Roboto:Regular',_sans-serif] font-normal leading-[normal] relative shrink-0 text-[16px] text-nowrap whitespace-pre ${
                    isEnabled ? 'text-gray-900' : 'text-gray-400'
                  }`} style={{ fontVariationSettings: "'wdth' 100" }}>
                    Key replacement
                  </p>
                </div>

                {/* Replace rate */}
                <NumberInput
                  label="Replace rate"
                  value={replaceRate}
                  onChange={onReplaceRateChange}
                  disabled={!isEnabled}
                  min={0}
                  max={1}
                  step={0.1}
                />
              </>
            )}

            {variant === "buff" && (
              <>
                {/* Frozen rotation toggle */}
                <div className="content-stretch flex gap-[12px] items-center relative shrink-0">
                  <Switch
                    checked={frozenRotation}
                    onCheckedChange={onFrozenRotationChange}
                    disabled={!isEnabled}
                  />
                  <p className={`font-['Roboto:Regular',_sans-serif] font-normal leading-[normal] relative shrink-0 text-[16px] text-nowrap whitespace-pre ${
                    isEnabled ? 'text-gray-900' : 'text-gray-400'
                  }`} style={{ fontVariationSettings: "'wdth' 100" }}>
                    Frozen rotation
                  </p>
                </div>

                {/* Before casting seconds */}
                <NumberInput
                  label="Before casting (seconds)"
                  value={beforeCastingSeconds}
                  onChange={onBeforeCastingSecondsChange}
                  disabled={!isEnabled}
                />

                {/* After casting seconds */}
                <NumberInput
                  label="After casting (seconds)"
                  value={afterCastingSeconds}
                  onChange={onAfterCastingSecondsChange}
                  disabled={!isEnabled}
                />
              </>
            )}
          </div>

          {/* Frozen rotation during casting (for CD skills) */}
          {variant === "cd skill" && (
            <div className="box-border content-stretch flex gap-[12px] items-center px-[12px] py-0 relative shrink-0 w-full">
              <Switch
                checked={frozenRotationDuringCasting}
                onCheckedChange={onFrozenRotationDuringCastingChange}
                disabled={!isEnabled}
              />
              <p className={`font-['Roboto:Regular',_sans-serif] font-normal leading-[normal] relative shrink-0 text-[16px] text-nowrap whitespace-pre ${
                isEnabled ? 'text-gray-900' : 'text-gray-400'
              }`} style={{ fontVariationSettings: "'wdth' 100" }}>
                Frozen rotation during casting
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

