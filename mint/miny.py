import functools
import inspect
import logging
import warnings

import min
import max

from max import VerilogGenerator

#-------------------------------------------------------------------------------
# Export the "miny" language constructs
__all__ = ['Module', 'Interface', 'model',
           'instance', 'interface', 'wire', 'concat', 'const',
           'verilog']

#-------------------------------------------------------------------------------
def register(mod_intf_class):
    """
    Decorator for registering modules and interafaces
    """
    name = mod_intf_class.__name__

    if issubclass(mod_intf_class, min.Module):
        base = min.Module
    elif issubclass(mod_intf_class, min.Interface):
        base = min.Interface

    min.Registry.register(mod_intf_class, name, base)

    return mod_intf_class

class RegisterMeta(type):
    """
    Metaclass for registering modules and interafaces
    """
    def __new__(metacls, name, bases, attrs):
        # Create the new class
        new_cls = super(RegisterMeta, metacls).__new__(metacls, name, bases, attrs) 

        # Register it
        if issubclass(new_cls, min.Module):
            _type = min.Module
        elif issubclass(new_cls, min.Interface):
            _type = min.Interface
        # TODO: is this '_type' business necessary?
        max.Registry.register(new_cls, name, _type)

        return new_cls

#-------------------------------------------------------------------------------
class Module(min.Module):
    __metaclass__ = RegisterMeta

    def __init__(self, *args, **kwargs):
        min.Module.__init__(self, *args, **kwargs)
        self.verilog = max.VerilogGenerator(self)

    def generate_verilog(self):
        for mod_inst in self.get_module_instances(flatten=True):
            try: mod_inst.make(self.model)
            except min.MintModelDoesNotExist, e: pass

        for intf_inst in self.get_interface_instances(flatten=True):
            intf_inst.make(self.model)
            for intf_inst2 in intf_inst.interface.get_interface_instances(flatten=True):
                intf_inst2.make(self.model)

        self.verilog.generate_module()

class Interface(min.Interface):
    __metaclass__ = RegisterMeta

class model(object):
    "Descriptor for model definition"

    def __init__(self, model_func):
        self.name = model_func.__name__
        self.func = model_func
        #logging.info('Reading model: %s' % self.name)

    def __get__(self, obj, objtype):
        """ obj = module or interface object """

        def _model(obj):
            #print "model:", obj.name, obj, objtype, self.func.__name__

            model_func_args = inspect.getargspec(self.func).args
            obj.port_at_pos = model_func_args[1:]

            arg_dict = {}
            for port_name in obj.port_at_pos:
                port_inst = min.ModInstScalar(module=min.Module(name='_port_'),
                                              name=port_name)
                port_inst.isport = True
                arg_dict[port_name] = port_inst

            func_locals = self.func(obj, **arg_dict)

            if func_locals is None:
                raise min.MintError(
                    "Missing 'return locals()' for %s model of %s" %
                    (self.func.__name__, objtype.__name__))

            #print "func locals:", func_locals

            for var_name, var in func_locals.items():
                #print var_name, var
                try:
                    var.name = var.name or var_name
                except AttributeError:
                    pass
                else:
                    obj.add(var)

            return func_locals

        functools.update_wrapper(_model, self.func)

        return _model

#-------------------------------------------------------------------------------
instance = max.InstGen(scalar_type=min.ModInstScalar,
                           vector_type=min.ModInstList,
                           instof_type=min.Module)

interface = max.InstGen(scalar_type=min.IntfInstScalar,
                            vector_type=min.IntfInstList,
                            instof_type=min.Interface)

wire = max.WireGen()
const = min.Const
concat = min.Concat

#-------------------------------------------------------------------------------
def verilog(module, model):
    mod = module(model=model)

    for mod_inst in mod.get_module_instances(flatten=True):
        try: mod_inst.make(model)
        except min.MintModelDoesNotExist, e: pass #warnings.warn(repr(e))

    for intf_inst in mod.get_interface_instances(flatten=True):
        intf_inst.make(model)
        #try: intf_inst.make(model)
        #except min.MintModelDoesNotExist: pass #warnings.warn(repr(e))
        for intf_inst2 in intf_inst.interface.get_interface_instances(flatten=True):
            intf_inst2.make(model)

    vgen = max.VerilogGenerator(mod)

    vgen.generate_module()

#-------------------------------------------------------------------------------
