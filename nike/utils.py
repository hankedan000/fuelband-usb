
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

def intFromLittleEndian(buf):
    t_num = 0
    for i in range(len(buf)):
        t_num = t_num | (buf[len(buf) - i - 1] << (i * 8))
    return t_num