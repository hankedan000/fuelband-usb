
# requires hidapi:
# https://github.com/trezor/cython-hidapi
import hid
import nike.utils

GOAL_TYPE_CURRENT  = 0x00
GOAL_TYPE_TOMORROW = 0x01

# hand orientation
ORIENTATION_LEFT = 1
ORIENTATION_RIGHT = 0

class FuelbandBase():
    VID = 0x11ac# Nike USB vendor id

    def __init__(self, device):
        self.device = device

        self.log = ''

        self.firmware_version = ''
        self.network_version = ''
        self.protocol_version = 'None'
        self.serial_number = ''
        self.hardware_revision = ''

    def send(self, cmd, **kwargs):
        verbose = kwargs.get('verbose',False)
        report_id = kwargs.get('report_id',0x01)

        # seems to be something that can get 'wrapped' backed in the
        # response packets... kinda of like a sequence id? initially i
        # i see them incrementing this number for each transaction from
        # the Nike+ Connect app, but eventually that stops, and it just
        # becomes nonsense.
        tag = kwargs.get('tag',0xFF)

        cmd_prefix = [report_id, len(cmd) + 1, tag]
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

FB_COMMAND_LUT = {
    'latchup' : {
        'cmd' : [0x03],
        'description' : 'Turn off battery',
        'args' : []
    }
}

FUELBAND_STATUS_BITFIELDS = [
    {'mask' : 0x8000000000000000, 'name' : 'serial_set'},
    {'mask' : 0x2000000000000000, 'name' : 'airplane_mode'},
    {'mask' : 0x1000000000000000, 'name' : 'power_day'},
    {'mask' : 0x0800000000000000, 'name' : 'goal_set'},
    {'mask' : 0x0600000000000000, 'name' : 'mode'},
    {'mask' : 0x0100000000000000, 'name' : 'imprinted'},
    {'mask' : 0x000000c000000000, 'name' : 'network_processor_status'},
    {'mask' : 0x0000000018000000, 'name' : 'battery_temp_fault'},
    {'mask' : 0x0000000000000400, 'name' : 'flash_present'},
    {'mask' : 0x0000000000000100, 'name' : 'accel_present'}
]

