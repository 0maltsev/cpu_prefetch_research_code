#!/usr/bin/env python3
"""Build only against the retained qualified 42f2ebb package, without Ninja.

Writes solely below this directory. Never contacts the stand or executes a
capture. Like the original native query builder, binds inputs before and after
building and checks the linked foundation identity with --identity only.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVISION = '42f2ebb96f751319cd55fc1fabdcf7f91ab1c8d0'
INVENTORY_SHA = '8e657978d848ae8c633036536357741fff02388788b0f6a18f2e13e5dc6d5397'
VERIFICATION_SHA = 'd54adf034fc514e2fb75e3f2f428c0bc2d88e9024d764279779a251b3fac38f3'
VERIFIED = ROOT / 'build/stage17-step5-prep/recovery-v23-continuation/verified-42f2ebb-1'
RUNTIME = ROOT / 'build/ext007-runtime-20261101/root'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def binding(path):
    requested = Path(path).absolute()
    path = requested.resolve(strict=True)
    before = path.stat()
    require(stat.S_ISREG(before.st_mode), 'nonregular build input: ' + str(path))
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    after = path.stat()
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    require(stamp(before) == stamp(after), 'input changed during hashing')
    return dict(path=str(requested), resolved_path=str(path),
                size_bytes=after.st_size, sha256=digest)


def identity(item):
    return item['size_bytes'], item['sha256']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sanitizers', action='store_true',
                        help='ASan/UBSan for caller only; qualified libraries stay original')
    args = parser.parse_args()
    out = HERE / ('asan-ubsan' if args.sanitizers else 'release')
    require(not out.exists(), 'output exists; preserve evidence and choose a fresh review')
    verification_path = VERIFIED / 'verification.json'
    require(binding(verification_path)['sha256'] == VERIFICATION_SHA,
            'retained package verification changed')
    verification = json.loads(verification_path.read_bytes())
    require(verification['source_revision'] == REVISION and
            verification['inventory_sha256'] == INVENTORY_SHA and
            verification['bundle_profile'] == 'STAGE17-PILOT-CANDIDATE-BUNDLE-v26',
            'different qualified package')
    bundle = Path(verification['bundle_root'])
    inventory_path = bundle / 'BUNDLE_INVENTORY.json'
    require(binding(inventory_path)['sha256'] == INVENTORY_SHA, 'inventory changed')
    inventory = json.loads(inventory_path.read_bytes())
    require(inventory['source_revision'] == REVISION, 'inventory revision differs')
    index = {row['path']: row for row in inventory['files']}
    require(len(index) == len(inventory['files']), 'duplicate inventory members')

    def member(name):
        path = bundle / name
        require(path.resolve(strict=True) == path, 'symlink package member')
        require(identity(binding(path)) == identity(index[name]), 'package drift: ' + name)
        return path

    # Entire native source/header closure and every archive we actually link
    # are checked against the immutable authenticated inventory, not the tree.
    members = sorted(name for name in index if name.startswith(('include/', 'src/')))
    libraries = ['runner_core', 'calibration', 'storage', 'lifecycle', 'timing',
                 'platform', 'workload', 'protocol', 'queue', 'foundation']
    library_paths = [member('release/lib/libcpu_prefetch_' + name + '.a') for name in libraries]
    for name in ('BUNDLE_MANIFEST.json', 'build-provenance/compile_commands.json',
                 verification['worker_member_path']):
        members.append(name)
    package_inputs = [member(name) for name in members]
    require(identity(binding(bundle / verification['worker_member_path'])) ==
            (verification['worker_size_bytes'], verification['worker_sha256']), 'worker changed')

    compiler = RUNTIME / 'usr/bin/g++'
    linker = RUNTIME / 'usr/bin/ld'
    loader = RUNTIME / 'usr/lib/ld-linux-x86-64.so.2'
    crypto = RUNTIME / 'usr/lib/libcrypto.so'
    zstd = RUNTIME / 'usr/lib/libzstd.so.1.5.7'
    source = HERE / 'service_layout.cpp'
    original_query_builder = ROOT / 'build/stage17-step5-prep/formal-q16a-analysis-1/native-geometry-dd981b4/build_and_record.py'
    inputs = [verification_path, inventory_path, Path(__file__), source,
              original_query_builder, compiler, linker, loader, crypto, zstd,
              *package_inputs, *library_paths]
    inputs = [binding(p) for p in dict.fromkeys(inputs)]
    commands = []
    # Prevent ambient include/library/compiler overrides from crossing the
    # explicit package/runtime boundary. Record actual system header closure.
    env = dict(os.environ)
    for name in ('CPATH', 'CPLUS_INCLUDE_PATH', 'C_INCLUDE_PATH', 'LIBRARY_PATH',
                 'COMPILER_PATH', 'GCC_EXEC_PREFIX', 'LD_PRELOAD', 'LD_LIBRARY_PATH'):
        env.pop(name, None)
    env['PATH'] = str(RUNTIME / 'usr/bin') + ':/usr/bin:/bin'
    env['LD_LIBRARY_PATH'] = str(RUNTIME / 'usr/lib')
    flags = ['--sysroot=' + str(RUNTIME), '-I' + str(bundle / 'include'),
             '-O3', '-DNDEBUG', '-std=c++20', '-Wall', '-Wextra', '-Wpedantic',
             '-Wconversion', '-Wsign-conversion', '-Wshadow', '-Wformat=2', '-Wundef', '-Werror']
    if args.sanitizers:
        flags += ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    out.mkdir()
    obj, binary = out / 'service_layout.o', out / 'service-layout'
    compile_command = [str(compiler), *flags, '-MD', '-MF', str(out / 'service_layout.d'),
                       '-c', str(source), '-o', str(obj)]
    link_command = [str(compiler), *flags, str(obj), '-Wl,--start-group',
                    *map(str, library_paths), '-Wl,--end-group', str(crypto), str(zstd),
                    '-ldl', '-pthread', '-Wl,-Map=' + str(out / 'service-layout.map'),
                    '-Wl,--dynamic-linker=' + str(loader),
                    '-Wl,-rpath,' + str(RUNTIME / 'usr/lib'), '-o', str(binary)]
    for command in (compile_command, link_command):
        commands.append(command)
        run = subprocess.run(command, cwd=HERE, env=env, capture_output=True, timeout=120)
        stem = 'compile' if command == compile_command else 'link'
        (out / (stem + '.stdout')).write_bytes(run.stdout)
        (out / (stem + '.stderr')).write_bytes(run.stderr)
        require(run.returncode == 0, stem + ' failed; inspect ' + str(out / (stem + '.stderr')))

    dependencies = shlex.split((out / 'service_layout.d').read_text().replace('\\\n', ' '))[1:]
    headers = []
    for name in dependencies:
        path = Path(name).absolute()
        if path == source:
            continue
        if path.is_relative_to(bundle):
            member(path.relative_to(bundle).as_posix())
        else:
            require(path.is_relative_to(RUNTIME), 'header escaped managed package/runtime: ' + str(path))
        headers.append(binding(path))
    dynamic_command = [str(loader), '--library-path', str(RUNTIME / 'usr/lib'), '--list', str(binary)]
    commands.append(dynamic_command)
    dynamic = subprocess.check_output(dynamic_command, env=env, timeout=10, text=True)
    (out / 'runtime-libraries.txt').write_text(dynamic)
    shared = []
    for line in dynamic.splitlines():
        if ' => /' in line:
            path = Path(line.split(' => ', 1)[1].split(' (', 1)[0])
            require(path.is_relative_to(RUNTIME), 'dynamic library escaped managed runtime')
            shared.append(binding(path))
    require(inputs == [binding(row['path']) for row in inputs], 'build inputs changed')
    require(headers == [binding(row['path']) for row in headers], 'headers changed')
    identity_command = [str(binary), '--identity']
    commands.append(identity_command)
    env['ASAN_OPTIONS'] = 'detect_leaks=0:halt_on_error=1'
    env['UBSAN_OPTIONS'] = 'halt_on_error=1:print_stacktrace=1'
    actual = json.loads(subprocess.check_output(identity_command, env=env, timeout=35))
    require(actual['source_revision'] == REVISION and actual['source_dirty'] is False,
            'linked foundation identity differs')
    result = dict(schema_version='software-native-service-layout-build/1', status='PASS',
                  native_library_source_revision=REVISION, qualified_release_claim=False,
                  execution_authority=False, performance_measurement=False,
                  hardware_observation=False, phase18_authority=False,
                  sanitizers='caller ASan/UBSan only' if args.sanitizers else 'none',
                  identity=actual, input_bindings=inputs, header_bindings=headers,
                  dynamic_library_bindings=shared, commands=commands,
                  binary=binding(binary), object=binding(obj),
                  dependency_file=binding(out / 'service_layout.d'),
                  link_map=binding(out / 'service-layout.map'),
                  compiler_version=subprocess.check_output([str(compiler), '--version'], env=env, text=True))
    (out / 'provenance.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps(dict(status='PASS', binary=str(binary), provenance=str(out / 'provenance.json'))))


if __name__ == '__main__':
    main()
