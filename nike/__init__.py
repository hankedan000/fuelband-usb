
# requires hidapi:
# https://github.com/trezor/cython-hidapi
import hid
import nike.utils
import datetime
from enum import Enum

GOAL_TYPE_CURRENT  = 0x00
GOAL_TYPE_TOMORROW = 0x01

# hand orientation
class Orientation(Enum):
    LEFT = 1
    RIGHT = 0

class Gender(Enum):
    MALE = 1
    FEMALE = 2
    UNKNOWN = 3

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

        # convert all enums in cmd to their integer values
        for i in range(len(cmd)):
            if isinstance(cmd[i], Enum):
                cmd[i] = cmd[i].value

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

    def getOrientation(self):
        return self.send([0x37])[0]

    def setOrientation(self, rightHanded):
        orientation = 0x01 if rightHanded else 0x00
        self.send([0x37, orientation])

    def getGoal(self, goal_type=GOAL_TYPE_CURRENT, goal=None):
        buf = self.send([0x25, goal_type])
        if len(buf) <= 0:
            print('Error getting goal: ', end='')
            utils.print_hex(buf)
        else:
            if goal_type == GOAL_TYPE_CURRENT:
                return utils.intFromBigEndian(buf[1:3])
            elif goal_type == GOAL_TYPE_TOMORROW:
                return utils.intFromBigEndian(buf[1:3])
            else:
                print('Error invalid goal_type: ', end='')
                utils.print_hex(buf)
        return None

    def setGoal(self, goal, goal_type=GOAL_TYPE_CURRENT):
        cmd = [0x25, goal_type] + utils.intToBigEndian(goal,3)
        buf = self.send(cmd)
        return buf

    def getTime(self):
        # TODO not sure how to interpret this yet
        buf = self.send([0x21], verbose=False)
        return buf

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

        print('Orientation: %s' % ("LEFT" if self.getOrientation() == 0 else "RIGHT"))

        print('Goal (current): %d' % self.getGoal(nike.GOAL_TYPE_CURRENT))

        print('Goal (tomorrow): %d' % self.getGoal(nike.GOAL_TYPE_TOMORROW))

        print('Time: %s' % self.getTime())

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

class SE_Opcode(Enum):
    RESET                  = 0x01
    RESET_STATUS           = 0x02
    VERSION                = 0x05
    EVENT_LOG              = 0x07
    BATTERY_STATE          = 0x06
    RTC                    = 0x09
    SETTING_GET            = 0x0a
    SETTING_SET            = 0x0b
    SELF_TEST              = 0x0c
    DEBUG                  = 0x10
    SAMPLE_STORE           = 0x11
    MEMORY_EXT             = 0x12
    DESKTOP_DATA           = 0x13
    SESSION_CTRL           = 0x14
    UPLOAD_GRAPHIC         = 0x15
    UPLOAD_GRAPHICS_PACK   = 0x16
    NOTIFICATION_SUBSCRIBE = 0x18
    STATUS                 = 0x20
    UNKNOWN3               = 0x21
    UNKNOWN2               = 0x60

# sub commands used with 'SE_Opcode.BATTERY_STATE'
class SE_SubCmdBatt(Enum):
    QUERY_BATTERY = 0
    ENABLE_CHARGER = 1
    DISABLE_CHARGER = 2
    DISCONNECT_BATTERY = 3

# sub commands used with 'SE_Opcode.RTC'
SUBCMD_RTC_GET_TIME = 2
SUBCMD_RTC_GET_DATE = 4
SUBCMD_RTC_SET_TIME_DATE = 5

# sub commands for doing memory read/write operations
SUBCMD_END_TRANSACTION = 3
SUBCMD_START_READ = 4
SUBCMD_READ_CHUNK = 0
SUBCMD_START_WRITE = 2
SUBCMD_WRITE_CHUNK = 1

