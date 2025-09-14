import { Disc3, Circle } from "lucide-react";
import { useEffect, useState } from "react";

export function StateMessage({
    isPlaying,
    isRecording,
    startTime,
    macroName,
    estimatedDuration = 60000
}) {
  const [playingTime, setPlayingTime] = useState('00:00:00')
  const [recordedTime, setRecordedTime] = useState('00:00:00')

  useEffect(() => {
    // Reset timers when states change
    if (!isPlaying && !isRecording) {
      setPlayingTime('00:00:00');
      setRecordedTime('00:00:00');
      return;
    }

    if (!startTime) return;
    
    // Update immediately to avoid delay
    const updateTime = () => {
      const elapsed = Date.now() - startTime;
      const hours = Math.floor(elapsed / 3600000);
      const minutes = Math.floor((elapsed % 3600000) / 60000);
      const seconds = Math.floor((elapsed % 60000) / 1000);
      
      const timeString = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
      
      if (isPlaying) {
        setPlayingTime(timeString);
      } else if (isRecording) {
        setRecordedTime(timeString);
      }
    };

    // Update immediately
    updateTime();
    
    // Then set interval for continuous updates
    const interval = setInterval(updateTime, 1000);

    return () => clearInterval(interval);
  }, [startTime, isPlaying, isRecording]);

  return (
    <div className="relative shrink-0 w-full" data-name="state msg">
      <div className="flex flex-row items-center relative size-full">
        {isPlaying && <div className="bg-emerald-100 box-border content-stretch flex gap-1 items-center justify-start p-3 relative w-full">
          <div className="relative shrink-0 size-[38px] flex items-center justify-center rounded-full">
            <Disc3 strokeWidth={1.2} size={44} className="text-emerald-700 animate-spin" />
          </div>
          <div className="basis-0 p-1 content-stretch flex flex-col gap-1 grow items-start justify-start leading-[0] min-h-px min-w-px relative shrink-0 text-nowrap">
            <div className="font-['Roboto:Bold',_sans-serif] font-bold min-w-full overflow-ellipsis overflow-hidden relative shrink-0 text-[0px]" style={{ width: "min-content", fontVariationSettings: "'wdth' 100" }}>
              <p className="[text-overflow:inherit] [text-wrap-mode:inherit] [white-space-collapse:inherit] font-['Roboto:Black',_sans-serif] font-black leading-[normal] overflow-inherit text-[18px]">
                <span className="text-emerald-700" style={{ fontVariationSettings: "'wdth' 100" }}>
                  Playing:
                </span>
                <span className="text-emerald-700" style={{ fontVariationSettings: "'wdth' 100" }}>{` ${macroName}`}</span>
              </p>
            </div>
            <div className="font-['Roboto:Medium',_sans-serif] font-medium relative shrink-0 text-[14px] text-emerald-700" style={{ fontVariationSettings: "'wdth' 100" }}>
              <p className="leading-[normal] text-nowrap whitespace-pre">Rotating time: {playingTime}</p>
            </div>
          </div>
        </div>}
        {
            isRecording && <div className="bg-blue-100 box-border content-stretch flex gap-2 items-center justify-start p-[8px] relative w-full">
          <div className="box-border content-stretch flex gap-2.5 items-center justify-start p-[5px] relative rounded-[999px] shrink-0">
            <div className="relative shrink-0 size-[23px] flex items-center justify-center">
              <Circle size={20} className="text-blue-600 fill-current z-10" />
                <span className='absolute bg-blue-400/90 rounded-full size-4 animate-ping'></span>
            </div>
          </div>
          <div className="basis-0 p-1 content-stretch flex flex-col gap-1 grow items-start justify-start leading-[0] min-h-px min-w-px relative shrink-0 text-blue-700 text-nowrap">
            <div className="font-['Roboto:Black',_sans-serif] font-black min-w-full overflow-ellipsis overflow-hidden relative shrink-0 text-[18px]" style={{ width: "min-content", fontVariationSettings: "'wdth' 100" }}>
              <p className="[text-overflow:inherit] [text-wrap-mode:inherit] [white-space-collapse:inherit] leading-[normal] overflow-inherit">Recording...</p>
            </div>
            <div className="font-['Roboto:Medium',_sans-serif] font-medium relative shrink-0 text-[14px]" style={{ fontVariationSettings: "'wdth' 100" }}>
              <p className="leading-[normal] text-nowrap whitespace-pre">Recorded time: {recordedTime}</p>
            </div>
          </div>
        </div>
        }
      </div>
    </div>
  );
}