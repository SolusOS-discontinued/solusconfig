# -*- coding: UTF-8 -*-

import os, os.path, subprocess, sys, logging, re
from glob import glob

sys_dir = "/sys"

''' Return a 3 part tuple with information on the graphics card '''
def get_glx_info():
	p = subprocess.Popen(['glxinfo'], stdout=subprocess.PIPE,
	    stderr=subprocess.PIPE, close_fds=True)
	output = p.communicate()[0]

	renderer = "UNKNOWN"
	vendor = "UNKNOWN"
	version = "UNKNOWN"

	for line in output.split("\n"):
		if "OpenGL" in line and ":" in line:

			bitWeWant = line.split(":")[1].strip()
			if "vendor" in line:
				vendor = bitWeWant
			elif "renderer" in line:
				renderer = bitWeWant
			elif "version string" in line and not "language" in line: # block CG compiler
				version = bitWeWant

	return (vendor,renderer,version)

''' Return the name of the driver in /etc/X11/xorg.conf, or None '''
def get_configured_driver():
	if not os.path.exists("/etc/X11/xorg.conf"):
		return None

	with open("/etc/X11/xorg.conf","r") as x_file:

		inSection = False
		for line in x_file.readlines():

			line = line.replace("\r","").replace("\n","").strip()

			if not inSection and "Section" in line and "\"Device\"" in line:
				inSection = True
			if "EndSection" in line:
				inSection = False
			if  "Driver" in line and inSection:

				driver = line.strip().split()[1].replace("\"","")
				return driver

	return None

def get_os_version():
	'''Initialize self.os_vendor and self.os_version.

	This defaults to reading the values from lsb_release.
	'''
	p = subprocess.Popen(['lsb_release', '-si'], stdout=subprocess.PIPE,
	    stderr=subprocess.PIPE, close_fds=True)
	self.os_vendor = p.communicate()[0].strip()
	p = subprocess.Popen(['lsb_release', '-sr'], stdout=subprocess.PIPE,
	    stderr=subprocess.PIPE, close_fds=True)
	self.os_version = p.communicate()[0].strip()
	assert p.returncode == 0

def get_system_vendor_product():
	'''Return (vendor, product) of the system hardware.

	Either or both can be '' if they cannot be determined.

	The default implementation queries sysfs.
	'''
	try:
	    vendor = open(os.path.join(sys_dir,
		'class', 'dmi', 'id', 'sys_vendor')).read().strip()
	except IOError:
	    vendor = ''

	try:
	    product = open(os.path.join(sys_dir,
		'class', 'dmi', 'id', 'product_name')).read().strip()
	except IOError:
	    product = ''

	return (vendor, product)

(sys_vendor, sys_product) = get_system_vendor_product()

def get_modaliases():
    '''Return a set of modalias HardwareIDs for available hardware.'''

    if get_modaliases.cache:
        return get_modaliases.cache

    hw = set()
    for path, dirs, files in os.walk(os.path.join(sys_dir, 'devices')):
        modalias = None

        # most devices have modalias files
        if 'modalias' in files:
            modalias = open(os.path.join(path, 'modalias')).read().strip()
        # devices on SSB bus only mention the modalias in the uevent file (as
        # of 2.6.24)
        elif 'ssb' in path and 'uevent' in files:
            info = {}
            for l in open(os.path.join(path, 'uevent')):
                if l.startswith('MODALIAS='):
                    modalias = l.split('=', 1)[1].strip()
                    break

        if not modalias:
            continue

        # ignore drivers which are statically built into the kernel
        driverlink =  os.path.join(path, 'driver')
        modlink = os.path.join(driverlink, 'module')
        if os.path.islink(driverlink) and not os.path.islink(modlink):
            continue

        hw.add(HardwareID('modalias', modalias))

    get_modaliases.cache = hw
    return hw

get_modaliases.cache = None

