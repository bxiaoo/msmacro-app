import { NumberInput } from "../ui/number-input";
import { Input } from "../ui/input";

export function PlaySettingsModal({ isOpen, onClose, settings, onSettingsChange }) {
  if (!isOpen) return null;

  const updateSetting = (key, value) => {
    onSettingsChange({
      ...settings,
      [key]: value
    });
  };

  const updateIgnoreKey = (index, value) => {
    const newIgnoreKeys = [...(settings.ignore_keys || ['', '', ''])];
    newIgnoreKeys[index] = value;
    updateSetting('ignore_keys', newIgnoreKeys);
  };

  return (
    <div className="bg-white relative rounded-tl-[8px] rounded-tr-[8px] shrink-0 w-full flex flex-col border border-gray-200" data-name="setting">
      <div className="relative flex-1 min-h-0">
        <div className="flex flex-col gap-4 px-4 w-full h-full max-h-[60vh] min-h-[240px] overflow-y-auto">
          <h2 className="text-lg font-semibold pt-4 z-20 text-foreground sticky top-0 bg-white pb-2 border-b border-gray-100">
            Rotation Settings
          </h2>
          <div className="space-y-4 w-full pb-4">
            <NumberInput
              label="Speed"
              value={settings.speed}
              onChange={(value) => updateSetting('speed', value)}
              step={1}
              min={1}
              className="w-48"
            />
            <div className="flex gap-4 w-full">
              <NumberInput
                label="Jitter time"
                value={settings.jitter_time}
                onChange={(value) => updateSetting('jitter_time', value)}
                step={0.1}
                min={0}
              />
              <NumberInput
                label="Jitter hold"
                value={settings.jitter_hold}
                onChange={(value) => updateSetting('jitter_hold', value)}
                step={0.001}
                min={0}
              />
            </div>
            <NumberInput
              label="Loop"
              value={settings.loop}
              onChange={(value) => updateSetting('loop', value)}
              step={1}
              min={1}
              className="w-48"
            />

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Jump Key
              </label>
              <Input
                placeholder="e.g., SPACE, Q, UP"
                value={settings.jump_key || 'SPACE'}
                onChange={(e) => updateSetting('jump_key', e.target.value)}
                className="w-48 bg-gray-100"
                autoComplete="off"
                data-form-type="other"
              />
              <p className="text-xs text-muted-foreground leading-tight">
                Key alias for jumping actions. Examples: SPACE, Q, ALT, UP
              </p>
            </div>

            {/* Randomization Settings */}
            <div className="space-y-3 pt-3 border-t border-gray-200">
              <h3 className="text-md font-medium text-foreground">
                Keystroke Randomization
              </h3>
              
              <NumberInput
                label="Ignore Tolerance"
                value={settings.ignore_tolerance || 0.1}
                onChange={(value) => updateSetting('ignore_tolerance', value)}
                step={0.05}
                min={0}
                max={1}
                className="w-48"
              />
              
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Keys to Ignore (up to 3)
                </label>
                <div className="flex gap-2">
                  {[0, 1, 2].map((index) => (
                    <Input
                      key={index}
                      placeholder={`Key ${index + 1}`}
                      value={(settings.ignore_keys || ['', '', ''])[index]}
                      onChange={(e) => updateIgnoreKey(index, e.target.value)}
                      className="w-full bg-gray-100 text-sm"
                    />
                  ))}
                </div>
                <p className="text-xs text-muted-foreground leading-tight">
                  Examples: 'a', 'space', 'enter', 'ctrl', 'shift'
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}