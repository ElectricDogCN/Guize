"""Keep original resource caps while retrying a torn live directory traversal."""
import os
import stat
import time


_MAX_TRAVERSALS = 8


def writable_disk_guard(writable, attached_paths, deadline):
    """Retry a whole scan on ENOENT; never accept a partial traversal."""
    def within_time():
        if time.monotonic() >= deadline:
            raise TimeoutError('writable disk observation exceeded the existing run deadline')

    for traversal in range(_MAX_TRAVERSALS):
        within_time()
        if not stat.S_ISDIR(writable.lstat().st_mode):
            raise ValueError('expected owned writable directory')
        total = other = count = 0
        pending = [writable]
        try:
            while pending:
                within_time()
                with os.scandir(pending.pop()) as entries:
                    for entry in entries:
                        within_time()
                        info = entry.stat(follow_symlinks=False)
                        if stat.S_ISLNK(info.st_mode):
                            raise ValueError('unexpected writable symlink')
                        if stat.S_ISDIR(info.st_mode):
                            pending.append(entry.path)
                        elif stat.S_ISREG(info.st_mode):
                            count += 1
                            total += info.st_size
                            if '/cache/' not in entry.path:
                                other += info.st_size
                                if info.st_size > 128*1024*1024:
                                    raise ValueError('noncache file budget')
                            if count > 5000 or total > 2*1024**3 or other > 1792*1024**2:
                                raise ValueError('private writable byte/file budget')
        except FileNotFoundError:
            # A producer may link the final name then unlink its .part file.
            # A missing entry invalidates this observation, never just that entry.
            if traversal + 1 == _MAX_TRAVERSALS:
                raise RuntimeError('writable directory changed throughout eight complete scan attempts')
            continue
        for path in attached_paths:
            if path.stat().st_size > 16*1024**2:
                raise ValueError('attached raw output budget')
        within_time()
        return {'files': count, 'logicalBytes': total, 'nonCacheLogicalBytes': other,
                'transientEnoentRescans': traversal}
