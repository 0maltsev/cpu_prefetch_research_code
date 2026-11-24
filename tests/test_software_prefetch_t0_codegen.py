"""Exact static mapping, legacy default and retained-report drift tests."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import check_software_prefetch_mapping_codegen as audit


def assembly(rows):
    return '\n'.join(f'00000000000000{i:02x} <{name}>:\n  {i:02x}: {body}\n  {i+1:02x}: ret'
        for i,(name,body) in enumerate(rows))


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.good=assembly([(s,'prefetcht0 (%rdi)') for s in audit.T0_SYMBOLS.values()])
        self.bad=assembly([(s,'prefetchw (%rdi)') for s in audit.T0_MUTANTS[:-2]]+
            [(audit.T0_MUTANTS[-2],'prefetcht0 (%rdi)\n  0f: prefetcht0 (%rdi)'),(audit.T0_MUTANTS[-1],'nop')])

    def test_three_actual_t0_roles_are_required(self):
        values=audit.inspect_t0_probe(self.good)
        self.assertEqual(set(values),{'ring_producer_write','ring_consumer_read','successor_header'})
        self.assertTrue(all(v['instruction']=='PREFETCHT0' for v in values.values()))

    def test_original_mapping_rejects_t0_probe_and_keeps_original_three_sites(self):
        with self.assertRaisesRegex(RuntimeError,'missing or empty'):audit.inspect_probe(self.good)
        original=assembly([(audit.PRODUCER_SYMBOL,'prefetchw (%rdi)'),
            (audit.CONSUMER_SYMBOL,'prefetcht0 (%rdi)'),(audit.SUCCESSOR_SYMBOL,'prefetcht0 (%rdi)')])
        self.assertEqual(audit.inspect_probe(original)['ring_producer_write']['instruction'],'PREFETCHW')
        with self.assertRaisesRegex(RuntimeError,'missing or empty'):audit.inspect_t0_probe(original)

    def test_wrong_intent_duplicate_missing_and_other_hints_reject_each_role(self):
        for symbol in audit.T0_SYMBOLS.values():
            for wrong in ('prefetchw (%rdi)','prefetcht1 (%rdi)','prefetchnta (%rdi)','nop',
                    'prefetcht0 (%rdi)\n  0f: prefetcht0 (%rdi)'):
                rows=[(s,wrong if s==symbol else 'prefetcht0 (%rdi)') for s in audit.T0_SYMBOLS.values()]
                with self.subTest(symbol=symbol,wrong=wrong),self.assertRaisesRegex(RuntimeError,'exactly one'):
                    audit.inspect_t0_probe(assembly(rows))

    def test_all_five_negative_sites_are_rejected(self):
        result=audit.inspect_t0_mutants(self.bad)
        self.assertEqual(set(result),set(audit.T0_MUTANTS));self.assertTrue(all(v['status']=='REJECTED' for v in result.values()))

    def test_repaired_or_missing_mutant_cannot_pass_negative_checks(self):
        for symbol in audit.T0_MUTANTS:
            rows=[(s,'prefetcht0 (%rdi)' if s==symbol else 'prefetchw (%rdi)') for s in audit.T0_MUTANTS]
            with self.subTest(symbol=symbol),self.assertRaisesRegex(RuntimeError,'unexpectedly accepted'):
                audit.inspect_t0_mutants(assembly(rows))
        with self.assertRaisesRegex(RuntimeError,'missing or empty'):audit.inspect_t0_mutants('')

    def report_fixture(self):
        tmp=tempfile.TemporaryDirectory(prefix='prefetch-t0-');self.addCleanup(tmp.cleanup);root=Path(tmp.name)
        for name in audit.T0_SOURCES:
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(name.encode())
        binary=root/'probe';binary.write_bytes(b'software ELF placeholder, not executed')
        mutant=root/'mutant';mutant.write_bytes(b'software mutant placeholder, not executed')
        report=dict(schema_version='cpu-prefetch-software-prefetch-mapping-codegen/1',mapping_id=audit.T0_MAPPING,
            status='PASS',missing_tools=[],binary=dict(sha256=audit.file_sha256(binary)),
            mutant=dict(sha256=audit.file_sha256(mutant)),rule_set=dict(sha256=audit.file_sha256(root/audit.T0_SOURCES[-1])),
            source_evidence={p:audit.file_sha256(root/p) for p in audit.T0_SOURCES},tools={})
        for kind,version in [('GNU_OBJDUMP','GNU Binutils 2.46.0'),('LLVM_OBJDUMP','LLVM 22.1.6')]:
            report['tools'][kind]=dict(status='PASS',version=version,mapping=audit.inspect_t0_probe(self.good),
                mutant=audit.inspect_t0_mutants(self.bad))
        return report,dict(binary=binary,mutant=mutant,source_root=root)

    def test_exact_software_source_report_replays(self):
        report,args=self.report_fixture();audit.validate_t0_report(report,**args)

    def test_retained_binary_source_and_rule_drift_reject(self):
        report,args=self.report_fixture()
        for key in ('binary','mutant','rule_set'):
            changed=copy.deepcopy(report);changed[key]['sha256']='f'*64
            with self.subTest(key=key),self.assertRaises(RuntimeError):audit.validate_t0_report(changed,**args)
        for path in audit.T0_SOURCES:
            changed=copy.deepcopy(report);changed['source_evidence'][path]='f'*64
            with self.subTest(path=path),self.assertRaises(RuntimeError):audit.validate_t0_report(changed,**args)

    def test_missing_tool_wrong_llvm_partial_sites_and_false_rejection_reject(self):
        report,args=self.report_fixture()
        edits=[lambda r:r['tools'].pop('LLVM_OBJDUMP'),lambda r:r.update(mapping_id=audit.ORIGINAL_MAPPING),
            lambda r:r['tools']['LLVM_OBJDUMP'].update(version='LLVM 21.1.0'),
            lambda r:r['tools']['GNU_OBJDUMP'].update(version='LLVM 22.1.6'),
            lambda r:r['tools']['GNU_OBJDUMP']['mapping'].pop('successor_header'),
            lambda r:r['tools']['GNU_OBJDUMP']['mapping']['ring_producer_write'].update(instruction='PREFETCHW'),
            lambda r:r['tools']['GNU_OBJDUMP']['mutant'].pop(audit.T0_MUTANTS[-1]),
            lambda r:r['tools']['GNU_OBJDUMP']['mutant'][audit.T0_MUTANTS[0]]['counts'].pop('prefetchw'),
            lambda r:r['tools']['GNU_OBJDUMP']['mutant'][audit.T0_MUTANTS[0]].update(status='PASS')]
        for edit in edits:
            changed=copy.deepcopy(report);edit(changed)
            with self.assertRaises(RuntimeError):audit.validate_t0_report(changed,**args)

    def test_t0_cli_requires_source_binding_before_reading_files(self):
        script=Path(audit.__file__)
        result=subprocess.run([sys.executable,'-B',str(script),'--mapping-id',audit.T0_MAPPING,
            '--binary','absent','--mutant','absent','--output','absent'],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,2);self.assertIn('requires --source-root',result.stderr)

    def test_missing_disassemblers_write_blocked_report_and_exit_three(self):
        _,args=self.report_fixture();output=args['source_root']/'blocked.json'
        result=subprocess.run([sys.executable,'-B',audit.__file__,'--mapping-id',audit.T0_MAPPING,
            '--source-root',str(args['source_root']),'--binary',str(args['binary']),'--mutant',str(args['mutant']),
            '--output',str(output),'--gnu-objdump','ABSENT-T0-GNU','--llvm-objdump','ABSENT-T0-LLVM'],
            capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,3)
        value=json.loads(output.read_bytes());self.assertEqual(value['status'],'BLOCKED_MISSING_TOOL')
        self.assertEqual(set(value['missing_tools']),{'GNU_OBJDUMP','LLVM_OBJDUMP'})


if __name__=='__main__':unittest.main()
