import { useState, useEffect } from "react";
import { Settings2, Bug, Trash2, Cpu, HardDrive } from "lucide-react";
import { ActionButton } from "./ui/action-button";
import { clsx } from "clsx";
import { getSystemStats } from "../api";

function LiveSymbol({active = false}) {
    return (
        <div className={'relative w-4 aspect-square flex m-auto'}>
            <span className={clsx('rounded-full w-4 aspect-square absolute m-auto', active ? 'bg-emerald-400 animate-ping' : 'bg-gray-200')}></span>
        
            <span className={clsx('rounded-full w-4 aspect-square absolute m-auto', active ? 'bg-emerald-500' : 'bg-gray-400')}></span>
        </div>
    )
}

function AppTitle({active = false}) {
  return (
    <div className="content-stretch flex flex-col items-start justify-center leading-[0] relative shrink-0 text-nowrap">
      <div className="font-['Roboto:Black',_sans-serif] font-black relative shrink-0 text-[32px] text-gray-900" style={{ fontVariationSettings: "'wdth' 100" }}>
        <p className="leading-[normal] text-nowrap whitespace-pre">MS Macro</p>
      </div>
      <div className={clsx("font-['Roboto:Medium',_sans-serif] font-medium relative shrink-0 text-[14px]", active ? "text-emerald-600" : "text-gray-400")} style={{ fontVariationSettings: "'wdth' 100" }}>
          <SystemStats />
      </div>
    </div>
  );
}



function SystemStats() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const data = await getSystemStats();
        setStats(data);
      } catch (err) {
        console.error("Failed to fetch system stats:", err);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 3000);
    return () => clearInterval(interval);
  }, []);

  if (!stats) return null;

  const getCPUColor = (percent) => {
    if (percent >= 80) return "text-red-600";
    if (percent >= 60) return "text-yellow-600";
    return "text-green-600";
  };

  const getMemColor = (percent) => {
    if (percent >= 85) return "text-red-600";
    if (percent >= 70) return "text-yellow-600";
    return "text-green-600";
  };

  return (
    <div className="flex items-center gap-3 text-xs text-gray-600">
      {/* CPU */}
      <div className="flex items-center gap-1">
        <Cpu size={14} className={getCPUColor(stats.cpu_percent)} />
        <span className={clsx("font-mono font-medium", getCPUColor(stats.cpu_percent))}>
          {stats.cpu_percent}%
        </span>
      </div>

      {/* RAM */}
      <div className="flex items-center gap-1">
        <HardDrive size={14} className={getMemColor(stats.memory_percent)} />
        <span className={clsx("font-mono font-medium", getMemColor(stats.memory_percent))}>
          {stats.memory_percent}%
        </span>
      </div>

      {/* Temperature (Pi only) */}
      {stats.temperature && (
        <div className="flex items-center gap-1">
          <span className={clsx(
            "font-mono font-medium",
            stats.temperature >= 70 ? "text-red-600" :
            stats.temperature >= 60 ? "text-yellow-600" :
            "text-green-600"
          )}>
            {stats.temperature}°C
          </span>
        </div>
      )}
    </div>
  );
}

export function Header({
    isActive = false,
  onSettingsClick,
  onDebugClick,
  onDeleteSelected,
  hasSelectedFiles = false,
  isSettingsActive = false,
  isDebugActive = false
}) {
  return (
    <div className="bg-gray-100 content-stretch flex items-center justify-between pb-0 pt-11 px-4 relative shrink-0 w-full">
      <div className="content-stretch flex gap-3 items-center justify-start relative shrink-0">
        <LiveSymbol active={isActive} />
        <AppTitle active={isActive} />
      </div>
      <div className="content-stretch flex gap-4 items-center justify-end relative shrink-0">
        <div className="content-stretch flex gap-1 items-center justify-start relative shrink-0">
          <ActionButton
            Icon={Trash2}
            onClick={onDeleteSelected}
            active={false}
            disabled={!hasSelectedFiles}
          />
          <ActionButton
            Icon={Settings2}
            onClick={onSettingsClick}
            active={isSettingsActive}
          />
          <ActionButton
            Icon={Bug}
            onClick={onDebugClick}
            active={isDebugActive}
          />
        </div>
      </div>
    </div>
  );
}