def get_printers():
    '''Return a set of HardwareIDs for connected printers.'''

    if get_printers.cache is not None:
        return get_printers.cache

    get_printers.cache = set()

    try:
        import cups
        import cupshelpers
    except ImportError:
        logging.warning('cups and/or cupshelpers Python modules are not present; printer detection is not available')
        return get_printers.cache

    try:
        for dev in cupshelpers.getDevices(cups.Connection()).itervalues():
            # openprinting.org database only uses MFG, MDL, DES, and CMD, so don't
            # send the rest (it might contain personal data such as serial numbers)
            if dev.id_dict.get('MFG') and dev.id_dict.get('MDL'):
                id = 'MFG:%s;MDL:%s;' % (dev.id_dict['MFG'], dev.id_dict['MDL'])
                if dev.id_dict.get('DES'):
                    id += 'DES:' + dev.id_dict['DES'] + ';'
                if dev.id_dict.get('CMD'):
                    id += 'CMD:' + ','.join(dev.id_dict['CMD']) + ';'
                _get_printers.cache.add(HardwareID('printer_deviceid', id))
    except (RuntimeError, cups.IPPError):
        logging.warning('cannot connect to cups; printer detection is not available')
        return set()
           
    return get_printers.cache

get_printers.cache = None

#--------------------------------------------------------------------#

class HardwareID:
    '''A piece of hardware is denoted by an identification type and value.

    The most common identification type is a 'modalias', but in the future we
    might support other types (such as bus/vendorid/productid, printer
    device ID, etc.).
    '''
    _recache = {}

    def __init__(self, type, id):
        self.type = type
        self.id = id

    def __repr__(self):
        return "HardwareID('%s', '%s')" % (self.type, self.id)

    def __eq__(self, other):
        if type(self) != type(other) or self.type != other.type:
            return False

        if self.type != 'modalias':
            return self.id == other.id

        # modalias pattern matching
        if '*' in self.id:
            # if used as dictionary keys we do need to compare two patterns; in
            # that case they should just be tested for string equality
            if '*' in other.id:
                return self.id == other.id
            else:
                return self.regex(self.id).match(other.id)
        else:
            if '*' in other.id:
                return self.regex(other.id).match(self.id)
            else:
                return self.id == other.id

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        # This is far from efficient, but we usually have a very small number
        # of handlers, so it doesn't matter.

        if self.type == 'modalias':
            # since we might have patterns, we cannot rely on hash identidy of
            # id
            return hash(self.type) ^ hash(self.id[:self.id.find(':')])
        else:
            return hash(self.type) ^ hash(self.id)

    @classmethod
    def regex(klass, pattern):
        '''Convert modalias pattern to a regular expression.'''

        r = klass._recache.get(pattern)
        if not r:
            r = re.compile(re.escape(pattern).replace('\\*', '.*') + '$')
            klass._recache[pattern] = r
        return r


def get_modinfo(module):
    '''Return information about a kernel module.
    
    This is delivered as a dictionary; keys are property names (strings),
    values are lists of strings (some properties might have multiple
    values, such as multi-line description fields or multiple PCI
    modaliases).
    '''
    try:
        return get_modinfo.cache[module]
    except KeyError:
        pass

    proc = subprocess.Popen(("/sbin/modinfo", module),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = proc.communicate()
    if proc.returncode != 0:
        logging.warning('modinfo for module %s failed: %s' % (module, stderr))
        return None

    modinfo = {}
    for line in stdout.split('\n'):
        if ':' not in line:
            continue

        (key, value) = line.split(':', 1)
        modinfo.setdefault(key.strip(), []).append(value.strip())

    get_modinfo.cache[module] = modinfo
    return modinfo

get_modinfo.cache = {}

def get_hardware():
    '''Return a set of HardwareID objects for the local hardware.'''

    # modaliases
    result = get_modaliases()
    # printer device IDs
    result.update(get_printers())

    # other hardware detection goes here

    return result

(MODE_FREE, MODE_NONFREE, MODE_ANY) = range(3)
