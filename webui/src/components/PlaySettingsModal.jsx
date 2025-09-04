import { NumberInput } from "./ui/number-input";

export function PlaySettingsModal({ isOpen, onClose, settings, onSettingsChange }) {
  if (!isOpen) return null;

  const updateSetting = (key, value) => {
    onSettingsChange({
      ...settings,
      [key]: value
    });
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
          </div>
        </div>
      </div>
    </div>
  );
}