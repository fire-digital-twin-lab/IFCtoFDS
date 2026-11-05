"""Read-only scheduler supervision probe; not a scientific or database verdict."""


def is_scheduler_healthy(service) -> bool:
    """Detect a dead supervisor without starting workers or touching artifacts.

    Idle instances need not have a supervisor thread yet: the first accepted
    job starts it. A queued/running job without a thread is not healthy.
    """
    with service.lock:
        if service.closed:
            return False
        thread = service.thread
        if thread is None:
            return service.repository.count_pending() == 0
        return bool(thread.is_alive())
