#!/usr/bin/env python3
from enum import Enum
import argparse
import nike
import nike.utils as utils

MAX_BYTES_PER_LINE = 16

# bytes offsets into txt file line
DATA_IDX   = 6
DATA_WIDTH = MAX_BYTES_PER_LINE * 3 - 1
ASCII_IDX  = DATA_IDX + DATA_WIDTH + 3

class RequestType(Enum):
    SUBMIT = 0x00
    COMPLETE = 0x01

class ReportType(Enum):
    SET_REPORT = 0x00
    GET_REPORT = 0x80

class RW_Mode(Enum):
    READ = 0x00
    WRITE = 0x01
    UNKNOWN1 = 0x02
    UNKNOWN_READ1 = 0x03 # finish read?
    UNKNOWN_READ2 = 0x04 # used for desktop data only?

class Packet(object):
    def __init__(self, id, data):
        self.id = id
        self.data = data
        self.request_type = RequestType(data[3])
        self.report_type = ReportType(data[30] & 0x80)

class Request(Packet):
    def __init__(self, pkt):
        super(Request, self).__init__(pkt.id, pkt.data)
        self.pkt = pkt

        FB_CMD_OFFSET = 32 # 32 -> Mac, 36 -> Linux
        self.report_id = self.data[FB_CMD_OFFSET]
        self.req_len = self.data[FB_CMD_OFFSET + 1]
        self.tag = self.data[FB_CMD_OFFSET + 2]
        self.opcode = nike.SE_Opcode(self.data[FB_CMD_OFFSET + 3])
        self.payload = self.data[FB_CMD_OFFSET + 4:FB_CMD_OFFSET + 4 + self.req_len - 1]
        self.subcmd_code = None
        self.subcmd_len = 0
        self.subcmd_val = []
        if self.opcode == nike.SE_Opcode.SETTING_SET:
            self.subcmd_code = nike.SE_SubCmdSett(self.payload[0])
            self.subcmd_len = int(self.payload[1])
            self.subcmd_val = self.payload[2:2+self.subcmd_len]
        elif self.opcode == nike.SE_Opcode.SETTING_GET:
            length = int(self.payload[0])
            if length != 1:
                raise RuntimeError("SETTING_GET request should have length == 1, but it's %d" % length)
            self.subcmd_code = nike.SE_SubCmdSett(self.payload[1])
        elif self.opcode == nike.SE_Opcode.BATTERY_STATE:
            self.subcmd_code = nike.SE_SubCmdBatt(self.payload[0])

    def pretty_str(self, **kwargs):
        out  = "req - "
        out += "op: %s; " % self.opcode.name
        if self.subcmd_code:
            out += "subcmd: %s; " % self.subcmd_code.name
            out += "subcmd_len: %d; " % self.subcmd_len
            if self.subcmd_len > 0:
                out += "\n%s" % nike.utils.to_hex_with_ascii(self.subcmd_val, indent=4)
        return out

class GraphicsPack(Request):
    def __init__(self, pkt):
        super(GraphicsPack, self).__init__(pkt.id, pkt.data)
        self.index = int(self.payload[0])
        self.address = utils.intFromLittleEndian(self.payload[1:2])
        self.graphics_len = int(self.payload[3])
        self.graphics_data = int(self.payload[4:])
        if len(self.graphics_data) != self.graphics_len:
            raise RuntimeError("graphics data length mismatch!")

    def pretty_str(self, **kwargs):
        out  = "req - "
        out += "op: %s; " % self.opcode.name
        out += "index: %d; " % self.index
        out += "\n%s" % utils.to_hex_with_ascii(self.graphics_data, indent=4)
        return out

class GenericMemoryBlock(Request):
    def __init__(self, pkt):
        super(GenericMemoryBlock, self).__init__(pkt)
        self.rw_mode = RW_Mode(self.payload[0])
        self.address = utils.intFromLittleEndian(self.payload[1:3])
        self.data_len = utils.intFromLittleEndian(self.payload[3:5])
        self.data = []
        if self.rw_mode == RW_Mode.WRITE:
            self.data = self.payload[5:5+self.data_len]

    def pretty_str(self, **kwargs):
        out  = "req - "
        out += "op: %s (%s); " % (self.opcode.name, self.rw_mode.name)
        out += "address: 0x%04x; " % self.address
        out += "data_len: %d; " % self.data_len
        if self.rw_mode == RW_Mode.WRITE:
            out += "\n%s" % utils.to_hex_with_ascii(self.data, indent=4)
        return out

class UploadGraphicsPack(GenericMemoryBlock):
    def __init__(self, pkt):
        super(UploadGraphicsPack, self).__init__(pkt)

def upcast_request(req):
    if req.opcode == nike.SE_Opcode.UPLOAD_GRAPHICS_PACK:
        return UploadGraphicsPack(req.pkt)
    elif req.opcode == nike.SE_Opcode.DESKTOP_DATA:
        return GenericMemoryBlock(req.pkt)
    return req

class Response(Packet):
    def __init__(self, pkt):
        super(Response, self).__init__(pkt.id, pkt.data)

def dissect_pkt(id, data, verbose=False):
    if verbose:
        print("id: %d" % id)
        print("data:")
        print(utils.print_hex_with_ascii(data))

    if len(data) < 35:
        return
    
    pkt = Packet(id, data)
    if pkt.report_type == ReportType.SET_REPORT:
        if pkt.request_type == RequestType.COMPLETE:
            req = upcast_request(Request(pkt))
            print(req.pretty_str())

def dissect_file(pcap_file, **kwargs):
    max_pkts = kwargs.get('max_pkts', None)
    pkt_data = bytearray()
    pkt_idx = 0
    
    DATA_START = DATA_IDX
    DATA_END = DATA_IDX + DATA_WIDTH
    for line_num,line in enumerate(pcap_file):
        if len(line) < DATA_END:
            if len(pkt_data) > 0:
                dissect_pkt(pkt_idx, pkt_data)
                pkt_idx += 1

                if max_pkts and pkt_idx >= max_pkts:
                    break
            pkt_data.clear()
            continue # skip empty line
        
        line = line.decode('utf-8')
        offset = int(line[0:4], 16)
        data = utils.hex_row_to_bytes(line[DATA_START:DATA_END])
        pkt_data += data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='pcap_dissect',
        description="dissects fuelband pcap text files")

    parser.add_argument(
        'pcap',
        type=argparse.FileType('rb'),
        help="the pcap text file to read")

    parser.add_argument(
        '-m','--max-pkts',
        default=None,
        type=int,
        help="max number of packets to analyze")

    args = parser.parse_args()

    dissect_file(
        args.pcap,
        max_pkts=args.max_pkts)