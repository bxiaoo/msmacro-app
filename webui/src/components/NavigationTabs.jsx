function TabItem({ label, active = false, onClick, count = 0 }) {
    return (
        <div
            className="basis-0 box-border content-stretch flex gap-[10px] grow items-center justify-center min-h-px min-w-px p-[16px] relative shrink-0 cursor-pointer"
            onClick={onClick}
        >
            {active && (
                <div aria-hidden="true" className="absolute border-[0px_0px_4px] border-blue-600 border-solid inset-0 pointer-events-none" />
            )}
            <p className={`font-['Roboto:Bold',_sans-serif] font-bold leading-[16px] relative shrink-0 text-[16px] text-nowrap whitespace-pre ${
                active ? 'text-blue-600' : 'text-gray-900'
            }`} style={{ fontVariationSettings: "'wdth' 100" }}>
                {label}
            </p>
            {count > 0 && (
                <div className={`flex items-center justify-center w-5 h-5 px-1.5 rounded-full bg-gray-300`}>
                    <span className="text-gray-500 text-xs font-medium">
                        {count}
                    </span>
                </div>
            )}
        </div>
    )
}

export function NavigationTabs({
    activeTab = 'rotations',
    onTabChange,
    rotationsCount = 0,
    skillsCount = 0
}) {
    return (
        <div className="content-stretch flex items-center relative w-full" data-name="tab-bar">
            <TabItem
                label="Rotations"
                active={activeTab === 'rotations'}
                onClick={() => onTabChange?.('rotations')}
                count={rotationsCount}
            />
            <TabItem
                label="Skills"
                active={activeTab === 'cd-skills'}
                onClick={() => onTabChange?.('cd-skills')}
                count={skillsCount}
            />
            <TabItem
                label="CV Config"
                active={activeTab === 'cv-config'}
                onClick={() => onTabChange?.('cv-config')}
            />
            <TabItem
                label="Detection"
                active={activeTab === 'object-detection'}
                onClick={() => onTabChange?.('object-detection')}
            />
        </div>
    )
}