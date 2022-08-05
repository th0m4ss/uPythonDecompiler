from dataclasses import dataclass
from enum import IntEnum
from typing import BinaryIO, Any

import micropython.py.makeqstrdata


@dataclass
class QStrType:
    def __init__(self, s: str):
        self.s = s
        self.qstr_esc = micropython.py.makeqstrdata.qstr_escape(self.s)
        self.qstr_id = "MP_QSTR_" + self.qstr_esc


global_qstrs = [None]
for n in micropython.py.makeqstrdata.static_qstr_list:
    global_qstrs.append(QStrType(n))


class InvalidMpyMagicException(Exception):
    pass


class MpCodeType(IntEnum):
    MP_CODE_BYTECODE = 2,
    MP_CODE_NATIVE_PY = 3,
    MP_CODE_NATIVE_VIPER = 4,
    MP_CODE_NATIVE_ASM = 5,


class MpNativeArch(IntEnum):
    MP_NATIVE_ARCH_NONE = 0,
    MP_NATIVE_ARCH_X86 = 1,
    MP_NATIVE_ARCH_X64 = 2,
    MP_NATIVE_ARCH_ARMV6 = 3,
    MP_NATIVE_ARCH_ARMV6M = 4,
    MP_NATIVE_ARCH_ARMV7M = 5,
    MP_NATIVE_ARCH_ARMV7EM = 6,
    MP_NATIVE_ARCH_ARMV7EMSP = 7,
    MP_NATIVE_ARCH_ARMV7EMDP = 8,
    MP_NATIVE_ARCH_XTENSA = 9,
    MP_NATIVE_ARCH_XTENSAWIN = 10,


class MpyVersion(IntEnum):
    MPY_VERSION_0 = 0,
    MPY_VERSION_UNKNOWN = 1,
    MPY_VERSION_2 = 2,
    MPY_VERSION_3 = 3,
    MPY_VERSION_4 = 4,
    MPY_VERSION_5 = 5,
    MPY_VERSION_6 = 6,


class BcFormat(IntEnum):
    MP_BC_FORMAT_BYTE = 0,
    MP_BC_FORMAT_QSTR = 1,
    MP_BC_FORMAT_VAR_UINT = 2,
    MP_BC_FORMAT_OFFSET = 3,


MP_BC_MASK_EXTRA_BYTE = 0x9E


def mp_opcode_format(buf: bytearray, ip: int, count_var_uint: bool) -> (BcFormat, int):
    opcode = buf[ip]
    ip_start = ip
    f = BcFormat((0x000003A4 >> (2 * ((opcode) >> 4))) & 3)
    extra_byte = ((opcode & MP_BC_MASK_EXTRA_BYTE) == 0)
    match f:
        case BcFormat.MP_BC_FORMAT_QSTR:
            ip += 3
        case BcFormat.MP_BC_FORMAT_VAR_UINT:
            ip += 1
            if count_var_uint:
                while buf[ip] & 0x80 != 0:
                    ip += 1
                ip += 1
        case BcFormat.MP_BC_FORMAT_OFFSET:
            extra_byte = ((opcode & MP_BC_MASK_EXTRA_BYTE) == 0)
            ip += 3
    if extra_byte:
        ip += 1
    return f, ip - ip_start


class BytecodeBuffer:
    def __init__(self, size: int):
        self.buf = bytearray(size)
        self.i = 0

    def is_full(self):
        return self.i == len(self.buf)

    def append(self, b: int):
        # l = len(b)
        # self.buf[self.i:self.i+l] = b
        self.buf[self.i] = b
        self.i += 1


@dataclass
class MpyHeader:
    version: MpyVersion = None
    features: int = 0
    small_int_bits: int = 0

    def __init__(self, data: bytes):
        if data[0] != ord('M'):
            raise InvalidMpyMagicException
        self.version = MpyVersion(data[1])
        self.features = data[2]
        self.small_int_bits = data[3]


@dataclass
class QStrWindow:
    size: int
    window: list[int]

    def __init__(self, size: int):
        self.size = size
        self.window = []

    def push(self, val: int):
        self.window.insert(0, val)

    def access(self, idx: int) -> int:
        return self.window.pop(idx)


@dataclass
class RawCode:
    escaped_names = set()

    rcType: MpCodeType
    data: bytes
    qstrs: list[int]
    objs: list[Any]
    children: list["RawCode"]
    prelude: Any

    def __init__(self, rcType: MpCodeType, data: bytes, qstrs: list[int], objs: list[Any], children: list["RawCode"], prelude: Any):
        self.rcType = rcType
        self.data = data
        self.qstrs = data
        self.objs = objs
        self.children = children
        self.prelude = prelude

            # self.simple_name = self._unpack_qstr(self.ip2)
            # self.source_file = self._unpack_qstr(self.ip2 + 2)
            # self.line_info_offset = self.ip2 + 4
            # print(self.simple_name)
            # print(self.source_file)

    @staticmethod
    def read_from_file(file: BinaryIO, window: QStrWindow) -> "RawCode":
        return None


