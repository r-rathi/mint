#-------------------------------------------------------------------------------
import collections
import copy
import warnings
import inspect
import logging
import math

#-------------------------------------------------------------------------------
class MintError(Exception): pass
class MintIndexError(MintError): pass
class MintValueError(MintError): pass
class MintConnectionError(MintError): pass
class MintModelDoesNotExist(MintError): pass

#-------------------------------------------------------------------------------
class Dir:
    I = 'input'
    O = 'output'
    IO = 'inout'
    ANY = '_any_dir_'

class Default:
    port_dir = Dir.ANY
    scalar_port_template = '{I}_{n}'
    vector_port_template = '{i}_{n}'
    net_template = '{I}_{n}'
    net_template = '{I}_{n}'

#-------------------------------------------------------------------------------
class Net(object):
    """ Base class for net types. """
    def _handle_cmp_ops(self, other, op, dir):
        if isinstance(other, ModInstBase):
            other.bind_net(self, dir=dir)
            return True

        raise TypeError("unsupported operand type(s) for %s: '%s' and '%s'" %
                        (op, type(self), type(other)))

    def __ne__(self, other):
        return self._handle_cmp_ops(other, '<>', Dir.IO)

    def __gt__(self, other):
        return self._handle_cmp_ops(other, '>', Dir.I)

    def __lt__(self, other):
        return self._handle_cmp_ops(other, '<', Dir.O)

    def __mul__(self, other):
        if isinstance(other, int):
            clones = []
            for i in range(other):
                clone = copy.copy(self)
                clone.parent = clone
                clones.append(clone)
            return clones
        else:
            return NotImplemented

    def __rmul__(self, other):
        return self.__mul__(other)

class Wire(Net):
    def __init__(self, name=None, size=None, indices=None, parent=None):
        """
        Initialize the Wire instance.
        - name = base name for the wire
        - size = None for scalar, int for vector.
        - indices = tuple of indices, but size takes precedence if defined.
        - parent points to parent wire for slices.
        """
        self._name = name

        if size is not None:
            self.indices = tuple(range(size))
        else:
            self.indices = indices  # 'None' for scalar

        self.parent = parent or self

        # Template used for full/formatted name
        self.template = "{name}"

    def __call__(self, name=None):
        """
        Additional initializations for the Wire instance.
        - name = base name for the wire
        """
        self.name = name or self.name
        return self

    @property
    def name(self):
        return self._name or self.parent._name

    @name.setter
    def name(self, val):
        self._name = val

    @property
    def fname(self):
        """ Return full/formatted name """
        return self.template.format(name=self.name)

    def formatted_repr(self, fmt0="{name}",
                             fmt1="{name}[{index}]",
                             fmt2="{name}[{index}]"):
        """ Return formatted representation
            - fmt0 : format for scalars
            - fmt1 : format for 1 bit vectors
            - fmt2 : format for >= 2 bit vectors
            Following replacement strings can be specified:
            - name, index, msb, lsb
        """
        name = self.fname
        #name = self.name.format(**kwargs)

        if self.indices is None:
            index = msb = lsb = ''
            return fmt0.format(name=name, index=index, msb=msb, lsb=lsb)
        elif len(self.indices) == 1:
            index = self.indices[0]
            msb = lsb = index
            return fmt1.format(name=name, index=index, msb=msb, lsb=lsb)
        else:
            lsb = self.indices[0]
            msb = self.indices[-1]
            index = "%s:%s" % (msb, lsb)
            return fmt2.format(name=name, index=index, msb=msb, lsb=lsb)

    def __getitem__(self, key):
        """ Verilog like indexing syntax is used:
            [index]   => python [index]
            [msb:lsb] => python [lsb:msb+1]
        """
        if self.indices is None:
            raise MintIndexError("scalar wire is not indexable")

        valid_range = range(len(self.indices))

        if isinstance(key, int):
            if key not in valid_range:
                raise MintIndexError("wire index out of range")

            indices = (self.indices[key],)

        elif isinstance(key, slice):
            msb, lsb, step = key.start, key.stop, key.step
            if msb is None: msb = valid_range[-1]
            if lsb is None: lsb = valid_range[0]

            if msb not in valid_range or lsb not in valid_range:
                raise MintIndexError("wire index out of range")

            if msb < lsb:
                raise MintIndexError("msb less than lsb")

            indices = self.indices[lsb : msb + 1 : step]

        return Wire(indices=indices, parent=self.parent)

    def __len__(self):
        if self.indices is None:
            return 1
        else:
            return len(self.indices)

    def __repr__(self):
        return "Wire(%s)" % self.formatted_repr()

