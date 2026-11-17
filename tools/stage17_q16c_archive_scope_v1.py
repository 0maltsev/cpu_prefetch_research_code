"""D273 private verified archive-image imports; no raw decode by import."""
import os,sys

def require(ok,message):
 if not ok:raise ValueError(message)

def selected_archive_modules(profile,deadline):
 # Each source is freshly hash/identity checked by the qualified runtime. It is
 # executed from the authenticated immutable bytes, without path/pyc reopening.
 # Unique aliases and module-local imports leave all qualified science modules
 # and the parent's public import cache untouched.
 import builtins,types
 import stage17_formal_archive_runtime_v1 as runtime
 images=runtime._closure_bytes(profile,deadline)
 cache={};prefix='_d273_archive_'+str(os.getpid())+'_'
 real_import=builtins.__import__
 def load(name):
  if name in cache:return cache[name]
  binding,raw=images[name];alias=prefix+name
  require(alias not in sys.modules,'private archive alias already used')
  module=types.ModuleType(alias);module.__file__=str(binding.image.path);module.__package__=''
  cache[name]=module;sys.modules[alias]=module
  namespace=dict(vars(builtins));namespace['__import__']=scoped_import
  module.__dict__['__builtins__']=namespace
  exec(compile(raw,module.__file__,'exec'),module.__dict__)
  return module
 def scoped_import(name,globals=None,locals=None,fromlist=(),level=0):
  if level==0 and name in images:return load(name)
  return real_import(name,globals,locals,fromlist,level)
 return load('stage17_formal_archive_v1'),load('stage17_formal_archive_custody_v1')
