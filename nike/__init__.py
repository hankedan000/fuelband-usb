
# requires hidapi:
# https://github.com/trezor/cython-hidapi
import hid
import nike.utils

VID_NIKE        = 0x11ac
PID_FUELBAND    = 0x6565
PID_FUELBAND_SE = 0x317d

GOAL_TYPE_A = 0x00
GOAL_TYPE_B = 0x01


class FuelbandBase():
    def __init__(self, device):
        self.device = device

        self.log = ''

        self.vid = VID_NIKE
        self.pid = None
        self.firmware_version = ''
        self.network_version = ''
        self.protocol_version = 'None'
        self.model_number = ''
        self.serial_number = ''
        self.hardware_revision = ''

    def send(self, cmd, **kwargs):
        verbose = kwargs.get('verbose',False)

        # seems to be something that can get 'wrapped' backed in the
        # response packets... kinda of like a sequence id? initially i
        # i see them incrementing this number for each transaction from
        # the Nike+ Connect app, but eventually that stops, and it just
        # becomes nonsense.
        tag = kwargs.get('tag',0x07)

        cmd_prefix = [0x01, len(cmd) + 1, tag]
        cmd = cmd_prefix + cmd

        if verbose: print("cmd: %s" % (utils.to_hex(cmd)))
        res = self.device.send_feature_report(cmd)
        if res <= 0: print('Error sending feature report')

        buf = self.device.get_feature_report(0x01, 64)
        if verbose: print("rsp (hex):   %s" % (utils.to_hex(buf)))
        if verbose: print("rsp (ascii): %s" % (utils.to_ascii(buf)))

        if len(buf) > 3:
            buf = buf[3:]
        else:
            buf = []
        return buf


class Fuelband(FuelbandBase):
    def __init__(self, device):
        super().__init__(device)

        self.pid = PID_FUELBAND

        self.goal_a = None# 16bit fuel goal
        self.goal_b = None# 16bit fuel goal


    def doVersion(self):
        buf = self.send([0x08])
        if len(buf) != 7:
            print('Error getting firmware version: ', end='')
            utils.print_hex(buf)
        else:
            self.firmware_version = '%c%d.%d' % (buf[0], buf[2], buf[1])
            self.firmware_version_raw = buf
            #print('Firmware Version: %c%d.%d (%02x%02x%02x%02x)' % (buf[0], buf[2], buf[1], buf[3], buf[4], buf[5], buf[6]))

    def doNetworkVersion(self):
        buf = self.send([0x06])
        if len(buf) != 2:
            print('Error getting firmware version: ', end='')
            utils.print_hex(buf)
        else:
            self.network_version = '%d.%d' % (buf[1], buf[0])
            #print('Network Firmware Version: %d.%d' % (buf[1], buf[0]))

    def protocolVersion(self):
        buf = self.send([0x60])
        if len(buf) > 1:
            print('Error getting protocol version: ', end='')
            utils.print_hex(buf)
        if len(buf) == 1:
            self.protocol_version = '%d' % buf[0]
        else:
            self.protocol_version = 'None'

    def doFactoryReset(self):
        buf = self.send([0x02])
        if len(buf) == 1 and buf[0] == 0x00:
            print('Factory reset SUCCESS!')
        else:
            print('Factory reset FAILED!')

    def doSaveUserSettings(self):
        buf = self.send([0x30])

    def doStatus(self):
        buf = self.send([0xdf])
        if len(buf) != 8:
            print('Error getting status: ', end='')
            utils.print_hex(buf)
        else:
            self.status_bytes = buf


    def doModelNumber(self):
        buf = self.send([0xe0])
        if len(buf) <= 0:
            print('Error getting model number: ', end='')
            utils.print_hex(buf)
        else:
            self.model_number = utils.to_ascii(buf)


    def doSerialNumber(self):
        buf = self.send([0xe1])
        if len(buf) <= 0:
            print('Error getting serial number: ', end='')
            utils.print_hex(buf)
        else:
            self.serial_number = utils.to_ascii(buf)

    def doHWRevision(self):
        buf = self.send([0xe2])
        if len(buf) <= 0:
            print('Error getting hardware revision: ', end='')
            utils.print_hex(buf)
        else:
            self.hardware_revision = '%d' % buf[0]

    def doBattery(self):
        buf = self.send([0x13])
        if len(buf) <= 0:
            print('Error getting battery status: ', end='')
            utils.print_hex(buf)
        else:
            self.battery_percent = utils.intFromLittleEndian(buf[0:1])
            self.battery_mv = utils.intFromLittleEndian(buf[2:4])
            if   buf[1] == 0x59:
                self.battery_mode = 'charging'
            elif buf[1] == 0x4e:
                self.battery_mode = 'idle'
            else:
                self.battery_mode = 'unknown %s' % utils.to_hex(buf[1])

    def doGoal(self, goal_type=GOAL_TYPE_A):
        buf = self.send([0x25, goal_type])
        if len(buf) <= 0:
            print('Error getting goal: ', end='')
            utils.print_hex(buf)
        else:
            if goal_type == GOAL_TYPE_A:
                self.goal_a = utils.intFromLittleEndian(buf[1:3])
            elif goal_type == GOAL_TYPE_B:
                self.goal_b = utils.intFromLittleEndian(buf[1:3])
            else:
                print('Error invalid goal_type: ', end='')
                utils.print_hex(buf)

    def doTimeStampDeviceInit(self):
        buf = self.send([0x42, 0x01])
        self.timestamp_deviceinit_raw = buf[0:4]
        self.timestamp_deviceinit = utils.intFromLittleEndian(buf[0:4])

    def doTimeStampAssessmentStart(self):
        buf = self.send([0x42, 0x02])
        self.timestamp_assessmentstart_raw = buf[0:4]
        self.timestamp_assessmentstart = utils.intFromLittleEndian(buf[0:4])

    def doTimeStampLastFuelReset(self):
        buf = self.send([0x42, 0x03])
        self.timestamp_lastfuelreset_raw = buf[0:4]
        self.timestamp_lastfuelreset = utils.intFromLittleEndian(buf[0:4])

    def doTimeStampLastGoalReset(self):
        buf = self.send([0x42, 0x04])
        self.timestamp_lastgoalreset_raw = buf[0:4]
        self.timestamp_lastgoalreset = utils.intFromLittleEndian(buf[0:4])

    def dumpLog(self):

        buf = [0]
        while len(buf) > 0:
            buf = self.send([0xf6, 0x00], verbose=False)
            for t_char in buf:
                self.log = self.log + '%c' % t_char


    def dumpMemory(self, command, max_bytes=0xFFFFFF):
        dump = []
        status = 0x01
        offset = [0x00, 0x00, 0x00]
        while status == 0x01:
            buf = self.send(command + offset)
            #utils.print_hex(buf)
            status = buf[0]
            offset = buf[1:4]
            dump = dump + buf[4:]
            if len(dump) >= max_bytes: status = 0xFF
            utils.print_hex([status] + offset)
        return dump

def open_fuelband():
    device = hid.device()

    # try gen 1 Fuelband
    try:
        device.open(VID_NIKE, PID_FUELBAND)
        device.set_nonblocking(1)
        print('opened Fuelband')
        return Fuelband(device)
    except IOError as ex:
        # no fuelband 1 exists
        pass

    # try gen 2 Fuelband (SE)
    try:
        device.open(VID_NIKE, PID_FUELBAND_SE)
        device.set_nonblocking(1)
        print('opened Fuelband SE!')
        return FuelbandSE(device)
    except IOError as ex:
        # no fuelband 1 exists
        pass

    return None