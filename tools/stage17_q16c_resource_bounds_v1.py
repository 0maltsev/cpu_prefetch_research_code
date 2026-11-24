"""D273 retained symbolic metadata/allocation model; software arithmetic only.

Static D234 metadata helper with its original type-width envelopes and runtime
allowances. No observations, allocations of represented arrays or rate inference.
Scheduled prospective metadata is bounded by the retained4MiB fixed allowance;
actual schedule arrays remain binary artifacts, not JSON arrays.
"""
import copy
import ctypes
from pathlib import Path
import stage17_observation_metadata_model_v1 as model

MIB=1024**2
COMMON_KEYS=('worker_mappings worker_stacks worker_preparation core monitor_arena hardware_preparation '
    'environment_preparations environment_samples environment_group_order thread_preparations '
    'regions residency controls tls_snapshots').split()
FIXED_METADATA_ALLOWANCE=4*MIB
FIXED_NATIVE_RUNTIME_ALLOWANCE=2*1024**3


def require(ok,message):
    if not ok:raise ValueError('Q16c resources: '+message)


def allocation_charge(n):
    return max(32,(n+23)//16*16)+(8192 if n>=128*1024 else 0)


def allocation_tree(value):
    if isinstance(value,model.Repeat):
        return ((allocation_charge(value.count*64) if value.count else 0)+value.count*allocation_tree(value.value))
    if isinstance(value,list):
        return ((allocation_charge(len(value)*64) if value else 0)+sum(allocation_tree(x) for x in value))
    if isinstance(value,dict):
        return sum(allocation_charge(128)+(allocation_charge(len(k)+1) if len(k)>15 else 0)+allocation_tree(v)
                   for k,v in value.items())
    if type(value) in (int,str):
        text=str(value);return allocation_charge(len(text)+1) if len(text)>15 else 0
    return 0


def metadata_bound(resources,monitoring):
    require(resources['tls_module_capacity']==8 and resources['thread_stat_bytes']==4096
        and resources['thread_status_bytes']==4096 and resources['thread_affinity_words']==4,
        'retained TLS/thread capacities required')
    require(all(n%4096==0 for n in resources['region_bytes']),'actual4096-page aligned native regions required')
    full=model.control(dict(layout=resources),[0,0]);common={k:full[k] for k in COMMON_KEYS}
    pages=[n//4096 for n in resources['region_bytes']]
    common['residency']=[model.residency(monitoring['during_page_count'][i] if moment==1 else n)
        for _phase in range(2) for moment in range(3) for i,n in enumerate(pages)]
    preparations=[];samples=[]
    for source in monitoring['environment_sources']:
        prep=copy.deepcopy(model.ENV_PREP)
        prep['plan']=dict(path_bytes=list(source['path'].encode()),
            **{k:source[k] for k in ('byte_capacity','chunk_bytes','max_data_reads','requested')})
        preparations.append(prep);sample=copy.deepcopy(model.ENV_SAMPLE)
        sample['raw_bytes']=model.Repeat(255,source['byte_capacity'])
        sample['reads']=model.Repeat(model.FILE_READ,source['max_data_reads']);samples.extend([sample]*6)
    common['environment_preparations']=preparations;common['environment_samples']=samples
    common_bytes=model.size(common);control=common_bytes+FIXED_METADATA_ALLOWANCE
    tree=allocation_tree(common)+64*FIXED_METADATA_ALLOWANCE
    cold_heap=max(2*tree,tree+3*control,2*control)+FIXED_NATIVE_RUNTIME_ALLOWANCE
    return dict(common_observation_json_bytes=common_bytes,control_bytes=control,
        fixed_formal_metadata_allowance_bytes=FIXED_METADATA_ALLOWANCE,active_json_tree_model_bytes=tree,
        cold_heap_model_bytes=cold_heap,model_caveat='Active allocation model, not retained allocator/RSS certification')


def zstd_bounder(path):
    library=ctypes.CDLL(str(Path(path).resolve(strict=True)))
    library.ZSTD_versionNumber.restype=ctypes.c_uint
    require(library.ZSTD_versionNumber()==10507,'accepted zstd1.5.7 required')
    library.ZSTD_compressBound.argtypes=[ctypes.c_size_t];library.ZSTD_compressBound.restype=ctypes.c_size_t
    return library.ZSTD_compressBound


def archive_upper(size,block_bytes,compress_bound):
    full,tail=divmod(size,block_bytes)
    return 16+32768+56+full*(64+compress_bound(block_bytes))+(64+compress_bound(tail) if tail else 0)