class Fuelband(FuelbandBase):
    PID = 0x6565# Fuelband USB product id

    def __init__(self, device):
        super().__init__(device)

        self.goal_current = None# 16bit fuel goal
        self.goal_tomorrow = None# 16bit fuel goal


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

    def doLatchup(self):# turn off battery
        buf = self.send([0x03])

    def doSaveUserSettings(self):
        buf = self.send([0x30])

    def doStatus(self):
        buf = self.send([0xdf])
        if len(buf) != 8:
            print('Error getting status: ', end='')
            utils.print_hex(buf)
        else:
            self.status_bytes = buf

    def getModelNumber(self):
        buf = self.send([0xe0])
        if len(buf) <= 0:
            print('Error getting model number: ', end='')
            utils.print_hex(buf)
            return None
        return utils.to_ascii(buf)

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
            self.battery_percent = utils.intFromBigEndian(buf[0:1])
            self.battery_mv = utils.intFromBigEndian(buf[2:4])
            if   buf[1] == 0x59:
                self.battery_mode = 'charging'
            elif buf[1] == 0x4e:
                self.battery_mode = 'idle'
            else:
                self.battery_mode = 'unknown %s' % utils.to_hex(buf[1])

    def doGoal(self, goal_type=GOAL_TYPE_CURRENT):
        buf = self.send([0x25, goal_type])
        if len(buf) <= 0:
            print('Error getting goal: ', end='')
            utils.print_hex(buf)
        else:
            if goal_type == GOAL_TYPE_CURRENT:
                self.goal_current = utils.intFromBigEndian(buf[1:3])
            elif goal_type == GOAL_TYPE_TOMORROW:
                self.goal_tomorrow = utils.intFromBigEndian(buf[1:3])
            else:
                print('Error invalid goal_type: ', end='')
                utils.print_hex(buf)

    def doTimeStampDeviceInit(self):
        buf = self.send([0x42, 0x01])
        self.timestamp_deviceinit_raw = buf[0:4]
        self.timestamp_deviceinit = utils.intFromBigEndian(buf[0:4])

    def doTimeStampAssessmentStart(self):
        buf = self.send([0x42, 0x02])
        self.timestamp_assessmentstart_raw = buf[0:4]
        self.timestamp_assessmentstart = utils.intFromBigEndian(buf[0:4])

    def doTimeStampLastFuelReset(self):
        buf = self.send([0x42, 0x03])
        self.timestamp_lastfuelreset_raw = buf[0:4]
        self.timestamp_lastfuelreset = utils.intFromBigEndian(buf[0:4])

    def doTimeStampLastGoalReset(self):
        buf = self.send([0x42, 0x04])
        self.timestamp_lastgoalreset_raw = buf[0:4]
        self.timestamp_lastgoalreset = utils.intFromBigEndian(buf[0:4])

    def dumpLog(self):

        buf = [0]
        while len(buf) > 0:
            buf = self.send([0xf6], verbose=False)
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

    def printStatusBitfield(self, show_expected=False):
        status_word = int.from_bytes(self.status_bytes, 'big')
        print('status: 0x%016x (actual)' % status_word)
        utils.print_bitfield_rows(status_word, FUELBAND_STATUS_BITFIELDS, 64)

        if not show_expected:
            return

        print()

        # got this from a log dump from the fuelband itself
        EXPECT_STATUS = 0x00CF3F5707FF0700
        print('status: 0x%016x (expect)' % EXPECT_STATUS)
        utils.print_bitfield_rows(EXPECT_STATUS, FUELBAND_STATUS_BITFIELDS, 64)

    def printStatus(self):
        self.doVersion()
        print('Firmware version: %s' % self.firmware_version)

        self.protocolVersion()
        print('Protocol version: %s' % self.protocol_version)

        if (self.protocol_version == 'None') or ('B' in self.firmware_version):
            print('Fuelband in bootblock!')

        self.doNetworkVersion()
        print('Network version: %s' % self.network_version)

        self.doStatus()
        self.printStatusBitfield()

        self.doBattery()
        print('Battery status: %d%% charged, %dmV, %s' % (self.battery_percent, self.battery_mv, self.battery_mode))

        self.doGoal(nike.GOAL_TYPE_CURRENT)
        print('Goal (current): %d' % (self.goal_current))

        self.doGoal(nike.GOAL_TYPE_TOMORROW)
        print('Goal (tomorrow): %d' % (self.goal_tomorrow))

        print('Model number: %s' % self.getModelNumber())

        self.doSerialNumber()
        print('Serial number: %s' % self.serial_number)

        self.doHWRevision()
        print('Hardware revision: %s' % self.hardware_revision)

        self.doTimeStampDeviceInit()
        print('Timestamp device-init: %d (%s)' % (self.timestamp_deviceinit, utils.to_hex(self.timestamp_deviceinit_raw)))

        self.doTimeStampAssessmentStart()
        print('Timestamp assessment-start: %d (%s)' % (self.timestamp_assessmentstart, utils.to_hex(self.timestamp_assessmentstart_raw)))

        self.doTimeStampLastFuelReset()
        print('Timestamp fuel-reset: %d (%s)' % (self.timestamp_lastfuelreset, utils.to_hex(self.timestamp_lastfuelreset_raw)))

        self.doTimeStampLastGoalReset()
        print('Timestamp goal-reset: %d (%s)' % (self.timestamp_lastgoalreset, utils.to_hex(self.timestamp_lastgoalreset_raw)))

OPCODE_VERSION = 5
OPCODE_EVENT_LOG = 7
OPCODE_RTC = 9
OPCODE_SETTING_GET = 10
OPCODE_SETTING_SET = 11
OPCODE_STATUS = 32

