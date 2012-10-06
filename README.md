solusconfig
===========

The SolusOS Configuration System

About
-----
solusconfig is the backend configuration system of SolusOS.
It provides a standardised interface for common configuration tasks within
the system.

It exposes itself as a D-BUS service, and performs authentication via PolicyKit.
PolicyKit authentication can be "remembered" for the lifetime of a session, enabling
"unlocking" of UI pages.

Implemented Tasks
-----------------

 * PulseAudio fix (Switch between interrupt and timer based scheduling)

Usage
-----
This system is designed solely for SolusOS. It may no function correctly on other operating systems.
It is currently in development and is not yet intended for any other use than put forward by the
author, as he so wishes.
