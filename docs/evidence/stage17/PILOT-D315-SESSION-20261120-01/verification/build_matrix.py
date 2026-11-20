import json,os,subprocess,sys
from pathlib import Path
root=Path.cwd();name=sys.argv[1];base=root/'build/stage17-s180-native';tool=root/'build/ext007-toolchain-20261101/root/usr';clang='clang' in name;san='THREAD' if 'tsan' in name else 'ADDRESS_UNDEFINED'
work=base/name;env=dict(os.environ,PATH=str(tool/'bin')+':'+os.environ['PATH'],LD_LIBRARY_PATH=str(tool/'lib'),ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',TSAN_OPTIONS='halt_on_error=1')
cmd=[str(tool/'bin/cmake'),'-S',str(root),'-B',str(work),'-G','Ninja','-DCMAKE_CXX_COMPILER='+str(tool/'bin'/('clang++' if clang else 'g++')),'-DCMAKE_BUILD_TYPE=Debug','-DCMAKE_PREFIX_PATH='+str(tool),'-DCPU_PREFETCH_RAPIDCHECK_REVISION=ff6af6f','-DPython3_EXECUTABLE=/usr/bin/python3.14','-DCPU_PREFETCH_SANITIZER='+san,'-DCMAKE_GTEST_DISCOVER_TESTS_DISCOVERY_MODE=PRE_TEST']
if clang:cmd+=['-DCPU_PREFETCH_USE_LIBCXX=ON','-DCMAKE_CXX_FLAGS=-isystem '+str(tool/'include/c++/v1'),'-DCMAKE_EXE_LINKER_FLAGS=-L'+str(tool/'lib')+' -Wl,-rpath,'+str(tool/'lib'),'-DGTest_DIR='+str(tool.parent.parent/'clang-tests/usr/lib/cmake/GTest'),'-DRapidCheck_LIBRARY='+str(tool.parent.parent/'clang-tests/usr/lib/librapidcheck.a')]
for phase,args in [('configure',cmd),('build',[str(tool/'bin/cmake'),'--build',str(work),'--target','cpu_prefetch_s180_io_tests','-j','2']),('tests',[str(work/'cpu_prefetch_s180_io_tests'),'--gtest_color=no'])]:
 with (base/(name+'-s180io-'+phase+'.txt')).open('wb') as out:p=subprocess.run(args,env=env,stdout=out,stderr=subprocess.STDOUT)
 print(json.dumps(dict(variant=name,phase=phase,exit_code=p.returncode)),flush=True)
 if p.returncode:raise SystemExit(p.returncode if p.returncode>0 else 1)
