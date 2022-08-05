#!/usr/bin/env python3
import io
import sys
from dataclasses import dataclass
from pprint import pprint


def run_mpy(filename: str, op: str = "freeze"):

    def do_run(args: list[str]) -> str:
        from micropython.tools.mpy_tool import main as mpy_tool

        newio = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = newio
        # old_stderr = sys.stderr
        # sys.stderr = newio

        mpy_tool(args)

        sys.stdout = old_stdout
        # sys.stderr = old_stderr
        return newio.getvalue()

    match op.lower():
        case "dump":
            return do_run(["-d", filename])
        case "freeze":
            return do_run(["-f", filename])
        case x:
            print(f"Unknown operation '{x}'")
            return do_run(["-h"])


from mpy import MpyFile, MpyVersion


@dataclass
class uDis:
    mpy: MpyFile = None

    def __init__(self, filename: str):
        print(f"Running uDis on {filename}")
        self.mpy = MpyFile(filename)

    def run(self):
        match self.mpy.header.version:
            case MpyVersion.MPY_VERSION_5:
                print(f"Version: 5")
            case _:
                raise NotImplementedError

        self.mpy.parse()
        pprint(self)


from micropython.tools.mpy_tool import RawCode, read_mpy, get_qstrs


def print_bytecode(bc: bytes, depth: int):
    from micropython.tools.mpy_tool import extract_prelude

    def read_prelude_size(b: bytes):
        i = 0
        I = 0
        C = 0
        n = 0
        while True:
            z = b[i]
            i += 1
            # xIIIIIIC
            I |= ((z & 0x7E) >> 1) << (6 * n)
            C |= (z & 1) << n
            if not (z & 0x80):
                break
            n += 1
        return I, C
    c = "----"
    # print(extract_prelude(bc, 0))
    # print(read_prelude_size(bc))

    skip = extract_prelude(bc, 0)[0]
    print(f"{c * depth}    {bc[skip:]}")


def print_raw_code(rc: RawCode, q, depth: int = 0):
    c = "----"
    print(f"{c * depth}{rc.code_kind_str[rc.code_kind]} {{")
    print(f"{c * depth}  lineno:      {rc.line_info_offset}")
    print(f"{c * depth}  simple_name: {rc.simple_name.str}")
    print(f"{c * depth}  source_file: {rc.source_file.str}")
    print(f"{c * depth}  qstrs:")
    for x in rc.qstrs:
        print(f"{c*depth}    {q[x][1]}")
    print(f"{c * depth}  const:")
    for x in rc.objs:
        print(f"{c*depth}    {x.encode()}")
    print(f"{c * depth}  bytecode:")
    # print(f"{c * depth}    {rc.bytecode}")
    print_bytecode(rc.bytecode, depth)
    print(f"{c * depth}  children:")
    for x in rc.raw_codes:
        print_raw_code(x, q, depth+1)
    print(f"{c * depth}}}")


def main():
    filename = "./tests/ben_player.mpy"
    # filename = "./tests/chomper_app.mpy"
    # print(run_mpy(filename, op="freeze"))
    # uDis(filename).run()

    rawcode = read_mpy(filename)
    q = get_qstrs({})
    # print(q)
    print_raw_code(rawcode, q, 0)
    # pprint(vars(rawcode.raw_codes[0]))


if __name__ == "__main__":
    main()
