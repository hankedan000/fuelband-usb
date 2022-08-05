#!/usr/bin/env python3

# requires hidapi:
# https://github.com/trezor/cython-hidapi

import sys
import time
import nike
import nike.utils as utils

fb = nike.open_fuelband()
if fb == None:
    print("No fuelband devices found")
    exit(-1)

print('opened %s' % (fb.getModelNumber()))

if len(sys.argv) > 1:
    if sys.argv[1] == 'log':
        fb.dumpLog()
        print(fb.log)

    elif sys.argv[1] == 'status':
        fb.printStatus()

    elif sys.argv[1] == 'desktopdata':
        if sys.argv[2] == 'get':
            if len(sys.argv) > 3:
                dump = fb.dumpMemory([0x50, 0x37, 0x36], 280)
                with open(sys.argv[3], "wb") as f:
                    #for t_byte in dump:
                    f.write(bytes(dump))
            #utils.print_hex(dump)
            #utils.print_ascii(dump)
    elif sys.argv[1] == 'set_time':
        fb.setTimeAndDate()
    elif sys.argv[1] == 'factory_reset':
        fb.doFactoryReset()
    elif sys.argv[1] == 'latchup':
        fb.doLatchup()
    elif sys.argv[1] == 'dump_graphics_pack':
        filename = 'graphics_pack.bin'
        data = fb.readGraphicsPackData(0x0000, 4096)
        with open(filename,'wb') as f:
            f.write(bytes(data))
        print("dumped %d byte(s) to '%s'" % (len(data),filename))
    elif sys.argv[1] == 'scan_cmds':
        for cmd in range(0x00, 0x100):
            if cmd == 0x02:
                # skip factory reset
                continue
            elif cmd == 0x0b:
                # send error
                continue
            elif cmd == 0x14:
                # send error and OS read error
                continue
            elif cmd == 0xdf:
                # send error
                continue

            try:
                print("Sending command 0x%02X..." % (cmd))
                res = fb.send([cmd], verbose=True)
                fb.dumpLog()
                if len(fb.log) > 0:
                    print("======== begin log ========")
                    print(fb.log)
                    print("========= end log =========")
                    fb.log = ''
            except OSError as os_error:
                print("  INVALID! (os_error = %s)" % (cmd,str(os_error)))
                exit(-1)



else:
    #buf = fb.send([0xe4, 0x6d, 0x6d, 0x20, 0x6d, 0x00])
    #utils.print_hex(buf)
    #utils.print_ascii(buf, True)
    #fb.doVersion()
    #print(fb.firmware_version)
    #fb.doNetworkVersion()

    # desktop data
    dump = fb.dumpMemory([0x50, 0x37, 0x36], 280)

    # workout data
    # dump = fb.dumpMemory([0x19])

    #dump = fb.dumpMemory([0x54, 0x37, 0x03])
    utils.print_hex(dump)
    utils.print_ascii(dump)
    print('')
    print('%d bytes / %d kb dumped' % (len(dump), len(dump)//1024))


    print('')
    fb.dumpLog()
    utils.print_ascii(fb.log)
