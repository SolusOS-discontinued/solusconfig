#!/usr/bin/env python
import gobject
import dbus
import dbus.service
import dbus.glib
import shutil

from polkit_helper import PolkitHelper

# Privileges
from privs_misc import *

class ConfigService(dbus.service.Object):

    CONFIGURE_AUDIO = "com.solusos.configuration.audio"


    def __init__(self, loop):
        bus_name = dbus.service.BusName('com.solusos.config', bus = dbus.SystemBus())
        dbus.service.Object.__init__(self, bus_name, '/com/solusos/Configuration')

	self.dbus_info = None

	self.polkit = PolkitHelper()

	# Is PulseAudio fixed? "tsched=0"
	self.pa_fixed = False

	self.pid_map = dict()
	self.loop = loop

	# Weird as it may sound this is a dict of lists.
	self.action_pids = dict()

	# Drop privileges immediately. We don't need root access unless we're doing something
	drop_privileges()


    def _is_pulse_fixed(self):
	tsched_found = False
	regain_privileges()
	with open("/etc/pulse/default.pa", "r") as pulseconfig:
		for line in pulseconfig.readlines():
			line = line.replace("\r","").replace("\n","")
			if "tsched" in line and "module-udev-detect" in line:
				tsched_found = True
				break
	drop_privileges()
	return tsched_found


    def _set_pulse_fixed(self,fixed):
	if self._is_pulse_fixed() and fixed:
		return
	if not self._is_pulse_fixed() and not fixed:
		return

	with open("/etc/pulse/default.pa", "r") as pulseconfig:
		regain_privileges()
		with open("/etc/pulse/TMPCONFIG", "w") as newconfig:
			for line in pulseconfig.readlines():
				line = line.replace("\r","").replace("\n","")
				if "load-module module-udev-detect" in line:
					if fixed:
						newconfig.write("load-module module-udev-detect tsched=0\n")
					else:
						newconfig.write("load-module module-udev-detect\n")
				else:
					newconfig.write("%s\n" % line)
		drop_privileges()

	# Move the files
	try:
		regain_privileges()
		shutil.move("/etc/pulse/default.pa", "/etc/pulse/default.pa.BAK")
		shutil.move("/etc/pulse/TMPCONFIG", "/etc/pulse/default.pa")
		shutil.copystat("/etc/pulse/default.pa.BAK", "/etc/pulse/default.pa")
		drop_privileges()
	except Exception, ex:
		print ex

	print "Fixing PulseAudio"

    ''' Return the process ID for the specified connection '''
    def get_pid_from_connection(self, conn, sender):
        if self.dbus_info is None:
            self.dbus_info = dbus.Interface(conn.get_object('org.freedesktop.DBus',
                '/org/freedesktop/DBus/Bus', False), 'org.freedesktop.DBus')
        pid = self.dbus_info.GetConnectionUnixProcessID(sender)

	return pid


    ''' Very much around the houses. Monitor connection and hold onto process id's.
	This way we know who is already "authenticated" and who is not '''
    def register_connection_with_action(self, conn, sender, action_id):
	pid = self.get_pid_from_connection(conn, sender)

	if sender not in self.pid_map:
		print "Adding new sender: %s" % sender
		self.pid_map[sender] = pid

	if action_id not in self.action_pids:
		self.action_pids[action_id] = list()

	def cb(conn,sender):
		# Complicated, doesn't really need a lambda but in the future for whatever reason
		# we may need the sender and connection objects
		if conn == "":
			pid = None
			try:
				pid = self.pid_map[sender]
			except:
				# already removed, called twice.
				return
			print "Disconnected process: %d" % pid

			self.pid_map.pop(sender)
			count = 0
			for i in self.action_pids[action_id]:
				if i == pid:
					self.action_pids[action_id].pop(count)
					break
				count += 1
			del count
	conn.watch_name_owner(sender, lambda x: cb(x, sender))


    ''' Is PulseAudio already fixed ? '''
    @dbus.service.method("com.solusos.config", sender_keyword="sender", connection_keyword="conn", out_signature="b")
    def GetPulseAudioFixed(self, sender=None, conn=None):
	# Being nice we allow anyone to see the status of whether pulseaudio is fixed or not.
	fixed = self._is_pulse_fixed()
	return fixed


    ''' Apply the PulseAudio fix '''
    @dbus.service.method("com.solusos.config", sender_keyword="sender", connection_keyword="conn", in_signature="b")
    def SetPulseAudioFixed(self, fixed, sender=None, conn=None):


	# I know this could be a simple return statement but this needs to be a readable example :p
	# Soon I'll be adding actual work-code here.
	if self.persist_authorized(sender, conn, self.CONFIGURE_AUDIO):
		self._set_pulse_fixed(fixed)
		return True
	else:
		return False



    ''' Utility Method. Check if the sender is authorized to perform this action. If so, add them to a persistent list.
	List is persistent until this object is destroyed. Works via process ID's '''
    def persist_authorized(self, sender,conn, action_id):
	self.register_connection_with_action(conn,sender,action_id)

	pid = self.pid_map[sender]

	if not pid in self.action_pids[action_id]:
		if self.polkit.check_authorization(pid, action_id):
			self.action_pids[action_id].append(pid)
			return True # Authorized by PolKit!

		else:
			return False # Unauthorized by PolKit!
	else:
		return True # Already authorized by PolKit in this session

    ''' Shut down this service '''
    @dbus.service.method('com.solusos.config',  sender_keyword='sender',  connection_keyword='conn')
    def ShutDown(self, sender=None, conn=None):
	# No special checks required as of yet, but in future, flag quit for after finishing

	print "Shutdown requested"

	# you can't just do a sys.exit(), this causes errors for clients
	self.loop.quit()