@dataclass
class MpyFile:
    filename: str = None
    file: BinaryIO = None
    header: MpyHeader = None

    rawCode: RawCode = None
    window: QStrWindow = None

    def __init__(self, filename: str):
        self.filename = filename
        self.file = open(filename, 'rb')
        self.header = MpyHeader(self.file.read(4))

        if self.header.version == MpyVersion.MPY_VERSION_5:
            self.window = QStrWindow(self.read_uint())

    def read_byte(self) -> int:
        return ord(self.file.read(1))

    def read_bytes(self, n: int = 1) -> bytes:
        return self.file.read(n)

    def read_uint(self) -> int:
        i = 0
        while True:
            b = self.read_byte()
            i = (i << 7) | (b & 0x7F)
            if b & 0x80 == 0:
                break
        return i

    def _unpack_qstr(self, buf: bytes, ip: int) -> QStrType:
        qst = buf[ip] | buf[ip+1] << 8
        return global_qstrs[qst]

    def read_qstr(self) -> int:
        ln = self.read_uint()
        if ln == 0:
            # static qstr
            return self.read_byte()
        if ln & 1:
            # qstr in table
            return self.window.access(ln >> 1)
        data = str(self.read_bytes(ln >> 1), "utf8")
        global_qstrs.append(QStrType(data))
        self.window.push(len(global_qstrs) - 1)
        return len(global_qstrs) - 1

    def read_obj(self) -> Any:
        obj_type = self.read_bytes()
        if obj_type == b"e":
            return Ellipsis
        else:
            buf = self.read_bytes(self.read_uint())
            match obj_type:
                case b"s":
                    return str(buf, "utf-8")
                case b"b":
                    return bytes(buf)
                case b"i":
                    return int(str(buf, "ascii"), 10)
                case b"f":
                    return float(str(buf, "ascii"))
                case b"c":
                    return complex(str(buf, "ascii"))

    def read_qstr_and_pack(self, buf: BytecodeBuffer):
        qstr = self.read_qstr()
        buf.append(qstr & 0xFF)
        buf.append(qstr >> 0xFF)

    def read_prelude(self, buf: BytecodeBuffer):
        (
            n_state,
            n_exc_stack,
            scope_flags,
            n_pos_args,
            n_kwonly_args,
            n_def_pos_args,
        ) = self.read_prelude_sig(buf)

        n_info, n_cell = self.read_prelude_size(buf)
        self.read_qstr_and_pack(buf)  # simple name
        self.read_qstr_and_pack(buf)  # source file
        for _ in range(n_info - 4 + n_cell):
            buf.append(self.read_byte())
        return n_state, n_exc_stack, scope_flags, n_pos_args, n_kwonly_args, n_def_pos_args, n_info, n_cell

    # No clue; copied from mpy-tool.py
    def read_prelude_size(self, buf: BytecodeBuffer) -> (int, int):
        I = 0
        C = 0
        n = 0
        while True:
            z = self.read_byte()
            buf.append(z)
            # xIIIIIIC
            I |= ((z & 0x7E) >> 1) << (6 * n)
            C |= (z & 1) << n
            if not (z & 0x80):
                break
            n += 1
        return I, C

    # No clue; copied from mpy-tool.py
    def read_prelude_sig(self, buf: BytecodeBuffer) -> (int, int, int, int, int, int):
        z = self.read_byte()
        buf.append(z)

        # xSSSSEAA
        S = (z >> 3) & 0xF
        E = (z >> 2) & 0x1
        F = 0
        A = z & 0x3
        K = 0
        D = 0
        n = 0
        while z & 0x80:
            z = self.read_byte()
            buf.append(z)
            # xFSSKAED
            S |= (z & 0x30) << (2 * n)
            E |= (z & 0x02) << n
            F |= ((z & 0x40) >> 6) << n
            A |= (z & 0x4) << n
            K |= ((z & 0x08) >> 3) << n
            D |= (z & 0x1) << n
            n += 1
        S += 1
        return S, E, F, A, K, D

    def read_bytecode(self, buf: BytecodeBuffer):
        while not buf.is_full():
            op = self.read_byte()
            buf.append(op)
            f, sz = mp_opcode_format(buf.buf, buf.i - 1, False)
            sz -= 1
            match f:
                case BcFormat.MP_BC_FORMAT_QSTR:
                    self.read_qstr_and_pack(buf)
                    sz -= 2
                case BcFormat.MP_BC_FORMAT_VAR_UINT:
                    x = self.read_byte()
                    buf.append(x)
                    while x & 0x80:
                        x = self.read_byte()
                        buf.append(x)
            for _ in range(sz):
                buf.append(self.read_byte())

    def read_raw_code(self) -> RawCode:
        type_len = self.read_uint()
        rcType = MpCodeType((type_len & 3) + MpCodeType.MP_CODE_BYTECODE)
        rcLen = type_len >> 2
        buf = BytecodeBuffer(rcLen)

        match rcType:
            case MpCodeType.MP_CODE_BYTECODE:
                prelude = self.read_prelude(buf)
                self.read_bytecode(buf)
            case _:
                raise NotImplementedError

        qstrs = []
        objs = []
        children = []

        match rcType:
            case MpCodeType.MP_CODE_BYTECODE:
                # load constant table
                n_obj = self.read_uint()
                n_rc = self.read_uint()
                print("Reading qstr...")
                qstrs = [self.read_qstr() for _ in range(prelude[3] + prelude[4])]
                print(qstrs)
                print("Reading constants...")
                objs.extend([self.read_obj() for _ in range(n_obj)])
                print(objs)
                print("Reading children...")
                # children = [self.read_raw_code() for _ in range(n_rc)]
                print(children)

                print(self._unpack_qstr(buf.buf, 0))
                ip2 = prelude[-2] + prelude[-1]
                print(self._unpack_qstr(buf.buf, ip2))

                return RawCode(rcType, buf.buf, qstrs, objs, children, prelude)
            case _:
                return None

    def parse(self):
        self.rawCode = self.read_raw_code()