class Const(Net):
    def __init__(self, size, val, fmt='hex'):
        self.size = size
        if val < 0 or val >= 2**size:
            raise MintValueError("constant value out of range")
        self.val = val
        self.fmt = fmt

    #@property
    #def name(self):
    #    return self.formatted_repr()

    def formatted_repr(self, fmt=None):
        fmt = fmt or self.fmt

        if fmt == 'bin':
            return "{size}'b{0:0>{width}b}".format(self.val, size=self.size,
                                                   width=self.size)
        elif fmt == 'hex':
            width = int(math.ceil(self.size/4))
            return "{size}'h{0:0>{width}x}".format(self.val, size=self.size,
                                                   width=width)
        else:
            return "{size}'d{0}".format(self.val, size=self.size)

    def __len__(self):
        return self.size

    def __repr__(self):
        return "Const(%s)" % self.formatted_repr()

class Concat(Net):
    def __init__(self, nets):
        self.nets = nets

    #@property
    #def name(self):
    #    return self.formatted_repr()

    @property
    def wires(self):
        return [wire for wire in self.nets if isinstance(wire, Wire)]

    def formatted_repr(self):
        return "{%s}" % ', '.join([net.formatted_repr() for net in self.nets])

    def __len__(self):
        size = 0
        for net in self.nets:
            size += len(net)
        return size

    def __repr__(self):
        return "Concat(%s)" % self.formatted_repr()

#-------------------------------------------------------------------------------
class InstBase(object):
    def __div__(self, other):
        " Supports inst_exp/template expressions "
        if isinstance(other, str):
            templatized = self.templatize(other)
        else:
            raise TypeError('unsupported operand type(s) for /: %s and %s' %
                            (type(self), type(other)))

        return templatized

class InstScalar(InstBase):
    def __init__(self, name=None, index=None):
        self.name = name

        # This would be set if part of a vector
        self.index = index

        # Set by obj/template expression.
        self.template = None

        # Which model to build
        self.model = None

        # Set to True if this instance is a port
        self.isport = False

    def formatted_repr(self, fmt0="{name}",
                             fmt1="{name}[{index}]"):
        """ Return formatted representation
            - fmt0 : format for scalars
            - fmt1 : format for 1 bit vectors (part of vector)
            Following replacement strings can be specified:
            - name, index
        """
        if self.index is None:
            return fmt0.format(name=self.name, index=self.index)
        else:
            return fmt1.format(name=self.name, index=self.index)

    def __iter__(self):
        return iter([self])

    def __len__(self):
        return 1

    def __repr__(self):
        return "%s(%s, %s)" % (self.__class__.__name__, self.formatted_repr(),
                               self.template)

