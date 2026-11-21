import os, subprocess, sys, json
from pathlib import Path
root=Path.cwd(); name=sys.argv[1]; base=root/'build/stage17-s180-native'; tool=root/'build/ext007-toolchain-20261101/root/usr'; work=base/name
env=dict(os.environ,PATH=str(tool/'bin')+':'+os.environ['PATH'],LD_LIBRARY_PATH=str(tool/'lib'),ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',TSAN_OPTIONS='halt_on_error=1')
for phase,args in [('build',[str(tool/'bin/cmake'),'--build',str(work),'--target','cpu_prefetch_s180_io_tests','-j2']),('tests',[str(work/'cpu_prefetch_s180_io_tests'),'--gtest_color=no','--gtest_filter=S180Worker.WholeSecond*:S180Worker.ActualSealed*:S180Worker.Window*'])]:
 with (base/(name+'-s180epoch-'+phase+'.txt')).open('wb') as output:
  result=subprocess.run(args,env=env,stdout=output,stderr=subprocess.STDOUT)
 print(json.dumps(dict(variant=name,phase=phase,exit_code=result.returncode)),flush=True)
 if result.returncode: raise SystemExit(1)
