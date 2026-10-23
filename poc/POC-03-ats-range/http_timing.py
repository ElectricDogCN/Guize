"""Observe the first received HTTP response byte separately from headers and media."""
import http.client
import time
import urllib.request

from lab import utc


class FirstResponseByteReader:
    def __init__(self, stream, marks, started):
        self.stream, self.marks, self.started = stream, marks, started
        self.observed = False

    def readline(self, limit=-1):
        if self.observed or limit == 0:
            return self.stream.readline(limit)
        first = self.stream.read(1)
        if not first:
            return first
        self.observed = True
        self.marks['firstResponseByteAt'] = utc()
        self.marks['firstResponseByteLatencyMs'] = (time.monotonic() - self.started) * 1000
        if first == b'\n' or limit == 1:
            return first
        return first + self.stream.readline(limit - 1 if limit > 0 else -1)

    def __getattr__(self, name):
        return getattr(self.stream, name)


def timing_handler(marks, started):
    class ObservedResponse(http.client.HTTPResponse):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fp = FirstResponseByteReader(self.fp, marks, started)

    class ObservedConnection(http.client.HTTPConnection):
        response_class = ObservedResponse

    class ObservedHandler(urllib.request.HTTPHandler):
        def http_open(self, request):
            return self.do_open(ObservedConnection, request)

    return ObservedHandler()