class InstList(InstBase):
    def __init__(self, inst_scalars, name=None):
        self.scalars = []
        index = 0
        for inst_scalar in inst_scalars:
            inst_scalar.index = index
            index += 1
            self.scalars.append(inst_scalar)

        self._name = name

        # Set by obj/template expression.
        self.template = None

        # Which model to build
        self._model = None

        # Set to True if this instance is a port
        self.isport = False

    @property
    def name(self):
        # Confirm all scalars have same name
        assert all(self._name == scalar.name for scalar in self),\
               "all scalars should have same name: %s" % self
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        for scalar in self.scalars:
            scalar.name = value

    #@property
    #def template(self):
    #    return self._template

    @property
    def model(self):
        # Confirm all scalars have same model
        assert all(self._model == scalar.model for scalar in self),\
               "all scalars should have same model: %s" % self
        return self._model

    @model.setter
    def model(self, value):
        for scalar in self.scalars:
            scalar.model = value
        self._model = value

    def make(self, model=None):
        self.model = model or self.model
        for scalar in self:
            scalar.make(self.model)

    def __getitem__(self, key):
        """ Verilog like indexing syntax is used:
            [index]   => python [index]
            [msb:lsb] => python [lsb:msb+1]
        """
        valid_range = range(len(self.scalars))

        if isinstance(key, int):
            if key not in valid_range:
                raise MintIndexError("inst index out of range")

            return self.scalars[key]

        elif isinstance(key, slice):
            msb, lsb, step = key.start, key.stop, key.step
            if msb is None: msb = valid_range[-1]
            if lsb is None: lsb = valid_range[0]

            if msb not in valid_range or lsb not in valid_range:
                raise MintIndexError("inst index out of range")

            if msb < lsb:
                raise MintIndexError("msb less than lsb")

            sliced = copy.copy(self)
            sliced.scalars = self.scalars[lsb : msb + 1 : step]
            return sliced

    def __iter__(self):
        return iter(self.scalars)

    def __len__(self):
        return len(self.scalars)

    def __contains__(self, value):
        return value in self.scalars

    def __repr__(self):
        #r = "InstList("
        r = "%s(%s)[" % (self.__class__.__name__, self.name)
        for i, e in enumerate(self.scalars):
            if i: r += ', ' + str(e)
            else: r += str(e)
        r += "]"
        return r

#-------------------------------------------------------------------------------
class ModInstBase(object):
    def _handle_cmp_ops(self, other, op, dir):
        if isinstance(other, IntfInstBase):
            self.bind_intf(other, modport=0, dir_filter=dir)
            return True

        if isinstance(other, Net):
            self.bind_net(other, dir=dir)
            return True

        raise TypeError("unsupported operand type(s) for %s: '%s' and '%s'" %
                        (op, type(self), type(other)))

    def __eq__(self, other):
        return self._handle_cmp_ops(other, '==', Dir.ANY)

    def __ne__(self, other):
        return self._handle_cmp_ops(other, '<>', Dir.IO)

    def __gt__(self, other):
        return self._handle_cmp_ops(other, '>', Dir.O)

    def __lt__(self, other):
        return self._handle_cmp_ops(other, '<', Dir.I)

class ModInstScalar(InstScalar, ModInstBase):
    # InsGen.__getattr__ expects "obj" (module in this case) as first arg
    def __init__(self, module, name=None, index=None):
        super(ModInstScalar, self).__init__(name, index)
        self.module = module

        # Bind relationships with interfaces represented as Interface Pins
        self.intfpins = []

        # Bind relationships with wires represented as Pins
        self.pins = []

    def templatize(self, template):
        # Important - we make a copy, not a deepcopy. This ensures that the
        # copy's instance variables point to the same object as the original
        templatized = copy.copy(self)
        templatized.template = template
        return templatized

    def bind_intf(self, intfinst, modport, dir_filter):
        for intfinst_scalar in intfinst:
            intfpin = IntfPin(modinst=self, intfinst=intfinst_scalar,
                              modport=modport, dir_filter=dir_filter,
                              template=self.template)
            #print 'IntfPin:', intfpin
            self.intfpins.append(intfpin)

    def bind_net(self, net, dir):
        pin = Pin(dir=dir, inst=self, net=net, name=self.template,
                  intfinst='_IF_')
        self.pins.append(pin)

    def make(self, model=None):
        self.model = model or self.model
        self.module.make(self.model)

    def get_pins(self):
        pins = []
        for intfpin in self.intfpins:
            pins += intfpin.get_pins()
        pins += self.pins
        return pins

    def __repr__(self):
        return "ModInstScalar(%s, %s, %s)" % (self.formatted_repr(),
                                              self.module.name, self.template)

