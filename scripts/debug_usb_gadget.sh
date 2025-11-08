#!/bin/bash
# Debug USB HID gadget configuration

echo "======================================================================"
echo "USB HID GADGET DIAGNOSTIC"
echo "======================================================================"

echo ""
echo "1. HID GADGET DEVICE FILE"
echo "----------------------------------------------------------------------"
if [ -e /dev/hidg0 ]; then
    echo "✓ /dev/hidg0 exists"
    ls -l /dev/hidg0
    echo ""
    echo "Testing write permissions:"
    if [ -w /dev/hidg0 ]; then
        echo "  ✓ /dev/hidg0 is writable"
    else
        echo "  ✗ /dev/hidg0 is NOT writable (permission issue)"
        echo "  Current user: $(whoami)"
        echo "  File owner: $(stat -c '%U:%G' /dev/hidg0)"
    fi
else
    echo "✗ /dev/hidg0 DOES NOT EXIST"
    echo "  The USB HID gadget is not configured!"
    echo ""
    echo "  Check if gadget module is loaded:"
    echo "    lsmod | grep usb"
    echo "    lsmod | grep gadget"
fi

echo ""
echo "2. USB DEVICE CONTROLLER (UDC) STATUS"
echo "----------------------------------------------------------------------"
UDC_DEVICES=$(ls /sys/class/udc/ 2>/dev/null)
if [ -z "$UDC_DEVICES" ]; then
    echo "✗ NO UDC devices found in /sys/class/udc/"
    echo "  This means USB device controller is not available/loaded"
else
    echo "Found UDC device(s):"
    for udc in /sys/class/udc/*; do
        udc_name=$(basename "$udc")
        echo "  - $udc_name"

        if [ -f "$udc/state" ]; then
            state=$(cat "$udc/state" 2>/dev/null)
            if [ "$state" = "configured" ]; then
                echo "    State: $state ✓ (USB host connected and enumerated)"
            elif [ "$state" = "not attached" ]; then
                echo "    State: $state ✗ (No gadget bound to this UDC)"
            else
                echo "    State: $state (USB host not fully connected)"
            fi
        fi
    done
fi

echo ""
echo "3. USB GADGET CONFIGURATION"
echo "----------------------------------------------------------------------"
if [ -d /sys/kernel/config/usb_gadget ]; then
    echo "✓ ConfigFS USB gadget framework is available"

    GADGETS=$(ls /sys/kernel/config/usb_gadget/ 2>/dev/null)
    if [ -z "$GADGETS" ]; then
        echo "✗ NO gadgets configured in /sys/kernel/config/usb_gadget/"
    else
        echo ""
        echo "Configured gadget(s):"
        for gadget in /sys/kernel/config/usb_gadget/*; do
            gadget_name=$(basename "$gadget")
            echo "  Gadget: $gadget_name"

            # Check if gadget is bound to UDC
            if [ -f "$gadget/UDC" ]; then
                udc_binding=$(cat "$gadget/UDC" 2>/dev/null)
                if [ -z "$udc_binding" ]; then
                    echo "    UDC Binding: (none) ✗ - Gadget is NOT bound to a UDC!"
                    echo "    This is the problem! Gadget needs to be bound to UDC."
                else
                    echo "    UDC Binding: $udc_binding ✓"
                fi
            fi

            # Check functions
            if [ -d "$gadget/functions" ]; then
                echo "    Functions:"
                for func in "$gadget/functions"/*; do
                    if [ -e "$func" ]; then
                        func_name=$(basename "$func")
                        echo "      - $func_name"
                    fi
                done
            fi

            # Check configurations
            if [ -d "$gadget/configs" ]; then
                echo "    Configs:"
                for cfg in "$gadget/configs"/*; do
                    if [ -e "$cfg" ]; then
                        cfg_name=$(basename "$cfg")
                        echo "      - $cfg_name"
                    fi
                done
            fi
        done
    fi
else
    echo "✗ ConfigFS not mounted or USB gadget framework not available"
fi

echo ""
echo "4. KERNEL MODULES"
echo "----------------------------------------------------------------------"
echo "Checking loaded USB gadget modules:"
MODULES=$(lsmod | grep -E "(gadget|usb|dwc|configfs)" | awk '{print $1}')
if [ -z "$MODULES" ]; then
    echo "✗ No USB gadget modules loaded"
else
    echo "$MODULES"
fi

echo ""
echo "5. PHYSICAL USB CONNECTION"
echo "----------------------------------------------------------------------"
echo "Checking dmesg for USB events (last 20 lines with 'usb'):"
dmesg | grep -i usb | tail -20

echo ""
echo "======================================================================"
echo "DIAGNOSIS SUMMARY"
echo "======================================================================"

# Determine the issue
if [ ! -e /dev/hidg0 ]; then
    echo "❌ ISSUE: /dev/hidg0 does not exist"
    echo ""
    echo "SOLUTION:"
    echo "  1. Check if USB gadget kernel modules are loaded"
    echo "  2. Check if USB gadget is configured via ConfigFS"
    echo "  3. Run gadget initialization script (if you have one)"
    echo "  4. Check systemd service dependencies (pikb-gadget.service?)"
elif [ ! -w /dev/hidg0 ]; then
    echo "❌ ISSUE: /dev/hidg0 exists but is not writable"
    echo ""
    echo "SOLUTION:"
    echo "  Fix permissions with:"
    echo "    sudo chmod 666 /dev/hidg0"
    echo "  OR add user to appropriate group"
else
    # Check UDC state
    UDC_CONFIGURED=false
    for udc in /sys/class/udc/*/state; do
        if [ -f "$udc" ]; then
            state=$(cat "$udc" 2>/dev/null)
            if [ "$state" = "configured" ]; then
                UDC_CONFIGURED=true
                break
            fi
        fi
    done

    if $UDC_CONFIGURED; then
        echo "✅ USB gadget appears to be properly configured!"
        echo ""
        echo "If you're still seeing BrokenPipeError, the USB host may be:"
        echo "  - Disconnecting/reconnecting frequently"
        echo "  - Entering power-save mode"
        echo "  - Having driver issues recognizing the gadget"
    else
        echo "❌ ISSUE: /dev/hidg0 exists but USB gadget is NOT in 'configured' state"
        echo ""
        echo "Possible causes:"
        echo "  1. USB cable not connected"
        echo "  2. Host computer is off/sleeping"
        echo "  3. Gadget not bound to UDC controller"
        echo ""
        echo "SOLUTIONS:"
        echo "  1. Check USB cable is connected between Pi and host computer"
        echo "  2. Check host computer is powered on"
        echo "  3. Bind gadget to UDC:"
        for udc in /sys/class/udc/*; do
            if [ -e "$udc" ]; then
                udc_name=$(basename "$udc")
                echo "     sudo sh -c 'echo \"$udc_name\" > /sys/kernel/config/usb_gadget/*/UDC'"
            fi
        done
        echo "  4. Restart USB gadget service:"
        echo "     sudo systemctl restart pikb-gadget.service"
    fi
fi

echo "======================================================================"