class SE_SubCmdSett(Enum):
    SERIAL_NUMBER = 0
    BAND_COLOR = 1
    BLE_ADDRESS = 2
    BLE_XTAL_TRIM = 3
    BLE_POWER_LEVEL = 4
    ADC_CAL_VCC_MV = 5
    ADC_CAL_VREFINT_CONV = 6
    ADC_CAL_BAT_RATIO = 7
    LED_ROW_BALANCE = 8
    LED_DOT_CORRECTION = 9
    ALS_BOOST = 10
    GOAL_0 = 40 # 0 to 6 for days of week (0 = monday)
    GOAL_1 = 41
    GOAL_2 = 42
    GOAL_3 = 43
    GOAL_4 = 44
    GOAL_5 = 45
    GOAL_6 = 46
    TEMP_GOAL = 47
    FUEL = 48
    CALORIES = 49
    STEPS = 50
    DISTANCE = 51
    ACTIVE_TIME = 52
    USE_24HR_CLOCK = 56
    MENU_CALORIES = 57
    MENU_STEPS = 58
    MENU_GOAL = 59
    MENU_FUEL_RATE = 60
    WEIGHT = 61
    HEIGHT = 62
    DATE_OF_BIRTH = 63
    GENDER = 64
    HANDEDNESS = 65 # orientation
    ACCESS_TOKEN = 66
    REFRESH_TOKEN = 67
    TZ_SECONDS = 69
    DST_MINUTES = 70
    UNKNOWN10 = 72
    UNKNOWN11 = 73
    DISCOVERY_TOKEN = 75
    BLE_AUTHENTICATION_KEY = 76
    UNKNOWN1 = 78
    UNKNOWN15 = 87
    MENU_STARS = 89
    HOURS_WON = 90
    UNKNOWN16 = 91
    MOVE_REMINDER_HOURS = 92
    LIFETIME_FUEL = 94
    UNKNOWN2 = 95
    FIRST_NAME = 97
    IN_SESSION_LED = 99

