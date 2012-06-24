from __future__ import with_statement
from threading import Lock
from threading import Condition
from contextlib import contextmanager

class OnetimeEvent(object):
    """
        Specialized lightweight event that can only transition 
        from cleared to set, one time.  
    """
    __slots__ = ("_value", "_condition", "_synclock")
    def __init__(self, lock=None):
        self._value = False
        self._condition = None
        self._synclock = lock if lock else Lock()
        super(OnetimeEvent, self).__init__()
    def set(self):
        with self._synclock:
            self._set()
    def wait(self, timeout=None):
        with self._synclock:
            if not self._value:
                if not self._condition:
                    self._condition = Condition(self._synclock)
                self._condition.wait(timeout)
            value = self._value
        return value
    @contextmanager
    def setting(self, asserts=False, unconditional=False):
        self._synclock.acquire()
        try:
            if asserts:
                assert not self._value
            (yield self._value)
        except:
            if unconditional:
                self._set()
            raise
        else:
            self._set()
        finally:
            self._synclock.release()
    def _set(self):
        self._value = True
        if self._condition:
            self._condition.notifyAll()
        self._condition = None
    def _get(self):
        return self._value
    def __call__(self):
        with self._synclock:
            return self._value
    is_set = isSet = __call__

