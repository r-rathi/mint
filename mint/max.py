#-------------------------------------------------------------------------------
import collections
import sys

import min

#-------------------------------------------------------------------------------
class Registry(object):
    Entry = collections.namedtuple('Entry', 'obj, type')
    _registry = collections.OrderedDict()
    _auto_enabled = {}

    #def __init__(self):
    #    Registry._registry = collections.OrderedDict()

    @classmethod
    #def register(cls, obj):
    def register(cls, obj, obj_name, obj_type):
        obj_name = obj_name or obj.name
        obj_type = obj_type or type(obj)
        if obj_name in cls._registry:
            raise ValueError("'%s' of type '%s' is already registered" %
                             (obj_name, obj_type))
        else:
            #Registry._registry[obj_name] = obj
            #logging.info("Registering %s of type %s" % (obj_name, obj_type))
            Registry._registry[obj_name] = Registry.Entry(obj, obj_type)

    @classmethod
    def get(cls, obj_name, obj_type):
        try:
            obj, _type = cls._registry[obj_name]
        except KeyError:
            raise KeyError("'%s' is not registered" % obj_name)

        #if not isinstance(obj, obj_type):
        if _type != obj_type:
            raise KeyError("'%s' is already registered as a different type"
                             " '%s'" % (obj_name, _type))

        return obj

    @classmethod
    def get_or_create(cls, obj_name, obj_type):
        try:
            #obj = cls._registry[obj_name]
            obj, _type = cls._registry[obj_name]
        except KeyError:
            if True:
            #if obj_type in cls._auto_enabled:
                #warnings.warn("auto creating '%s' of type '%s'" % (obj_name,
                #                                                   obj_type))
                # Auto create, and register
                #obj = obj_type(obj_name)
                obj = type(obj_name, (obj_type,), {})
                #TODO: maybe we should not be registering autocreated classes?
                #cls.register(obj, obj_name, obj_type)
                return obj
            else:
                # Auto creation is not enabled
                raise KeyError("'%s' is not registered" % obj_name)

        #if not isinstance(obj, obj_type):
        #if _type != obj_type:
        #    raise KeyError("'%s' is already registered as a different type"
        #                     " '%s'" % (obj_name, _type))

        return obj

    @classmethod
    def deregister(cls, obj_name, obj_type):
        try:
            #obj = cls._registry[obj_name]
            obj, _type = cls._registry[obj_name]
        except KeyError:
            raise KeyError("'%s' is not registered" % obj_name)

        #if not isinstance(obj, obj_type):
        if _type != obj_type:
            raise KeyError("'%s' is registered as a different type"
                             " '%s'" % (obj_name, _type))

        del(cls._registry[obj_name])

    @classmethod
    def enable_auto_creation_for(cls, obj_type):
        cls._auto_enabled[obj_type] = 1

    @classmethod
    def clear(cls):
        cls._registry = collections.OrderedDict()
        cls._auto_enabled = {}

#-------------------------------------------------------------------------------
class InstGen(object):
    def __init__(self, scalar_type, vector_type, instof_type=None):
        self.scalar_type = scalar_type
        self.vector_type = vector_type
        self.instof_type = instof_type

        self.registry = Registry() # all instances point to same data
        self.registry.enable_auto_creation_for(instof_type)

        self.indices = None

    def __getitem__(self, key):
        indices = []

        if isinstance(key, slice):
            start, stop, step = key.start, key.stop, key.step
            if step is not None:
                raise ValueError, "step should not be specified"
            if start is None:
                start = 0
            if start != 0:
                raise ValueError, "start should be 0"
            if stop is None:
                raise ValueError, "stop must be defined"
            indices = tuple(range(stop))
        elif isinstance(key, int):
            indices = tuple(range(key))
        else:
            indices = tuple(key)

        if self.indices is None:
            self.indices = indices
        else:
            # FIXME: how should multiple dimensions work?
            self.indices = (self.indices, indices)

        #print 'InstGen:', key, self.indices
        return  self

        # TODO: handle dictionary type

    def __call__(self, *args, **kwargs):
        indices = self.indices
        self.indices = None  # reset indices before next call

        if indices is None:
            #print "InstGen: %s(%s, %s)" % (self.scalar_type.__name__,
            #                               args, kwargs)
            return self.scalar_type(*args, **kwargs)
        else:
            vector = [self.scalar_type() for i in indices]
            #print "InstGen: %s(%s, %s, %s)" % (self.vector_type.__name__,
            #                                   vector, args, kwargs)
            return self.vector_type(vector, *args, **kwargs)


    def __getattr__(self, attr):
        try: # Return value if we have the attribute (regular access)
            return self.__dict__[attr]
        except KeyError: # else, delegate to Registry (magic)
            pass

        # Use attr as name of the object to be instantiated
        if self.instof_type is None:
            raise KeyError, "type of '%s' is unknown" % attr

        obj_name = attr
        obj_type = self.instof_type
        #print "InstGen: registry.get(%s, %s)" % (obj_name, obj_type)
        #obj = self.registry.get(obj_name, obj_type)
        obj_class = self.registry.get_or_create(obj_name, obj_type)
        #obj = obj_class()

        indices = self.indices
        self.indices = None  # reset indices before next call

        if indices is None:
            #print "InstGen: %s(%s)" % (self.scalar_type.__name__,
            #                               obj_name)
            return self.scalar_type(obj_class())
        else:
            vector = [self.scalar_type(obj_class()) for i in indices]
            #print "InstGen: %s(%s)" % (self.vector_type.__name__, vector)
            return self.vector_type(vector)

