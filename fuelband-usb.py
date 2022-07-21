#!/usr/bin/env python3

# requires hidapi:
# https://github.com/trezor/cython-hidapi

import sys
import time
import nike
import nike.utils as utils

fb = nike.open_fuelband()

if len(sys.argv) > 1:
    if sys.argv[1] == 'log':
        fb.dumpLog()
        print(fb.log)

    elif sys.argv[1] == 'status':
        fb.doVersion()
        print('Firmware version: %s' % fb.firmware_version)
        fb.protocolVersion()
        print('Protocol version: %s' % fb.protocol_version)

        if (fb.protocol_version == 'None') or ('B' in fb.firmware_version):
            print('Fuelband in bootblock!')

        fb.doNetworkVersion()
        print('Network version: %s' % fb.network_version)

        fb.doStatus()
        print('Status bytes: ', end='')
        utils.print_hex(fb.status_bytes)

        fb.doBattery()
        print('Battery status: %d%% charged, %dmV, %s' % (fb.battery_percent, fb.battery_mv, fb.battery_mode))

        fb.doGoal(nike.GOAL_TYPE_A)
        print('Goal A: %d' % (fb.goal_a))

        fb.doGoal(nike.GOAL_TYPE_B)
        print('Goal B: %d' % (fb.goal_b))

        fb.doModelNumber()
        print('Model number: %s' % fb.model_number)

        fb.doSerialNumber()
        print('Serial number: %s' % fb.serial_number)

        fb.doHWRevision()
        print('Hardware revision: %s' % fb.hardware_revision)

        fb.doTimeStampDeviceInit()
        print('Timestamp device-init: %d (%s)' % (fb.timestamp_deviceinit, utils.to_hex(fb.timestamp_deviceinit_raw)))

        fb.doTimeStampAssessmentStart()
        print('Timestamp assessment-start: %d (%s)' % (fb.timestamp_assessmentstart, utils.to_hex(fb.timestamp_assessmentstart_raw)))

        fb.doTimeStampLastFuelReset()
        print('Timestamp fuel-reset: %d (%s)' % (fb.timestamp_lastfuelreset, utils.to_hex(fb.timestamp_lastfuelreset_raw)))

        fb.doTimeStampLastGoalReset()
        print('Timestamp goal-reset: %d (%s)' % (fb.timestamp_lastgoalreset, utils.to_hex(fb.timestamp_lastgoalreset_raw)))


    elif sys.argv[1] == 'desktopdata':
        if sys.argv[2] == 'get':
            if len(sys.argv) > 3:
                dump = fb.dumpMemory([0x50, 0x37, 0x36], 280)
                with open(sys.argv[3], "wb") as f:
                    #for t_byte in dump:
                    f.write(bytes(dump))
            #utils.print_hex(dump)
            #utils.print_ascii(dump)
    elif sys.argv[1] == 'factory_reset':
        fb.doFactoryReset()
    elif sys.argv[1] == 'scan_cmds':
        for cmd in range(255):
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
                res = fb.send([cmd],True)
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
