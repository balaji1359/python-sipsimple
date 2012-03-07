# Copyright (C) 2008-2011 AG Projects. See LICENSE for details.
#

"""Implements utilities commonly used in various parts of the library"""

from __future__ import absolute_import, with_statement

__all__ = ["All", "Any", "MultilingualText", "Route", "Timestamp", "TimestampedNotificationData", "user_info"]

import os
import platform
import re
import socket
import sys
from datetime import datetime

from application.notification import NotificationData
from application.python.types import Singleton
from dateutil.tz import tzoffset


# Utility classes
#

class AllType(object):
    __metaclass__ = Singleton

    def __repr__(self):
        return 'All'

    def __reduce__(self):
        return (self.__class__, (), None)

All = AllType()


class AnyType(object):
    __metaclass__ = Singleton

    def __repr__(self):
        return 'Any'

    def __reduce__(self):
        return (self.__class__, (), None)

Any = AnyType()


class MultilingualText(unicode):
    def __new__(cls, *args, **translations):
        if len(args) > 1:
            raise TypeError("%s.__new__ takes at most 1 positional argument (%d given)" % (cls.__name__, len(args)))
        default = args[0] if args else translations.get('en', u'')
        obj = unicode.__new__(cls, default)
        obj.translations = translations
        return obj

    def get_translation(self, language):
        return self.translations.get(language, self)


class Route(object):
    def __init__(self, address, port=None, transport='udp'):
        self.address = address
        self.port = port
        self.transport = transport

    def _get_address(self):
        return self._address
    def _set_address(self, address):
        try:
            socket.inet_aton(address)
        except:
            raise ValueError('illegal address: %s' % address)
        self._address = address
    address = property(_get_address, _set_address)
    del _get_address, _set_address

    def _get_port(self):
        if self._port is None:
            return 5060 if self.transport in ('udp', 'tcp') else 5061
        else:
            return self._port
    def _set_port(self, port):
        port = int(port) if port is not None else None
        if port is not None and not (0 < port < 65536):
            raise ValueError('illegal port value: %d' % port)
        self._port = port
    port = property(_get_port, _set_port)
    del _get_port, _set_port

    def _get_transport(self):
        return self._transport
    def _set_transport(self, transport):
        if transport not in ('udp', 'tcp', 'tls'):
            raise ValueError('illegal transport value: %s' % transport)
        self._transport = transport
    transport = property(_get_transport, _set_transport)
    del _get_transport, _set_transport

    def get_uri(self):
        from sipsimple.core import SIPURI
        if self.transport in ('udp', 'tcp') and self.port == 5060:
            port = None
        elif self.transport == 'tls' and self.port == 5061:
            port = None
        else:
            port = self.port
        parameters = {'transport': self.transport} if self.transport != 'udp' else {}
        return SIPURI(host=self.address, port=port, parameters=parameters)

    def __repr__(self):
        return '%s(%r, %r, %r)' % (self.__class__.__name__, self.address, self.port, self.transport)
    
    def __str__(self):
        return 'sip:%s:%d;transport=%s' % (self.address, self.port, self.transport)


class Timestamp(datetime):
    _timestamp_re = re.compile(r'(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})T(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(\.(?P<secfrac>\d{1,}))?((?P<UTC>Z)|((?P<tzsign>\+|-)(?P<tzhour>\d{2}):(?P<tzminute>\d{2})))')

    @classmethod
    def utc_offset(cls):
        timediff = datetime.now() - datetime.utcnow()
        return int(round((timediff.days*86400 + timediff.seconds + timediff.microseconds/1000000.0)/60))

    @classmethod
    def parse(cls, stamp):
        if stamp is None:
            return None
        match = cls._timestamp_re.match(stamp)
        if match is None:
            raise ValueError("Timestamp %s is not in RFC3339 format" % stamp)
        dct = match.groupdict()
        if dct['UTC'] is not None:
            secoffset = 0
        else:
            secoffset = int(dct['tzminute'])*60 + int(dct['tzhour'])*3600
            if dct['tzsign'] == '-':
                secoffset *= -1
        tzinfo = tzoffset(None, secoffset)
        if dct['secfrac'] is not None:
            secfrac = dct['secfrac'][:6]
            secfrac += '0'*(6-len(secfrac))
            secfrac = int(secfrac)
        else:
            secfrac = 0
        dt = datetime(int(dct['year']), month=int(dct['month']), day=int(dct['day']),
                      hour=int(dct['hour']), minute=int(dct['minute']), second=int(dct['second']),
                      microsecond=secfrac, tzinfo=tzinfo)
        return cls(dt)

    @classmethod
    def format(cls, dt):
        if dt is None:
            return None
        if dt.tzinfo is not None:
            return dt.replace(microsecond=0).isoformat()
        minutes = cls.utc_offset()
        if minutes == 0:
            tzspec = 'Z'
        else:
            if minutes < 0:
                sign = '-'
                minutes *= -1
            else:
                sign = '+'
            hours = minutes / 60
            minutes = minutes % 60
            tzspec = '%s%02d:%02d' % (sign, hours, minutes)
        return dt.replace(microsecond=0).isoformat()+tzspec

    def __new__(cls, value, *args, **kwargs):
        if isinstance(value, cls):
            return value
        elif isinstance(value, datetime):
            return cls(value.year, month=value.month, day=value.day,
                       hour=value.hour, minute=value.minute, second=value.second,
                       microsecond=value.microsecond, tzinfo=value.tzinfo)
        elif isinstance(value, basestring):
            return cls.parse(value)
        else:
            return datetime.__new__(cls, value, *args, **kwargs)

    def __str__(self):
        return self.format(self)


class TimestampedNotificationData(NotificationData):

    def __init__(self, **kwargs):
        self.timestamp = datetime.now()
        NotificationData.__init__(self, **kwargs)


# Utility objects
#

class UserInfo(object):
    __metaclass__ = Singleton

    def __repr__(self):
        attribs = ', '.join('%s=%r' % (attr, getattr(self, attr)) for attr in ('username', 'fullname'))
        return '%s(%s)' % (self.__class__.__name__, attribs)

    @property
    def username(self):
        if platform.system() == 'Windows':
            name = os.getenv('USERNAME')
        else:
            import pwd
            name = pwd.getpwuid(os.getuid()).pw_name
        return name.decode(sys.getfilesystemencoding())

    @property
    def fullname(self):
        if platform.system() == 'Windows':
            name = os.getenv('USERNAME')
        else:
            import pwd
            name = pwd.getpwuid(os.getuid()).pw_gecos.split(',', 1)[0] or pwd.getpwuid(os.getuid()).pw_name
        return name.decode(sys.getfilesystemencoding())

user_info = UserInfo()
del UserInfo