class ModportWireGen(object):
    def __init__(self, scalar_type, vector_type):
        self.scalar_type = scalar_type
        self.vector_type = vector_type
        self.indices = None

    def __getitem__(self, key):
        indices = []

        if isinstance(key, slice):
            start, stop, step = key.start, key.stop, key.step
            if step is not None:
                raise ValueError, "step should not be specified"
            if start is None:
                start = 0
            if start != 0:
                raise ValueError, "start should be 0"
            if stop is None:
                raise ValueError, "stop must be defined"
            indices = tuple(range(stop))
        elif isinstance(key, int):
            indices = tuple(range(key))
        else:
            indices = tuple(key)

        if self.indices is None:
            self.indices = indices
        else:
            # FIXME: how should multiple dimensions work?
            self.indices = (self.indices, indices)

        #print 'ModportWireGen:', key, self.indices
        return  self

        # TODO: handle dictionary type

    def __call__(self, *args, **kwargs):
        indices = self.indices
        self.indices = None  # reset indices before next call

        if indices is None:
            #print "ModportWireGen: %s(%s, %s)" % (self.scalar_type.__name__,
            #                               args, kwargs)
            return self.scalar_type(*args, **kwargs)
        else:
            vector = [self.scalar_type() for i in indices]
            #print "ModportWireGen: %s(%s, %s, %s)" % (self.vector_type.__name__,
            #                                   vector, args, kwargs)
            return self.vector_type(vector, *args, **kwargs)


    def __getattr__(self, attr):
        try: # Return value if we have the attribute (regular access)
            return self.__dict__[attr]
        except KeyError: # else treat attr as wire name to be generated
            pass

        indices = self.indices
        self.indices = None  # reset indices before next call

        if indices is None:
            #print "ModportWireGen: %s(%s)" % (self.scalar_type.__name__,
            #                               attr)
            return self.scalar_type(attr)
        else:
            vector = [self.scalar_type() for i in indices]
            #print "ModportWireGen: %s(%s)" % (self.vector_type.__name__, vector)
            return self.vector_type(vector, attr)

class WireGen(object):
    def __call__(self, *args, **kwargs):
        return min.Wire(*args, **kwargs)

    def __getitem__(self, key):
        indices = ()

        if isinstance(key, int):
            if key < 1:
                return min.Wire()
            else:
                return min.Wire(size=key)

        if isinstance(key, slice):
            msb, lsb, step = key.start, key.stop, key.step
            if msb is None:
                raise min.MINIndexError("msb not defined")
            if lsb:
                raise min.MINIndexError("lsb not equal to 0")
            if step is not None:
                raise min.MINIndexError("step not handled")
            return min.Wire(indices=tuple(range(msb + 1)))
        else:
            return min.Wire(indices=tuple(key))

