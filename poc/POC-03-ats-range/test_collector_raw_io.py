"""Actual loopback HTTP with synthetic media and raw files; no ATS/POC run."""
import hashlib
import http.client
import http.server
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from collect import Collector


class CollectorRawIOTests(unittest.TestCase):
    def request(self, framing='length', writing='normal'):
        data = b'abcdefgh' if framing=='truncated' or writing=='zero' else b'abcdefgh'*10001+b'tail'
        class Source(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def log_message(self, *args): pass
            def do_GET(self):
                self.send_response(200)
                if framing in ('chunked','truncated'):
                    self.send_header('Transfer-Encoding','chunked')
                else:
                    self.send_header('Content-Length',str(len(data)))
                self.send_header('Connection','close')
                self.end_headers()
                try:
                    if framing=='truncated':
                        self.wfile.write(b'8\r\nabc')
                    elif framing=='chunked':
                        for offset in range(0,len(data),8191):
                            block=data[offset:offset+8191]
                            self.wfile.write((format(len(block),'x')+'\r\n').encode()+block+b'\r\n')
                        self.wfile.write(b'0\r\n\r\n')
                    else:
                        self.wfile.write(data)
                    self.wfile.flush()
                except (BrokenPipeError,ConnectionResetError):
                    if writing!='zero':raise
                self.close_connection=True
        requests=[]
        original_readinto=http.client.HTTPResponse.readinto
        def observed_readinto(response,target):
            requests.append((len(target),id(target.obj)))
            return original_readinto(response,target)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.bin';source.write_bytes(data)
            output=root/'out';(output/'bodies').mkdir(parents=True);(output/'observations').mkdir()
            collector=object.__new__(Collector)
            collector.out=output
            collector.cfg=dict(users={'lab-user-a':'synthetic-only'},aclVersion='synthetic-acl',
                inputs={'base':dict(path=str(source),sizeBytes=len(data),etag='"synthetic"',sha256=hashlib.sha256(data).hexdigest())})
            collector.lock=threading.RLock();collector.rows=[];collector.total_bytes=0
            collector.request_active=collector.request_peak=0;collector.monotonic=time.monotonic()
            collector.control=lambda *args,**kwargs:dict(originRequestCount=0,objectReadCount=0,objectReadBytes=0,activeOriginRequests=0)
            original_open=Path.open
            write_calls=[]
            observed_modes=[]
            class Writer:
                def __init__(self,stream):self.stream=stream
                def __enter__(self):return self
                def __exit__(self,*args):self.stream.close()
                def write(self,view):
                    write_calls.append(len(view))
                    if writing=='zero':return 0
                    with view[:4093] as part:return self.stream.write(part)
            def opened(path,*args,**kwargs):
                mode=args[0] if args else kwargs.get('mode','r')
                if path==source or (path.parent.name=='bodies' and mode=='xb'):
                    observed_modes.append((mode,kwargs.get('buffering')))
                    self.assertEqual(kwargs.get('buffering'),0)
                stream=original_open(path,*args,**kwargs)
                if path.parent.name=='bodies' and mode=='xb' and writing!='normal':return Writer(stream)
                return stream
            with http.server.HTTPServer(('127.0.0.1',0),Source) as server:
                worker=threading.Thread(target=lambda:server.serve_forever(poll_interval=.02))
                worker.start()
                collector.entry='http://127.0.0.1:'+str(server.server_address[1])
                try:
                    with patch.object(Path,'open',new=opened),patch.object(http.client.HTTPResponse,'readinto',new=observed_readinto):
                        row=collector.request('stream',range_header='')
                finally:
                    server.shutdown();worker.join(timeout=3)
                self.assertFalse(worker.is_alive())
            saved=json.loads(next((output/'observations').glob('request-*.json')).read_text())
            self.assertEqual(json.loads(json.dumps(row)),saved)
            self.assertEqual((collector.request_active,collector.request_peak),(0,1))
            actual=(output/row['bodyRef']).read_bytes()
            self.assertTrue(requests)
            self.assertEqual(requests[0][0],1)
            self.assertEqual(len({identity for _,identity in requests}),1)
            self.assertTrue(all(1<=size<=65536 for size,_ in requests))
            self.assertEqual(row['clientBackingCapacityBytes'],65537)
            self.assertIsNotNone(row['firstResponseByteAt'])
            self.assertIsNotNone(row['firstBodyByteAt'])
            self.assertIn(('xb',0),observed_modes)
            if writing=='zero':
                self.assertFalse(row['transportCompleted'])
                self.assertIn('raw response write made no progress',row['bodyPersistenceError'])
                self.assertEqual(actual,b'')
            elif framing=='truncated':
                self.assertFalse(row['transportCompleted'])
                self.assertEqual(row['transportError'],'IncompleteRead')
                self.assertLess(len(actual),len(data))
                self.assertEqual(row['bodySha256'],hashlib.sha256(actual).hexdigest())
                self.assertNotIn('sourceIntervalComparison',row)
            else:
                self.assertTrue(row['transportCompleted'])
                self.assertEqual(actual,data)
                self.assertEqual(row['bodyBytes'],len(data))
                self.assertEqual(row['bodySha256'],hashlib.sha256(data).hexdigest())
                self.assertTrue(row['sourceIntervalComparison']['actualBytesEqual'])
                self.assertEqual(row['comparisonBackingCapacityBytes'],65537)
                self.assertIn(('rb',0),observed_modes)
                if writing=='partial':self.assertGreater(len(write_calls),3)

    def test_content_length_stream_and_comparison_use_fixed_raw_buffers(self):
        self.request()

    def test_chunked_stream_uses_real_http_readinto_and_exact_content(self):
        self.request(framing='chunked')

    def test_partial_raw_file_writes_are_completed_without_losing_bytes(self):
        self.request(writing='partial')

    def test_no_progress_raw_file_write_remains_an_explicit_failure(self):
        self.request(writing='zero')

    def test_truncated_chunked_stream_retains_incomplete_read_failure(self):
        self.request(framing='truncated')


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CollectorRawIOTests))
    if result.testsRun!=5 or result.skipped:
        raise SystemExit('Expected five actual Collector raw-I/O tests and no skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)