SETTING_SERIAL_NUMBER = 0
SETTING_GOAL_0 = 40 # 0 to 6 for days of week (0 = monday)
SETTING_GOAL_1 = 41
SETTING_GOAL_2 = 42
SETTING_GOAL_3 = 43
SETTING_GOAL_4 = 44
SETTING_GOAL_5 = 45
SETTING_GOAL_6 = 46
SETTING_FUEL = 48
SETTING_MENU_CALORIES = 57
SETTING_MENU_STEPS = 58
SETTING_HANDEDNESS = 65 # orientation
SETTING_MENU_STARS = 89 # hours won
SETTING_LIFETIME_FUEL = 94
SETTING_FIRST_NAME = 97

class FuelbandSE(FuelbandBase):
    PID = 0x317d# Fuelband SE USB product id

    def __init__(self, device):
        super().__init__(device)

        self.goal_current = None# 16bit fuel goal
        self.goal_tomorrow = None# 16bit fuel goal

    def setSetting(self, setting_code, opt_buf):
        buf = self.send([OPCODE_SETTING_SET, setting_code, len(opt_buf)] + opt_buf, verbose=False)
        return len(buf) == 1 and buf[0] == 0x00

    def getSetting(self, setting_code):
        setting_len = 1 # setting_code always 1 byte?
        buf = self.send([OPCODE_SETTING_GET, setting_len, setting_code], verbose=False)
        # FuelbandBase.send() only returns the last part of the full response buffer
        #  _____________________
        # /    full reponse     \
        #           ____________
        #          /    buf     \
        # 01 06 ff 00 01 41 01 01
        # ^  ^  ^  ^  ^  ^  ^  ^
        # |  |  |  |  |  |  |  +- setting value
        # |  |  |  |  |  |  +---- setting length
        # |  |  |  |  |  +------- setting code (0x41 = 'handedness') \___ wrapped back command
        # |  |  |  |  +---------- cmd length                         /
        # |  |  |  +------------- status word?
        # |  |  +---------------- tag (so we know what response this is. FuelbandBase always uses 0xff)
        # |  +------------------- total response length in bytes
        # +---------------------- USB HID report id (always 1?)

        # TODO could check status and wrapped command for validity
        return buf[4:]

    def getModelNumber(self):
        buf = self.send([OPCODE_VERSION])
        if len(buf) <= 0:
            print('Error getting model number: ', end='')
            utils.print_hex(buf)
            return None
        # TODO there's definitely some extra info at the beginning of this reponse
        return utils.to_ascii(buf[15:])

    def getSerialNumber(self):
        buf = self.getSetting(SETTING_SERIAL_NUMBER)
        return utils.to_ascii(buf)

    def getStatus(self):
        buf = self.send([OPCODE_STATUS])
        if len(buf) <= 0:
            print('Error getting status: ', end='')
            utils.print_hex(buf)
            return None
        return buf

    def getTime(self):
        buf = self.send([OPCODE_RTC,0x2])
        time = {
            'hour' : buf[1],
            'min' : buf[2],
            'sec' : buf[3]
        }
        return time

    def getDate(self):
        buf = self.send([OPCODE_RTC,0x4])
        date = {
            'year' : 2000 + buf[1],
            'month' : buf[2],
            'day' : buf[3]
        }
        return date

    def setOrientation(self, orientation):
        return self.setSetting(SETTING_HANDEDNESS, [orientation])

    def getOrientation(self):
        return self.getSetting(SETTING_HANDEDNESS)[0]

    def getFuel(self):
        return utils.intFromLittleEndian(self.getSetting(SETTING_FUEL))

    def getLifeTimeFuel(self):
        return utils.intFromLittleEndian(self.getSetting(SETTING_LIFETIME_FUEL))

    # goal_idx - [0 to 6] (0 = monday)
    # goal - 32bit value
    def setGoal(self, goal_idx, goal):
        if goal_idx < 0:
            raise RuntimeError('invalid goal_idx must be >=0')
        elif goal_idx > 6:
            raise RuntimeError('invalid goal_idx must be <=6')
        setting_code = SETTING_GOAL_0 + goal_idx
        return self.setSetting(setting_code,utils.intToLittleEndian(goal,4))

    # goal_idx [0 to 6] (0 = monday)
    def getGoal(self, goal_idx=0):
        if goal_idx < 0:
            raise RuntimeError('invalid goal_idx must be >=0')
        elif goal_idx > 6:
            raise RuntimeError('invalid goal_idx must be <=6')
        setting_code = SETTING_GOAL_0 + goal_idx
        return utils.intFromLittleEndian(self.getSetting(setting_code))

    def setFirstname(self,name):
        name_buff = list(bytes(name,'ascii'))
        return self.setSetting(SETTING_FIRST_NAME,name_buff)

    def getFirstName(self):
        return self.getSetting(SETTING_FIRST_NAME)

    def setDisplayOptions(self, **kwargs):
        okay = True

        calories = kwargs.get('calories',None)
        if calories != None:
            calories = (0x01 if calories else 0x00)
            okay = self.setSetting(SETTING_MENU_CALORIES, [calories]) and okay

        steps = kwargs.get('steps',None)
        if steps != None:
            steps = (0x01 if steps else 0x00)
            okay = self.setSetting(SETTING_MENU_STEPS, [steps]) and okay

        hours_won = kwargs.get('hours_won',None)
        if steps != None:
            hours_won = (0x01 if hours_won else 0x00)
            okay = self.setSetting(SETTING_MENU_STARS, [hours_won]) and okay

        return okay

    def printStatus(self):
        # self.doVersion()
        # print('Firmware version: %s' % self.firmware_version)

        # self.protocolVersion()
        # print('Protocol version: %s' % self.protocol_version)

        # if (self.protocol_version == 'None') or ('B' in self.firmware_version):
        #     print('Fuelband in bootblock!')

        # self.doNetworkVersion()
        # print('Network version: %s' % self.network_version)

        status_bytes = self.getStatus()
        print('Status bytes: %s' % utils.to_hex(status_bytes))

        print('Time: %s' % self.getTime())

        print('Date: %s' % self.getDate())

        # self.doBattery()
        # print('Battery status: %d%% charged, %dmV, %s' % (self.battery_percent, self.battery_mv, self.battery_mode))

        print('Model number: %s' % self.getModelNumber())

        print('Serial number: %s' % self.getSerialNumber())

        first_name = self.getFirstName()
        print('First Name: %s' % (utils.to_ascii(first_name)))

        print('Fuel: %s' % (self.getFuel()))

        print('Fuel (lifetime): %s' % (self.getLifeTimeFuel()))

        DAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
        for d in range(7):
            print('Goal%d (%s): %s' % (d,DAYS[d],self.getGoal(d)))

        orientation = self.getOrientation()
        print('Orientation: %s' % ('LEFT' if orientation == ORIENTATION_LEFT else 'RIGHT'))

        # self.doHWRevision()
        # print('Hardware revision: %s' % self.hardware_revision)

        # self.doTimeStampDeviceInit()
        # print('Timestamp device-init: %d (%s)' % (self.timestamp_deviceinit, utils.to_hex(self.timestamp_deviceinit_raw)))

        # self.doTimeStampAssessmentStart()
        # print('Timestamp assessment-start: %d (%s)' % (self.timestamp_assessmentstart, utils.to_hex(self.timestamp_assessmentstart_raw)))

        # self.doTimeStampLastFuelReset()
        # print('Timestamp fuel-reset: %d (%s)' % (self.timestamp_lastfuelreset, utils.to_hex(self.timestamp_lastfuelreset_raw)))

        # self.doTimeStampLastGoalReset()
        # print('Timestamp goal-reset: %d (%s)' % (self.timestamp_lastgoalreset, utils.to_hex(self.timestamp_lastgoalreset_raw)))

def open_fuelband():
    device = hid.device()

    # try gen 1 Fuelband
    try:
        device.open(FuelbandBase.VID, Fuelband.PID)
        device.set_nonblocking(1)
        return Fuelband(device)
    except IOError as ex:
        # no fuelband 1 exists
        pass

    # try gen 2 Fuelband (SE)
    try:
        device.open(FuelbandBase.VID, FuelbandSE.PID)
        device.set_nonblocking(1)
        return FuelbandSE(device)
    except IOError as ex:
        # no fuelband 1 exists
        pass

    return None