#-------------------------------------------------------------------------------
class VerilogGenerator(object):
    def __init__(self, module):
        self.module = module
        self.port_pins = None
        self.reset_indent()

    def invert_dir(self, dir):
        if dir == 'input':
            return 'output'
        elif dir == 'output':
            return 'input'
        else:
            return dir

    def reset_indent(self):
        self.indent_stack = []
        self.indent_pos = 0
        self.new_line = True

    def next_line(self):
        print
        self.new_line = True

    def indent(self, by=1, width=4):
        self.indent_stack.append(self.indent_pos)
        self.indent_pos += by * width

    def dedent(self):
        self.indent_pos = self.indent_stack.pop()

    def emit(self, string, space=' '):
        if self.new_line:
            prefix = ' ' * self.indent_pos
            self.new_line = False
        else:
            prefix = space

        sys.stdout.write(prefix + string)

    def emitln(self, string, space=' '):
        self.emit(string, space)
        self.next_line()

    def generate_module(self):
        self.reset_indent()
        self.generate_header()
        self.generate_wires()
        self.generate_instances()
        self.generate_trailer()

    def generate_header(self):
        self.emit('module')
        self.emit(self.module.name)
        self.emit('(')
        self.generate_ports()
        self.emit(')')
        self.emitln(';', space='')

    def generate_trailer(self):
        self.emitln('endmodule')

    def generate_ports(self):
        port_insts = [inst for inst in self.module.get_module_instances() if
                     inst.isport]
        assert len(port_insts) == 1
        self.port_inst = port_insts[0]

        port_pins = self.port_inst.get_pins()

        uniq_port_pins = collections.OrderedDict()
        for pin in port_pins:
            uniq_port_pins[pin.net.fname] = pin

        # save for use in wires later
        self.port_pins = uniq_port_pins.values()

        if len(self.port_pins) == 0:
            return

        self.next_line()
        self.indent()

        self.generate_port(self.port_pins[0])

        for pin in self.port_pins[1:]:
            self.emitln(',', space='')
            self.generate_port(pin)

        self.next_line()
        self.dedent()

    def generate_port(self, pin):
        self.emit(self.invert_dir(pin.dir).ljust(6))

        index = pin.net.parent.formatted_repr(fmt0='',
                                              fmt1='[{msb}:{lsb}]',
                                              fmt2='[{msb}:{lsb}]')
        self.emit(index.rjust(8), space='')

        self.emit(' ' * 2, space='')
        self.emit(pin.net.fname, space='')

    def generate_wires(self):
        wire_list = []

        wires_by_intf = collections.OrderedDict() # wires grouped by intf
        wires_all = {} # for uniquifiying

        port_wires = [] # wires connected to module ports
        for port_pin in self.port_pins:
            port_wires.append(port_pin.net.fname)

        for mod_inst in self.module.get_module_instances(flatten=True):
            if mod_inst is self.port_inst: continue

            pins = mod_inst.get_pins()

            for pin in pins:
                if isinstance(pin.net, min.Const):    # skip constants
                    continue

                if isinstance(pin.net, min.Concat):
                    wires = pin.net.wires
                else:
                    wires = [pin.net]

                for wire in wires:
                    if wire.fname in port_wires:    # skip module ports
                        continue

                    if wire.fname not in wires_all:
                        wires_all[wire.fname] = True
                        if pin.intfinst in wires_by_intf:
                            wires_by_intf[pin.intfinst] += [wire]
                        else:
                            wires_by_intf[pin.intfinst] = [wire]

        for intfinst_name, wires in wires_by_intf.items():
            self.next_line()
            #self.emit('//')
            #self.emitln(intfinst_name)
            for wire in wires:
                self.generate_wire(wire)

    def generate_wire(self, wire):
        self.emit('wire'.ljust(10))

        index = wire.parent.formatted_repr(fmt0='', fmt1='', fmt2='[{index}]')
        self.emit(index.rjust(8), space='')

        self.emit(' ' * 2, space='')
        self.emit(wire.fname, space='')
        self.emitln(';', space='')

    def generate_instances(self):
        for inst in self.module.get_module_instances(flatten=True):
            if inst is self.port_inst: continue
            self.generate_instance(inst)

    def generate_instance(self, inst):
        self.next_line()
        self.emit(inst.module.name)
        self.emit(inst.formatted_repr(fmt0="{name}", fmt1="{name}{index}"))

        pins = inst.get_pins()

        if len(pins) == 0:
            self.emitln('();')
            return

        self.emit('(')
        self.next_line()
        self.indent()

        self.generate_portmap(pins[0])

        for pin in pins[1:]:
            self.emitln(',', space='')
            self.generate_portmap(pin)

        self.emitln(');', space='')
        self.next_line()
        self.dedent()

    def generate_portmap(self, pin):
        self.emit('.')
        self.emit(pin.fname.ljust(24), space='')
        self.emit('(')
        self.emit(pin.net.formatted_repr().ljust(24))
        self.emit(')')

#-------------------------------------------------------------------------------
if __name__ == '__main__':
    pass
