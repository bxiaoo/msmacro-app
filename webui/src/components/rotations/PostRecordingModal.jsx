export function PostRecordingModal({ 
  isOpen,
  name,
  onNameChange
}) {
  if (!isOpen) return null;

  return (
    <div className="bg-white relative rounded-tl-[8px] rounded-tr-[8px] shrink-0 w-full" data-name="setting">
      <div className="relative size-full">
        <div className="box-border content-stretch flex flex-col gap-4 items-start justify-start pb-2 pt-6 px-4 relative w-full">
          <div className="font-['Roboto:Bold',_sans-serif] font-bold leading-[0] relative shrink-0 text-[18px] text-gray-900 w-full" style={{ fontVariationSettings: "'wdth' 100" }}>
            <p className="leading-[normal]">Post record</p>
          </div>
          
          {/* Input Section */}
          <div className="content-stretch flex flex-col gap-3.5 items-start justify-start relative shrink-0 w-full">
            <div className="content-stretch flex gap-3.5 items-center justify-start relative shrink-0 w-full">
              <div className="basis-0 content-stretch flex flex-col gap-2 grow items-start justify-start min-h-px min-w-px relative shrink-0" data-name="input">
                <div className="bg-white h-11 relative rounded-[2px] shrink-0 w-full" data-name="input-text">
                  <div className="flex flex-row items-center overflow-clip relative size-full">
                    <div className="box-border content-stretch flex gap-2.5 h-11 items-center justify-start px-2 py-0 relative w-full">
                      <input
                        type="text"
                        value={name}
                        onChange={(e) => onNameChange(e.target.value)}
                        placeholder="Name"
                        className="w-full bg-transparent border-none outline-none font-['Roboto:Regular',_sans-serif] font-normal leading-[0] text-[16px] text-gray-900 placeholder:text-gray-600"
                        style={{ fontVariationSettings: "'wdth' 100" }}
                      />
                    </div>
                  </div>
                  <div aria-hidden="true" className="absolute border border-gray-400 border-solid inset-[-1px] pointer-events-none rounded-[3px]" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}