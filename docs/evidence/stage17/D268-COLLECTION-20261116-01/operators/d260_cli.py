"""Authenticate the separately published D265 packet before operational entry."""
import argparse,hashlib,importlib.util,pathlib,sys
LOADER=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-27/d260-configuration-3/stage17_service_continuation_packet_v3.py')
PIN='b8c54a71ea73b8e4381cb85bd2d7352c5a5524085d05babe9d6673a3fedc0058'
def configure(path,digest):
 raw=LOADER.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('loader changed')
 name='stage17_service_continuation_packet_v3';m=sys.modules.get(name)
 if m is None:
  m=__import__('types').ModuleType(name);m.__file__=str(LOADER);sys.modules[name]=m;exec(compile(raw,str(LOADER),'exec'),m.__dict__)
 elif m.__file__!=str(LOADER):raise ValueError('foreign loader cache')
 return m.activate(path,digest)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--configuration',type=pathlib.Path,required=True);p.add_argument('--configuration-sha256',required=True);a,rest=p.parse_known_args()
 cli,_=configure(a.configuration,a.configuration_sha256);sys.argv=[__file__,*rest];raise SystemExit(cli.main())
