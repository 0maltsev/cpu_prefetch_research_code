"""Explicit bound D254 configuration before the qualified operational CLI.

Packet bytes confer no experiment authority. Every formal command still uses
its original signed request, verified journal and actual source qualification.
"""
import argparse,hashlib,json,os,pathlib,stat,sys,types

def read(b):
 if set(b)!={'path','size_bytes','sha256'}:raise ValueError('exact binding required')
 p=pathlib.Path(b['path'])
 if not p.is_absolute() or any(q.is_symlink() for q in (p,*p.parents)):raise ValueError('canonical nonsymlink path required')
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK)
 with os.fdopen(fd,'rb') as stream:
  before=os.fstat(stream.fileno())
  if not stat.S_ISREG(before.st_mode) or not 0<before.st_size==b['size_bytes']<=128*1024**2:raise ValueError('bounded regular file required')
  raw=stream.read(before.st_size+1);after=os.fstat(stream.fileno())
 stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
 if stamp(before)!=stamp(after) or stamp(before)!=stamp(p.stat()) or len(raw)!=before.st_size or hashlib.sha256(raw).hexdigest()!=b['sha256']:raise ValueError('configuration/member bytes changed')
 return raw

def configure(path,digest):
 raw=read(dict(path=str(path),size_bytes=path.stat().st_size,sha256=digest));c=json.loads(raw)
 if c['schema_version']!='software-d254-qualified-cli-configuration/1' or c['execution_authority'] is not False:raise ValueError('configuration schema/authority')
 if pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=c['boot_id']:raise ValueError('stand boot changed')
 root=pathlib.Path(c['repository_root']);packet=pathlib.Path(c['packet_root'])
 # Authenticate every source from the exact qualified policy before imports.
 policy=json.loads(read(c['policy']))
 for group in ('bindings','runtime_closure'):
  for b in policy[group].values():read(dict(b,path=str(root/b['path'])))
 sys.path.insert(0,str(root/'tools'));sys.path.insert(1,str(packet))
 name='stage17_daycap_administration_v1'
 if name in sys.modules:raise ValueError('unverified cached administrative module')
 administrative_bytes=read(c['administration'])
 module=types.ModuleType(name);module.__file__=c['administration']['path'];sys.modules[name]=module
 exec(compile(administrative_bytes,module.__file__,'exec'),module.__dict__)
 cli=module.make_cli()
 import stage17_archive_daycap_overlay_v1 as overlay
 overlay.configure_verified_descriptor(read(c['overlay']),packet)
 cli.controller.configure_historical_inputs(json.loads(read(c['historical_inputs'])),packet)
 cli.activate();return cli,c

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--configuration',type=pathlib.Path,required=True);p.add_argument('--configuration-sha256',required=True);a,remaining=p.parse_known_args()
 cli,c=configure(a.configuration,a.configuration_sha256)
 sys.argv=[str(pathlib.Path(cli.__file__)),*remaining];raise SystemExit(cli.main())