class ModInstList(InstList, ModInstBase):
    def templatize(self, template):
        scalars = []
        for scalar in self:
            scalars += [scalar.templatize(template)]
        templatized = copy.copy(self)
        templatized.scalars = scalars
        templatized.template = template
        return templatized

    def bind_intf(self, intfinst, modport, dir_filter):
        #if len(intfinst) == 1:
        if isinstance(intfinst, IntfInstScalar):
            # v - s
            for modinst_scalar in self:
                intfpin = IntfPin(modinst=modinst_scalar, intfinst=intfinst,
                                  modport=modport, dir_filter=dir_filter,
                                  template=self.template)
                #print 'IntfPin:', intfpin
                modinst_scalar.intfpins.append(intfpin)
        else:
            # v - v
            if len(self) != len(intfinst):
                raise MintConnectionError("vector sizes differ: %s(%s), %s(%s)" %
                    (self, len(self), intfinst, len(intfinst)))

            for modinst_scalar, intfinst_scalar in zip(self, intfinst):
                intfpin = IntfPin(modinst=modinst_scalar,
                                  intfinst=intfinst_scalar,
                                  modport=modport, dir_filter=dir_filter,
                                  template=self.template)
                #print 'IntfPin:', intfpin
                modinst_scalar.intfpins.append(intfpin)

    def bind_net(self, net, dir):
        for modinst_scalar in self:
            pin = Pin(dir=dir, inst=modinst_scalar, net=net, name=self.template)
            modinst_scalar.pins.append(pin)

#-------------------------------------------------------------------------------
class IntfInstBase(object):
    def _handle_cmp_ops(self, other, op, dir_filter):
        if isinstance(other, ModInstBase):
            other.bind_intf(self, modport=1, dir_filter=dir_filter)
            return True

        raise TypeError("unsupported operand type(s) for %s: '%s' and '%s'" %
                        (op, type(self), type(other)))

    def __eq__(self, other):
        return self._handle_cmp_ops(other, '==', Dir.ANY)

    def __ne__(self, other):
        return self._handle_cmp_ops(other, '<>', Dir.IO)

    def __gt__(self, other):
        return self._handle_cmp_ops(other, '>', Dir.I)

    def __lt__(self, other):
        return self._handle_cmp_ops(other, '<', Dir.O)

class IntfInstScalar(InstScalar, IntfInstBase):
    # InsGen.__getattr__ expects "obj" (interface in this case) as first arg
    def __init__(self, interface, name=None, index=None):
        super(IntfInstScalar, self).__init__(name, index)
        self.interface = interface

    def templatize(self, template):
        self.template = template
        return self

    def make(self, model=None):
        self.model = model or self.model
        self.interface.make(self.model)

    def __repr__(self):
        return "IntfInstScalar(%s, %s, %s)" % (self.formatted_repr(),
                                               self.interface.name, self.template)

class IntfInstList(InstList, IntfInstBase):
    def templatize(self, template):
        for scalar in self:
            scalar.template = template
        return self

#-------------------------------------------------------------------------------
class Pin(object):
    """
    P = port name, dir
    I = inst/modport
    N = net
    PIN = I.P(N) = inst I has port P that connects to net N
    """

    def __init__(self, dir, inst, net, name=None, intfinst=None):
        self.dir = dir
        self.modinst = inst
        self.net = net

        # This may be defined by "inst/'name'" expression, else net name
        self._name = name

        self.intfinst = intfinst

        # Template used for full/formatted name
        self.template = "{name}"

    @property
    def name(self):
        if self._name:
            return self._name
        
        try:
            return self.net.name
        except AttributeError:
            # This will happen if net is a Const or Concat and port name is not
            # specified
            raise MintConnectionError("port name not specified for '%s' and '%s'" %
                                     (self.inst, self.net))

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def fname(self):
        """ Return full/formatted name """
        return self.template.format(name=self.name)

    def __repr__(self):
        r = '{self.dir}: {self.modinst.name}.{self.fname}({self.net.fname})'
        return r.format(self=self)


