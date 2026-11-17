"""Local-only full TIFF conversion probe; never connects to Skybox.

Run from repository root with PYTHONPATH=. and tuning environment variables.
Requires scratch space for the staged raster and COG. Injects one HTTP 400
at 8–9 GiB to exercise window recovery on the 17 GB fixture.
"""
import argparse
import json
import tempfile
import os, re, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path)
parser.add_argument('destination', type=Path)
args = parser.parse_args()
source = args.source.resolve()
if args.destination.exists():
 parser.error('Destination must not exist.')
args.destination.parent.mkdir(parents=True, exist_ok=True)
size=source.stat().st_size
state={'requests':0,'bytes':0,'faults':0,'max_range_bytes':0}
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def do_HEAD(self): self.reply(False)
 def do_GET(self): self.reply(True)
 def reply(self,body):
  start,end=0,size-1
  value=self.headers.get('Range')
  if value:
   match=re.fullmatch(r'bytes=(\d+)-(\d*)',value)
   if not match: self.send_error(416);return
   start=int(match[1]);end=min(int(match[2]) if match[2] else end,end)
  if self.headers.get('If-Match')!='"original-verified"':self.send_error(412);return
  state['requests']+=1
  state['max_range_bytes']=max(state['max_range_bytes'],end-start+1 if body else 0)
  if body and 8*1024**3<=start<9*1024**3 and not state['faults']:
   state['faults']+=1;self.send_error(400);return
  self.send_response(206 if value else 200)
  self.send_header('Content-Length',str(end-start+1));self.send_header('ETag','"original-verified"')
  if value:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
  self.end_headers()
  if body:
   with source.open('rb') as stream:
    stream.seek(start);remaining=end-start+1
    while remaining:
     data=stream.read(min(1024*1024,remaining))
     try:self.wfile.write(data)
     except (BrokenPipeError,ConnectionResetError):break
     remaining-=len(data);state['bytes']+=len(data)
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
header_dir = tempfile.TemporaryDirectory(prefix='ija-range-probe-')
headers=Path(header_dir.name)/'headers'
headers.write_text('If-Match: '+chr(34)+'original-verified'+chr(34)+chr(10))
t=time.monotonic()
try:
 import subprocess,sys
 env=os.environ.copy()
 env.update(GDAL_HTTP_HEADER_FILE=str(headers), GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif', CPL_VSIL_CURL_CHUNK_SIZE=str(4*1024*1024), CPL_VSIL_CURL_CACHE_SIZE=str(512*1024*1024), GDAL_HTTP_MULTIRANGE='SERIAL', ORTHOMOSAIC_JOB_MAX_BYTES=str(12*1024**3))
 result=subprocess.run([sys.executable,'-u','app/modules/ortomosaicos/processor.py','convert',f'/vsicurl/http://127.0.0.1:{server.server_port}/original.tif',str(args.destination)],env=env)
 print(json.dumps(dict(state, exit_code=result.returncode, elapsed_seconds=round(time.monotonic()-t, 3))), flush=True)
finally:
 server.shutdown();server.server_close();thread.join();header_dir.cleanup()
raise SystemExit(result.returncode)
