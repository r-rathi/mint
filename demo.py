from mint.miny import *
import re

#-------------------------------------------------------------------------------
class Demo(Module):
    @model
    def rtl(self, io):
        a = instance     .A
        b = instance [2] .B

        CLK_IF = interface .clk_if

        io == CLK_IF/'{n}' == a
        io == CLK_IF/'{n}' == b

        A_IF   = interface     .a_if
        AB_IF  = interface [2] .ab_if

        io == A_IF == a == AB_IF == b

        si, so = wire    () * 2
        smid   = wire [2]()
        io > si > a > smid[0]
        smid[0] > b[0]/'si', b[0]/'so' > smid[1]
        smid[1] > b[1]/'si', b[1]/'so' > so > io

        return locals()

#-------------------------------------------------------------------------------
class InterfaceFromString(Interface):
    signals = """
        """

    @model
    def rtl(self, a, b):
        signals = []
        for line in re.split(r'\n', self.signals):
            line = line.lstrip(' ')
            line = line.rstrip(' ')

            if line == "": continue

            op, sig, size = re.split(r'\s+', line)

            w = wire[int(size)](sig)

            if op == '>':
                a > w > b
            elif op == '<':
                a < w < b
            elif op == '<>':
                a <> w <> b
            else:
                raise Error("Invalid op")

        return locals()

class InterfaceFromTable(Interface):
    table = """
    | dir | signal | width | description |
    | --- | ----   | ----- | ----------- |
    |     |        |       |             |
        """

    @model
    def rtl(self, a, b):
        signals = []
        for line in re.split(r'\n', self.signals):
            line = line.lstrip(' ')
            line = line.rstrip(' ')

            if line == "": continue

            op, sig, size = re.split(r'\s+', line)

            w = wire[int(size)](sig)

            if op == '>':
                a > w > b
            elif op == '<':
                a < w < b
            elif op == '<>':
                a <> w <> b
            else:
                raise Error("Invalid op")

        return locals()

class clk_if(Interface):
    @model
    def rtl(self, a, b):
        clk = wire()
        reset = wire()

        a > clk > b
        a > reset >b

        return locals()

class a_if(InterfaceFromString):
    signals = """
        > cmd       2
        < resp      2
        """

class ab_if(InterfaceFromString):
    signals = """
        >  address   8
        <> data      8
        >  ren       1
        >  wen       0
        """

class tab_if(InterfaceFromTable):
    table = """
    | dir | signal | width | description |
    | --- | ----   | ----- | ----------- |
    | >   | req    | 1     | request     |
    | <   | resp   | 1     | response    |
    | >   | cmd    | 2     | command:    |
    |     |        |       | 00: foo     |
    |     |        |       | 01: bar     |
    |     |        |       | 10: do      |
    |     |        |       | 11: dat     |
    """
#-------------------------------------------------------------------------------
if __name__ == '__main__':

    print "-" * 80
    Demo(model='rtl').generate_verilog()
    print "-" * 80