class IntfPin(object):
    """
    Interface Pin binds a modinst to a view/filter of the interface instance
    P = port template, dir
    I = inst
    N = interface inst, modport
    PIN = I.P(N) = inst I has port P that connects to net N
    """

    def __init__(self, modinst, intfinst, modport, dir_filter, template=None):
        self.modinst = modinst
        self.intfinst = intfinst
        self.modport = modport # this could int(position) or str(name)
        self.dir_filter = dir_filter
        # This may be defined by "inst/template" expression, else default
        self._template = template

    #@property
    #def name(self):
    #    return self.intfinst.name   # ???

    @property
    def template(self):
        if self._template is not None:
            return self._template
        else:
            if self.modinst.index is None:
                return Default.scalar_port_template
            else:
                return Default.vector_port_template

    #@template.setter
    #def template(self, value):
    #    self._template = value

    def get_pins(self):
        interface = self.intfinst.interface

        # TODO: consider replacing with named tuple
        if isinstance(self.modport, int):
            modport_name = interface.port_at_pos[self.modport]
        else:
            modport_name = self.modport
        modport = interface.module_instances[modport_name]

        # Get the pins form the modport that match the direction criteria and
        # compute the port and wire names based on naming rules
        pins = []
        #for pin in modport.pins:
        for pin in modport.get_pins():
            if self.dir_filter in (Dir.ANY, pin.dir):
                i = self.intfinst.name
                k = self.intfinst.formatted_repr(fmt0="", fmt1="{index}")
                I = self.intfinst.formatted_repr(fmt0="{name}",
                                                 fmt1="{name}{index}")

                # Inplace pin template change
                pin_template = self.template
                pin.template = pin_template.format(i=i, k=k, I=I, n='{name}')

                # Inplace wire template change
                net_template = self.intfinst.template or Default.net_template
                if hasattr(pin.net, 'template'):
                    pin.net.template = net_template.format(i=i, k=k, I=I, n='{name}')

                pin.intfinst = I
                pins.append(pin)
        return pins

    def __repr__(self):
        r = '{self.dir_filter}: {self.modinst.name}.{self.name}'
        r += '({self.intfinst.name}.{self.modport})'
        return r.format(self=self)

#-------------------------------------------------------------------------------
class MintObject(object):
    def __init__(self, name=None, model=None):
        self._name = name or self.__class__.__name__
        self.model = model

        self.module_instances = collections.OrderedDict()
        self.interface_instances = collections.OrderedDict()
        self.port_at_pos = []
        # TODO add shadow dict for self.intstances

        if model:
            self.make(model)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    def add(self, obj):
        if obj.name is None:
            raise MintValueError, "obj %s has no name" % obj

        if isinstance(obj, ModInstBase):
            self.module_instances[obj.name] = obj
        elif isinstance(obj, IntfInstBase):
            self.interface_instances[obj.name] = obj

    def make(self, model):
        try:
            model_method = getattr(self, model)
        except AttributeError:
            raise MintModelDoesNotExist("'%s' of '%s'" % (model, self.name))

        model_method(self)

    def get_module_instances(self, flatten=False):
        mod_insts = []
        for mod_inst in self.module_instances.values():
            if isinstance(mod_inst, ModInstList):
                if flatten == True:
                    for mod_inst_scalar in mod_inst:
                        mod_insts += [mod_inst_scalar]
                else:
                    mod_insts += [mod_inst]
            else:
                mod_insts += [mod_inst]
        return mod_insts

    def get_interface_instances(self, flatten=False):
        intf_insts = []
        for intf_inst in self.interface_instances.values():
            if isinstance(intf_inst, IntfInstList):
                if flatten == True:
                    for intf_inst_scalar in intf_inst:
                        intf_insts += [intf_inst_scalar]
                else:
                    intf_insts += [intf_inst]
            else:
                intf_insts += [intf_inst]
        return intf_insts

class Module(MintObject): pass
class Interface(MintObject): pass
