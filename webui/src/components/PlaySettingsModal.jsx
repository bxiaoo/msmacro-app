import { NumberInput } from "./ui/number-input";
import { Input } from "./ui/input";

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
    <div className="bg-white relative rounded-tl-[8px] rounded-tr-[8px] shrink-0 w-full" data-name="setting">
      <div className="relative size-full">
        <div className="flex flex-col gap-6 px-6 py-6 w-full">
          <h2 className="text-lg font-semibold text-foreground">
            Play Settings
          </h2>
          <div className="space-y-4 w-full">
            <NumberInput
              label="Speed"
              value={settings.speed}
              onChange={(value) => updateSetting('speed', value)}
              step={1}
              min={1}
              className="w-48"
            />
            <div className="grid grid-cols-2 gap-4 w-full">
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
            
            {/* Randomization Settings */}
            <div className="space-y-4 pt-4 border-t border-gray-200">
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
              
              <div className="space-y-3">
                <label className="text-sm font-medium text-foreground">
                  Keys to Ignore (up to 3)
                </label>
                <div className="flex gap-1">
                  {[0, 1, 2].map((index) => (
                    <div key={index} className="flex items-center gap-2">
                      <Input
                        placeholder="e.g., 'a', 'space', 'ctrl'"
                        value={(settings.ignore_keys || ['', '', ''])[index]}
                        onChange={(e) => updateIgnoreKey(index, e.target.value)}
                        className="w-full bg-gray-100"
                      />
                    </div>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">
                  Enter key names like 'a', 'space', 'enter', 'ctrl', 'shift', etc.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}