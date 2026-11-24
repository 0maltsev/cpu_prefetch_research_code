"""S180 root verification of unchanged original-owner SSHSIG trust bytes.

The original journal still replays under its actual UID1000 owner. Only this
root controller's verifier receives a temporary root-owned copy of the same
hash-bound public allowed-signers bytes. Original locators, owner, permissions,
signed payloads, principal and namespace remain untouched. No key is copied.
"""
from __future__ import annotations
import copy
import hashlib
import os
from pathlib import Path
import stat
import tempfile

import stage17_formal_archive_v1 as archive
import stage17_phase_controller_v2 as legacy

ControllerError=legacy.ControllerError
_now=legacy._now
OWNER_UID=1000
MAX=65536


def require(ok,message):
    if not ok:raise ControllerError('S180 original-owner signature: '+message)


def _public_bytes(path,measurements,fd,expected_uid):
    before=os.fstat(fd)
    require(stat.S_ISREG(before.st_mode) and before.st_uid==expected_uid and before.st_nlink==1
        and not before.st_mode&0o022,'original public trust owner/protection differs')
    require(0<before.st_size<=MAX and before.st_size==measurements['allowed_signers_size_bytes'],
        'original public trust extent differs')
    raw=os.pread(fd,before.st_size+1,0)
    require(len(raw)==before.st_size and hashlib.sha256(raw).hexdigest()==measurements['allowed_signers_sha256'],
        'original public trust bytes differ')
    require(archive.file_stamp(before)==archive.file_stamp(os.fstat(fd))
        ==archive.file_stamp(path.stat(follow_symlinks=False)),'original public trust changed during read')
    return raw,archive.file_stamp(before)


def _projected_verify(payload,signature,trust,raw):
    """Actual unchanged legacy verifier over an exclusively owned public copy."""
    with tempfile.TemporaryDirectory(prefix='cpu-prefetch-s180-public-trust-',dir='/run') as directory:
        path=Path(directory)/'allowed-signers'
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        try:
            require(os.write(fd,raw)==len(raw),'partial public trust snapshot')
            os.fsync(fd)
        finally:os.close(fd)
        projected=copy.deepcopy(trust)
        projected['measurements']['allowed_signers_path']=str(path)
        legacy._verify_signature(payload,Path(signature),projected)


def _verify_signature(payload,signature,trust):
    if os.geteuid()!=0:return legacy._verify_signature(payload,Path(signature),trust)
    require(os.getresuid()==(0,0,0),'full root credentials required')
    measurements=trust.get('measurements')
    require(type(measurements) is dict,'actual admitted trust measurements required')
    path=Path(measurements['allowed_signers_path'])
    require(path.is_absolute() and path.resolve(strict=True)==path,'canonical original public trust required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        owner=os.fstat(fd).st_uid
        # Preserve the ordinary same-owner contract (including disposable
        # software fixtures). The actual root route needs exactly UID1000.
        require(owner in (0,OWNER_UID),'unrecognized original public trust owner')
        raw,before=_public_bytes(path,measurements,fd,owner)
        if owner==0:legacy._verify_signature(payload,Path(signature),trust)
        else:_projected_verify(payload,Path(signature),trust,raw)
        after,_=_public_bytes(path,measurements,fd,owner)
        require(after==raw and before==archive.file_stamp(os.fstat(fd)),
            'original public trust changed through signature verification')
    finally:os.close(fd)
