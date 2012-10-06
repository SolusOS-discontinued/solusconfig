import dbus
import os

# Reference File. Because there just isn't any decent documentation in existence on
# accessing policykit from Python. Modify to suit your needs
# (In fairness you can now access polkit via gi.repository but not everyone can use that.)

class PolkitHelper:

	def check_authorization(self, pid, action_id):

		# PolicyKit lives on the system bus
		bus = dbus.SystemBus()
		proxy = bus.get_object('org.freedesktop.PolicyKit1', '/org/freedesktop/PolicyKit1/Authority')

		# Create an automated interface object from org.freedesktop.PolicyKit1.Authority
		# Why? Because 1) You need this object and 2) Constantly getting dbus methods is a pain
		# in the hole. This automagics it a bit
		pk_authority = dbus.Interface(proxy,  dbus_interface='org.freedesktop.PolicyKit1.Authority')



		# We're enquiring about this process
		subject = ('unix-process',{'pid':dbus.UInt32(pid,variant_level=1),'start-time':dbus.UInt64(0,variant_level=1)})

		# No cancellation.
		CANCEL_ID = ''

		# AllowUserInteractionFlag
		flags = dbus.UInt32(1) 

		# Only for trusted senders, rarely used.
		details = {}

		# Returns all 3 of these. Fancy that. Invariably you'll only care whether the person is actually authorized or not.
		# i.e. you correctly created your dbus service so that the right group/user/etc can talk to it, and you created
		# your policykit configuration correctly
		(pk_granted,pk_other,pk_details) = pk_authority.CheckAuthorization(
			subject,
			action_id ,
			details,
			flags,
			CANCEL_ID,
			timeout=600) # Makes sense to use a timeout, you don't want your service to lockup

		return pk_granted

if __name__ == "__main__":

	# Our own process id. In an ideal world you would ask the dbus client for the sendors PID
	# Once this is done, you use it in 'pid' section. If your dbus service works on a Lock/Unlock
	# policy, it makes sense to add the PID to a list of "authorized clients"
	# Of course, you should also monitor connections, and remove the disconnected PID instantly
	# to maintain security.
	pid = os.getpid()

	# This is the action we're interested in
	action_id = "com.solusos.installdriver"

	polkit_helper = PolkitHelper()

	granted = polkit_helper.check_authorization(pid, action_id)
	if granted:
		# Simple as that. Granted access.
		print "Granted!"
	else:
		# No go :)
		print "Denied!"




# Example Policy File
# -------------------
# This goes in /usr/share/polkit-1/actions/ as com.solusos.installdriver.policy 
# Change to suit :) 
#
'''
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1.0/policyconfig.dtd">
<policyconfig>

  <vendor>SolusOS</vendor>
  <vendor_url>http://www.solusos.com</vendor_url>
  <icon_name>video-display</icon_name>
  <action id="com.solusos.installdriver">
    <description>Install a driver on SolusOS</description>
    <message>To install a driver, you first need to authenticate</message>
    <defaults>
      <allow_any>no</allow_any>
      <allow_inactive>no</allow_inactive>
      <allow_active>auth_admin</allow_active>
    </defaults>
  </action>

</policyconfig>
'''
