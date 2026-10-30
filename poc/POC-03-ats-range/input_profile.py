"""Validate actual input bytes for a raw lab; this never grants sample approval."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import stat

PROTOTYPE_BYTES = 67108864
PROTOTYPE_COLLECTION_BYTES = 1073741824


def _unique(rows):
    result = {}
    for key, value in rows:
        if key in result:
            raise ValueError('duplicate fixture manifest key')
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError('nonfinite fixture value')


def _integer(value, minimum=1):
    if type(value) is not int or value < minimum:
        raise ValueError('positive integer input/profile bound required')
    return value


def _signature(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns)


def _path_signature(value):
    if os.name != 'nt':
        return _signature(value)
    # On this Windows runtime fstat exposes change time while path stat still
    # exposes creation time as ctime. Compare like identity/birth fields here;
    # retain the full change-time comparison between both reads of the same FD.
    return (value.st_dev, value.st_ino, value.st_mode, value.st_size,
            value.st_mtime_ns, getattr(value, 'st_birthtime_ns', None))


def _actual_digest(path, size):
    if path.is_symlink():
        raise ValueError('input symlink refused')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size != size:
            raise ValueError('actual input size/type differs from fixed manifest')
        value = hashlib.sha256()
        remaining = size
        # Keep the already validated descriptor and one fixed raw-file slot.
        # No previous returned bytes survive into the next native read.
        with os.fdopen(fd, 'rb', buffering=0, closefd=False) as stream, memoryview(bytearray(1048576)) as backing:
            while remaining:
                if backing.obj.__alloc__() != 1048577:
                    raise OSError('unqualified fixed input backing capacity')
                with backing[:min(len(backing), remaining)] as target:
                    count = stream.readinto(target)
                    if type(count) is not int or not 0 <= count <= len(target):
                        raise OSError('invalid raw input read count')
                    if not count:
                        raise ValueError('input shortened during validation')
                    remaining -= count
                    with target[:count] as block:value.update(block)
            if backing.obj.__alloc__() != 1048577:
                raise OSError('unqualified fixed input backing capacity')
            with backing[:1] as target:count = stream.readinto(target)
            if type(count) is not int or not 0 <= count <= 1:
                raise OSError('invalid raw input read count')
            if count:
                raise ValueError('input grew during validation')
        if _signature(os.fstat(fd)) != _signature(before) or _path_signature(path.lstat()) != _path_signature(before):
            raise ValueError('input identity/content metadata changed during validation')
        return value.hexdigest()
    finally:
        os.close(fd)


def prepare_input_pair(cfg, manifest_path, raw, pinned):
    """Return hash-verified real inputs; approval remains an external prerequisite.

    The original prototype keeps its exact hashes and numeric limits. The
    explicit representative profile binds a fixed manifest and finite caller
    budgets, allowing larger real files without treating declared size as data.
    """
    if not isinstance(raw, bytes) or len(raw) > 65536:
        raise ValueError('bounded fixture manifest bytes required')
    manifest = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique, parse_constant=_nonfinite)
    if not isinstance(manifest, dict):
        raise ValueError('fixture manifest object required')
    minimum = _integer(cfg['minimumInputBytes'], PROTOTYPE_BYTES)
    slice_bytes = _integer(cfg['sliceBytes'])
    buffered = _integer(cfg['maximumBufferedBytes'])
    if slice_bytes != 1048576 or not slice_bytes <= buffered < minimum:
        raise ValueError('actual input must exceed the declared Slice and buffering bounds')
    profile = cfg.get('fixtureProfile', 'prototype-64m-v1')
    if profile == 'prototype-64m-v1':
        if (minimum != PROTOTYPE_BYTES or cfg['maximumOriginRequests'] != 2048
                or cfg.get('maximumCollectionBytes', PROTOTYPE_COLLECTION_BYTES) != PROTOTYPE_COLLECTION_BYTES):
            raise ValueError('original prototype limits must remain fixed')
        rows = {}
        for label, (name, sha) in pinned.items():
            row = manifest['base' if label == 'base' else 'changedVersion']
            if not isinstance(row, dict) or row.get('file') != name or row.get('sha256') != sha:
                raise ValueError('fixed prototype input pair mismatch')
            rows[label] = dict(file=name, sha256=sha, sizeBytes=PROTOTYPE_BYTES)
    elif profile == 'representative-v1':
        if (type(manifest.get('schemaVersion')) is not int or manifest['schemaVersion'] != 1
                or manifest.get('kind') != 'poc003-representative-pair-v1'
                or set(manifest) != {'schemaVersion', 'kind', 'base', 'changedVersion'}):
            raise ValueError('explicit representative pair manifest required')
        if (not isinstance(cfg.get('fixtureManifestSha256'), str)
                or not re.fullmatch('[0-9a-f]{64}', cfg['fixtureManifestSha256'])
                or hashlib.sha256(raw).hexdigest() != cfg['fixtureManifestSha256']):
            raise ValueError('representative manifest hash mismatch')
        maximum = _integer(cfg['maximumInputBytes'], minimum)
        rows = {label: manifest[key] for label, key in [('base', 'base'), ('changed', 'changedVersion')]}
        for row in rows.values():
            if not isinstance(row, dict) or set(row) != {'file', 'sha256', 'sizeBytes'}:
                raise ValueError('exact input file/hash/size fields required')
            size = _integer(row['sizeBytes'], minimum)
            if size > maximum:
                raise ValueError('input exceeds the declared per-file resource budget')
        source_slices = lambda size: (size + slice_bytes - 1)//slice_bytes
        origin_minimum = max(2048, 4*source_slices(rows['base']['sizeBytes'])+source_slices(rows['changed']['sizeBytes'])+64)
        _integer(cfg['maximumOriginRequests'], origin_minimum)
        # The unchanged matrix includes four base-object equivalents and one
        # changed representation, plus bounded small Range/error responses.
        _integer(cfg['maximumCollectionBytes'], 4*rows['base']['sizeBytes']+rows['changed']['sizeBytes']+2*slice_bytes)
    else:
        raise ValueError('unknown fixture profile')
    if rows['base']['file'] == rows['changed']['file'] or rows['base']['sha256'] == rows['changed']['sha256']:
        raise ValueError('distinct fixed base/changed files and content required')
    inputs = {}
    for label, row in rows.items():
        name, sha, size = row['file'], row['sha256'], row['sizeBytes']
        if not isinstance(name, str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}', name):
            raise ValueError('single portable input filename required')
        if not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{64}', sha):
            raise ValueError('fixed lowercase SHA256 required')
        path = Path(manifest_path).parent/name
        if _actual_digest(path, size) != sha:
            raise ValueError('actual input hash differs from fixed manifest')
        inputs[label] = dict(path=str(path.resolve()), sha256=sha, sizeBytes=size, etag='"sha256-'+sha+'"')
    return inputs
