"""Bounded cleanup of allocated or started multiprocessing workers."""


def stop_process(process, *, timeout: float = 2.0) -> bool:
    """Return whether termination was needed; never join an unstarted worker."""
    if process is None:
        return False
    forced = False
    if process.pid is not None:
        process.join(timeout=max(0.0, float(timeout)))
        if process.is_alive():
            forced = True
            process.terminate()
            process.join(timeout=1.0)
        if process.is_alive():
            raise RuntimeError("worker did not exit after termination; retained for cleanup")
    process.close()
    return forced


def close_queues(*channels) -> None:
    for channel in channels:
        channel.cancel_join_thread()
        channel.close()
