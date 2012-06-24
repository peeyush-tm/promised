from __future__ import with_statement
from functools import wraps
from collections import deque
from threading import Thread
from utils import OnetimeEvent

class Result(object):
    """
        Simple Result type based on a synchronous version of 
        Python's multiprocessing.pool.ApplyResult, which is 
        the Asynchronous Result returned by processes. 
    """
    def __init__(self, value, error=False):
        self._value = value
        self._error = error
        super(Result, self).__init__()
    def successful(self):
        return not self._error
    def value(self):
        return self._value
    def get(self):
        if not self.successful():
            raise self._value
        return self._value

class AsynchronousResult(Result):
    """
        Asynchronous Result based on 
        multiprocessing.pool.ApplyResult.
    """
    def __init__(self, lock=None):
        self._synclock = lock
        self._ready = OnetimeEvent(lock)
        super(AsynchronousResult, self).__init__(None)
    def ready(self):
        return self._ready()
    def wait(self, timeout=None):
        self._ready.wait(timeout)
        return self
    def successful(self):
        self.assert_ready(False)
        return super(AsynchronousResult, self).successful()
    def get(self, timeout=15):
        self.assert_ready(True, timeout)
        return super(AsynchronousResult, self).get()
    def set(self, value, error=False):
        with self._synclock:
            self._set(value, error)
        return self
    def assert_ready(self, blocking=False, timeout=None):
        if blocking:
            self.wait(timeout)
        assert self.ready()
    def _set(self, value, error):
        assert not self._ready._get(), "Result value already set."
        self._value = value
        self._error = error
        self._ready._set()
        return
