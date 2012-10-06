import contextlib
import os
import pwd

_dropped_privileges = 0

# Drop to "nobody"
ASSUMED_UID = 65534
ASSUMED_GID = 65534

def drop_all_privileges():
    # gconf needs both the UID and effective UID set.
    global _dropped_privileges
    if 'SUDO_GID' in os.environ:
        gid = int(os.environ['SUDO_GID'])
        os.setregid(gid, gid)
    else:
	os.setregid(ASSUMED_GID, ASSUMED_GID)
    if 'SUDO_UID' in os.environ:
        uid = int(os.environ['SUDO_UID'])
        os.setreuid(uid, uid)
        os.environ['HOME'] = pwd.getpwuid(uid).pw_dir
    else:
	os.setreuid(ASSUMED_UID, ASSUMED_UID)
	os.environ['HOME'] = "/tmp"
    _dropped_privileges = None

def drop_privileges():
    global _dropped_privileges
    assert _dropped_privileges is not None
    if _dropped_privileges == 0:
        if 'SUDO_GID' in os.environ:
            gid = int(os.environ['SUDO_GID'])
            os.setegid(gid)
	else:
            os.setegid(ASSUMED_GID)
        if 'SUDO_UID' in os.environ:
            uid = int(os.environ['SUDO_UID'])
            os.seteuid(uid)
	else:
            os.seteuid(ASSUMED_UID)
    _dropped_privileges += 1

def regain_privileges():
    global _dropped_privileges
    assert _dropped_privileges is not None
    _dropped_privileges -= 1
    if _dropped_privileges == 0:
        os.seteuid(0)
        os.setegid(0)


@contextlib.contextmanager
def raised_privileges():
    """As regain_privileges/drop_privileges, but in context manager style."""
    regain_privileges()
    try:
        yield
    finally:
        drop_privileges()

def raise_privileges(func):
    """As raised_privileges, but as a function decorator."""
    from functools import wraps

    @wraps(func)
    def helper(*args, **kwargs):
        with raised_privileges():
            return func(*args, **kwargs)

    return helper
