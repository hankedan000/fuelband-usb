
def print_hex(buf, newline=True):
    for i in buf:
        print('%02x ' % i, end='')
    if newline: print('')

def to_hex(buf):
    t_buf = ''
    for i in buf:
        if t_buf != '': t_buf = t_buf + ' '
        t_buf = t_buf + '%02x' % i
    return t_buf

def print_ascii(buf, newline=False):
    for i in buf:
        print('%c' % i, end='')
    if newline: print('')

def to_ascii(buf):
    t_buf = ''
    for i in buf:
        if i != 0x00:
            t_buf = t_buf + '%c' % i
    return t_buf

# sanatizes bytes to just readable ascii chars
def to_ascii_san(byte_buff):
    s = ''
    for b in byte_buff:
        print_char = '%c' % b
        if b < 32 or b > 126:
            print_char = '.'
        s = s + print_char
    return s

def print_hex_with_ascii(buf, **kwargs):
    bytes_per_line = kwargs.get('bytes_per_line',16)

    # build a format string for printing rows with hex portion padded with spaces
    row_hex_width = bytes_per_line * 3 # 3 chars per hex print
    row_fmt_str = '0x%%04x | %%-%ds| %%s' % row_hex_width

    bytes_remaining = len(buf)
    offset = 0
    while bytes_remaining:
        bytes_this_line = bytes_remaining
        if bytes_this_line > bytes_per_line:
            bytes_this_line = bytes_per_line
        buf_slice = buf[offset:(offset+bytes_this_line)]
        print(row_fmt_str % (offset,to_hex(buf_slice),to_ascii_san(buf_slice)))
        bytes_remaining -= bytes_this_line
        offset += bytes_this_line

def intFromBigEndian(buf):
    t_num = 0
    for i in range(len(buf)):
        t_num = t_num | (buf[len(buf) - i - 1] << (i * 8))
    return t_num

def intFromLittleEndian(buf):
    t_num = 0
    for i in range(len(buf)):
        t_num = t_num | (buf[i] << (i * 8))
    return t_num

def intToBigEndian(num,n_bytes):
    buff = []
    for b in range(n_bytes):
        buff.insert(0,num & 0xff)# append to front of list
        num = num >> 8
    return buff

def intToLittleEndian(num,n_bytes):
    buff = []
    for b in range(n_bytes):
        buff.append(num & 0xff)
        num = num >> 8
    return buff

def get_shift(mask):
    if mask == 0:
        return 0
    else:
        shift = 0
        while (mask & 0x1) == 0:
            mask = mask >> 1
            shift = shift + 1
        return shift

def print_bitfield_line(value, mask, name, n_bits=64):
    masked_value = value & mask
    i_mask = (1 << (n_bits - 1))
    for b in range(n_bits):
        if b > 0 and b % 4 == 0:
            print(' ', end='')

        if mask & i_mask:
            if masked_value & i_mask:
                print('1', end='')
            else:
                print('0', end='')
        else:
            print('.', end='')
        i_mask = i_mask >> 1

    shift = get_shift(mask)
    shifted_value = masked_value >> shift
    print(" : '%s' %d (0x%x)" % (name,shifted_value,shifted_value))

def print_bitfield_rows(value, bitfield_def, n_bits=64, show_unknown=True):
    if show_unknown:
        unknown_mask = 0
        for row in bitfield_def:
            unknown_mask = unknown_mask | row['mask']
        unknown_mask = unknown_mask ^ ((1 << n_bits) - 1)# invert the mask
        bitfield_def = [{'mask' : unknown_mask, 'name' : 'reserved/unknown'}] + bitfield_def

    for row in bitfield_def:
        print_bitfield_line(value, row['mask'], row['name'], n_bits)