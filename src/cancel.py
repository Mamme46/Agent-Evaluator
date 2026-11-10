_CANCELLED = set()


class ScanCancelled(Exception):
    pass


def request_cancel(scan_id):
    _CANCELLED.add(scan_id)


def is_cancelled(scan_id):
    return scan_id in _CANCELLED


def clear(scan_id):
    _CANCELLED.discard(scan_id)