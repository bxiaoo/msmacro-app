import { Settings2, Bug, Trash2 } from "lucide-react";
import { ActionButton } from "./ui/action-button";
import { clsx } from "clsx";

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
        <p className="leading-[normal] text-nowrap whitespace-pre">{active ? 'Online' : 'Offline'}</p>
      </div>
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
  );
}