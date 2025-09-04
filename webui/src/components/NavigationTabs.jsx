import { Bot, Keyboard} from 'lucide-react'

function TabItem({
    Icon, label, active = false, onClick
}) {
    return (
        <button
        onClick={onClick}
        className="basis-0 w-full grow min-h-px min-w-px relative shrink-0"
        >
        {active && (
            <div aria-hidden="true" className="absolute border-[3px_0px_0px] border-blue-600 border-solid inset-0 pointer-events-none" />
        )}
        <div className="flex flex-col items-center relative size-full">
            <div className="box-border content-stretch flex flex-col gap-2 items-center justify-start pb-2 pt-4 px-2 relative w-full">
            <div className="relative shrink-0 size-5 flex items-center justify-center">
                <Icon size={24} className={active ? 'text-blue-600' : 'text-gray-900'} />
            </div>
            <div 
                className={`font-['Roboto:Bold',_sans-serif] font-normal leading-[0] relative shrink-0 text-[14px] text-nowrap ${
                active ? 'text-blue-600' : 'text-gray-900'
                }`} 
                style={{ fontVariationSettings: "'wdth' 100" }}
            >
                <p className="leading-[normal] whitespace-pre">{label}</p>
            </div>
            </div>
        </div>
        </button>
    )
}

export function NavigationTabs({
    activeTab = 'botting',
    onTabChange
}) {
    return (
        <div className='bg-white flex content-stretch w-full pb-5'>
            <div className='w-full'>
            <TabItem 
                Icon={Bot} 
                label="Botting" 
                active={activeTab === 'botting'}
                onClick={() => onTabChange?.('botting')}
            />
            </div>
            <div className='w-full'>
            <TabItem 
                Icon={Keyboard} 
                label="Macro" 
                active={activeTab === 'macro'}
                onClick={() => onTabChange?.('macro')}
            />
            </div>
        </div>
    )
}