class FuelbandSE(FuelbandBase):
    PID = 0x317d# Fuelband SE USB product id

    def __init__(self, device):
        super().__init__(device)

        self.goal_current = None# 16bit fuel goal
        self.goal_tomorrow = None# 16bit fuel goal

    def setSetting(self, setting_code, opt_buf, **kwargs):
        verbose = kwargs.get('verbose',False)
        buf = self.send([SE_Opcode.SETTING_SET, setting_code, len(opt_buf)] + opt_buf, verbose=verbose)
        return len(buf) == 1 and buf[0] == 0x00

    def getSetting(self, setting_code):
        setting_len = 1 # setting_code always 1 byte?
        buf = self.send([SE_Opcode.SETTING_GET, setting_len, setting_code], verbose=False)
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
        buf = self.send([SE_Opcode.VERSION])
        if len(buf) <= 0:
            print('Error getting model number: ', end='')
            utils.print_hex(buf)
            return None
        # TODO there's definitely some extra info at the beginning of this reponse
        return utils.to_ascii(buf[15:])

    def getSerialNumber(self):
        buf = self.getSetting(SE_SubCmdSett.SERIAL_NUMBER)
        return utils.to_ascii(buf)

    def getStatus(self):
        buf = self.send([SE_Opcode.STATUS])
        if len(buf) <= 0:
            print('Error getting status: ', end='')
            utils.print_hex(buf)
            return None
        return buf

    def getBatteryState(self):
        buf = self.send([SE_Opcode.BATTERY_STATE,SE_SubCmdBatt.QUERY_BATTERY])
        return {
            'charging' : buf[2] == 1,
            'charge_level' : utils.intFromLittleEndian(buf[3:5]),
            'charge_pct' : utils.intFromLittleEndian(buf[5:7])
        }

    def getTime(self):
        buf = self.send([SE_Opcode.RTC,SUBCMD_RTC_GET_TIME])
        time = {
            'hour' : buf[1],
            'min' : buf[2],
            'sec' : buf[3]
        }
        return time

    def getDate(self):
        buf = self.send([SE_Opcode.RTC,SUBCMD_RTC_GET_DATE])
        date = {
            'year' : 2000 + buf[1],
            'month' : buf[2],
            'day' : buf[3],
            'day_of_week' : buf[4] # 1 = monday ... 7 = sunday
        }
        return date

    # Sets the Fuelband's date and time
    # dt_obj - a python datetime.datetime object. if 'None', then current time
    #      will be used and set.
    def setTimeAndDate(self, dt_obj=None):
        if dt_obj == None:
            dt_obj = datetime.datetime.now()
        cmd = [SE_Opcode.RTC, SUBCMD_RTC_SET_TIME_DATE]
        cmd += [dt_obj.hour,dt_obj.minute,dt_obj.second]
        day_of_week = datetime.date(dt_obj.year,dt_obj.month,dt_obj.day).weekday() + 1 # fuelband wants monday = 1
        cmd += [dt_obj.year-2000,dt_obj.month,dt_obj.day,day_of_week]
        # not sure what the rest of this is...
        cmd += [0x50,0x46,0x00,0x00,0x3c,0x00,0x00]
        buf = self.send(cmd, report_id = 11, verbose=False)
        if len(buf) != 1 and buf[0] != 0x00:
            raise RuntimeError('Failed to set time!')

    def setOrientation(self, orientation):
        return self.setSetting(SE_SubCmdSett.HANDEDNESS, [orientation])

    def getOrientation(self):
        return Orientation(self.getSetting(SE_SubCmdSett.HANDEDNESS)[0])

    def getFuel(self):
        return utils.intFromLittleEndian(self.getSetting(SE_SubCmdSett.FUEL))

    def getLifeTimeFuel(self):
        return utils.intFromLittleEndian(self.getSetting(SE_SubCmdSett.LIFETIME_FUEL))

    # goal_idx - [0 to 6] (0 = monday)
    # goal - 32bit value
    def setGoal(self, goal_idx, goal):
        if goal_idx < 0:
            raise RuntimeError('invalid goal_idx must be >=0')
        elif goal_idx > 6:
            raise RuntimeError('invalid goal_idx must be <=6')
        setting_code = SE_SubCmdSett.GOAL_0.value + goal_idx
        return self.setSetting(setting_code,utils.intToLittleEndian(goal,4))

    # goal_idx [0 to 6] (0 = monday)
    def getGoal(self, goal_idx=0):
        if goal_idx < 0:
            raise RuntimeError('invalid goal_idx must be >=0')
        elif goal_idx > 6:
            raise RuntimeError('invalid goal_idx must be <=6')
        setting_code = SE_SubCmdSett.GOAL_0.value + goal_idx
        return utils.intFromLittleEndian(self.getSetting(setting_code))

    def setFirstname(self,name):
        name_buff = list(bytes(name,'ascii'))
        return self.setSetting(SE_SubCmdSett.FIRST_NAME,name_buff)

    def getFirstName(self):
        return self.getSetting(SE_SubCmdSett.FIRST_NAME)

    def setWeight(self,weight_lbs):
        return self.setSetting(SE_SubCmdSett.WEIGHT,[weight_lbs & 0xFF,(weight_lbs >> 8) & 0xFF])

    # returns height in inches
    def getWeight(self):
        return utils.intFromLittleEndian(self.getSetting(SE_SubCmdSett.WEIGHT))

    def setHeight(self,height_inches):
        return self.setSetting(SE_SubCmdSett.HEIGHT,[height_inches])

    # returns height in inches
    def getHeight(self):
        return self.getSetting(SE_SubCmdSett.HEIGHT)[0]

    def setDateOfBirth(self,date_obj):
        date_buff = [date_obj.year & 0xff, (date_obj.year >> 8) & 0xff, date_obj.month, date_obj.day]
        return self.setSetting(SE_SubCmdSett.DATE_OF_BIRTH,date_buff)

    def getDateOfBirth(self):
        rsp = self.getSetting(SE_SubCmdSett.DATE_OF_BIRTH)
        year = utils.intFromLittleEndian(rsp[0:2])
        month = rsp[2]
        day = rsp[3]
        return datetime.date(year,month,day)

    def setGender(self,gender):
        if gender == Gender.MALE:
            self.setSetting(SE_SubCmdSett.GENDER,[77])
        elif gender == Gender.FEMALE:
            self.setSetting(SE_SubCmdSett.GENDER,[70])
        else:
            raise RuntimeError("Need to set gender to male/female")

    def getGender(self):
        genderCode = self.getSetting(SE_SubCmdSett.GENDER)[0]
        if genderCode == 77:
            return Gender.MALE
        elif genderCode == 70:
            return Gender.FEMALE
        return Gender.UNKNOWN

    def setDisplayOptions(self, **kwargs):
        okay = True

        calories = kwargs.get('calories',None)
        if calories != None:
            calories = (0x01 if calories else 0x00)
            okay = self.setSetting(SE_SubCmdSett.MENU_CALORIES, [calories]) and okay

        steps = kwargs.get('steps',None)
        if steps != None:
            steps = (0x01 if steps else 0x00)
            okay = self.setSetting(SE_SubCmdSett.MENU_STEPS, [steps]) and okay

        hours_won = kwargs.get('hours_won',None)
        if steps != None:
            hours_won = (0x01 if hours_won else 0x00)
            okay = self.setSetting(SE_SubCmdSett.MENU_STARS, [hours_won]) and okay

        return okay

    # not sure what this does
    def getEventLog(self):
        buf = self.send([SE_Opcode.EVENT_LOG],verbose=True)
        return buf

    # causes device reboot???
    def setDebug(self):
        buf = self.send([SE_Opcode.DEBUG,0x1],verbose=True)
        return buf

    def __memoryErrorToStr(self, err_code):
        if err_code == 0:
            return "Success"
        elif err_code == 1:
            return "Request packet does not contain all required fields"
        elif err_code == 2:
            return "Request fields contain invalid values";
        elif err_code == 3:
            return "Transaction already in progress"
        elif err_code == 4:
            return "Request does not belong to a transaction"
        elif err_code == 5:
            return "Failed to open a transaction"
        elif err_code == 6:
            return "Failed to close a transaction"
        elif err_code == 7:
            return "I/O failed"
        return "Unknown error"

    # Starts a block memory operation
    # op_code - SE_Opcode.DESKTOP_DATA, SE_Opcode.UPLOAD_GRAPHICS_PACK, or SE_Opcode.MEMORY_EXT???
    # start_sub_cmd - SUBCMD_START_READ or SUBCMD_START_WRITE
    def __memoryStartOperation(self, op_code, start_sub_cmd, **kwargs):
        verbose = kwargs.get('verbose',False)
        buf = self.send([op_code, start_sub_cmd, 0x01, 0x00],report_id=10,verbose=verbose)
        if len(buf) != 1 and buf[0] != 0x00:
            raise RuntimeError('Failed to start memory operation! status = 0x%x (%s); buf = %s' % (buf[0],self.__memoryErrorToStr(buf[0]),buf))

    def __memoryEndTransaction(self, op_code, **kwargs):
        verbose = kwargs.get('verbose',False)
        buf = self.send([op_code, SUBCMD_END_TRANSACTION],report_id=10,verbose=verbose)
        if len(buf) != 1 and buf[0] != 0x00:
            raise RuntimeError('Failed to end memory transaction! status = 0x%x (%s); buf = %s' % (buf[0],self.__memoryErrorToStr(buf[0]),buf))

    # Start a memory read operation
    # op_code - SE_Opcode.DESKTOP_DATA, SE_Opcode.UPLOAD_GRAPHICS_PACK, or SE_Opcode.MEMORY_EXT???
    def __memoryRead(self,op_code,addr,size, **kwargs):
        verbose = kwargs.get('verbose',False)
        warn_on_truncated = kwargs.get('warn_on_truncated',True)

        self.__memoryStartOperation(op_code,SUBCMD_START_READ,verbose=verbose)

        read_data = []
        bytes_remaining = size
        offset = addr
        cmd_buf = [op_code,SUBCMD_READ_CHUNK,0,0,0,0]
        while bytes_remaining > 0:
            bytes_this_read = bytes_remaining
            if bytes_this_read > 58:
                bytes_this_read = 58
            cmd_buf[2] = offset & 0xff
            cmd_buf[3] = (offset >> 8) & 0xff
            cmd_buf[4] = bytes_this_read & 0xff
            cmd_buf[5] = (bytes_this_read >> 8) & 0xff
            rsp = self.send(cmd_buf,report_id=10,verbose=verbose)
            if len(rsp) >= 1 and rsp[0] != 0x00:
                raise RuntimeError('Read failed! status = 0x%x (%s)' % (rsp[0],self.__memoryErrorToStr(rsp[0])))
            if len(rsp) >= 2 and rsp[1] < bytes_this_read:
                if warn_on_truncated:
                    print('WARN: truncated read! expected = %d; actual = %d' % (bytes_this_read,rsp[1]))
                read_data += rsp[2:]
                break;
            elif len(rsp) >= 2 and rsp[1] > bytes_this_read:
                print('WARN: read size > than expected! expected = %d; actual = %d' % (bytes_this_read,rsp[1]))
                read_data += rsp[2:]
                break;
            else:
                read_data += rsp[2:]
            bytes_remaining -= bytes_this_read
            offset += bytes_this_read

        self.__memoryEndTransaction(op_code,verbose=verbose)

        return read_data

    def readDesktopData(self,addr,size):
        return self.__memoryRead(SE_Opcode.DESKTOP_DATA,addr,size,verbose=False,warn_on_truncated=False)

    def readGraphicsPackData(self,addr,size):
        return self.__memoryRead(SE_Opcode.UPLOAD_GRAPHICS_PACK,addr,size,verbose=False)

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

        batt_state = self.getBatteryState()
        print('Battery State: %s' % batt_state)

        print('Time: %s' % self.getTime())

        print('Date: %s' % self.getDate())

        # self.doBattery()
        # print('Battery status: %d%% charged, %dmV, %s' % (self.battery_percent, self.battery_mv, self.battery_mode))

        print('Model number: %s' % self.getModelNumber())

        print('Serial number: %s' % self.getSerialNumber())

        first_name = self.getFirstName()
        print('First Name: %s' % (utils.to_ascii(first_name)))

        print('Weight: %d lbs' % (self.getWeight()))

        print('Date of Birth: %s' % (self.getDateOfBirth()))

        height = self.getHeight()
        print("Height: %d'%d\"" % (int(height/12),int(height%12)))

        print('Gender: %s' % (self.getGender()))

        print('Fuel: %s' % (self.getFuel()))

        print('Fuel (lifetime): %s' % (self.getLifeTimeFuel()))

        DAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
        for d in range(7):
            print('Goal%d (%s): %s' % (d,DAYS[d],self.getGoal(d)))

        print('Orientation: %s' % (self.getOrientation()))

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

        data = self.readDesktopData(0x0000, 128)
        print('Desktop Data:')
        utils.print_hex_with_ascii(data)

        data = self.readGraphicsPackData(0x0000, 256)# not sure how large these really are
        print('Graphics Pack Data:')
        utils.print_hex_with_ascii(data,bytes_per_line=34)

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