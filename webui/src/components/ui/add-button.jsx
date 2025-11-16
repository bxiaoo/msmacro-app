import {Plus} from "lucide-react";
import * as React from 'react';

function AddButton({ onClick }) {
    return (
        <div
            className="relative rounded-[4px] shrink-0 w-full cursor-pointer"
            onClick={onClick}
        >
            <div className="box-border content-stretch flex items-center justify-center overflow-clip px-0 py-[18px] relative w-full">
                <div className="overflow-clip relative shrink-0 size-[20px]">
                    <Plus size={20} className="text-gray-600" />
                </div>
            </div>
            <div aria-hidden="true" className="absolute border-2 border-dashed border-gray-300 inset-0 pointer-events-none rounded-[4px]" />
        </div>
    )
}

export { AddButton }