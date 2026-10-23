"""Execute actual queue supervision using replaceable process/store/clock ports."""

from ifc_to_fds.modules.jobs.api import JobService


class MemoryStore:
    def __init__(self): self.cache = {}
    def get(self, key): return self.cache.get(key)
    def set(self, key, value): self.cache[key] = value
    def all_jobs(self): return list(self.cache.values())
    def items(self): return list(self.cache.items())
    def snapshot(self, key): return dict(self.cache[key])
    def delete(self, key): self.cache.pop(key, None)
    def count_pending(self): return sum(job['state'] in ('QUEUED', 'RUNNING') for job in self.cache.values())
    def read_result(self, key): return self.cache[key]['result']


class Processes:
    def __init__(self): self.launched = []; self.stopped = []; self.bytes = 0
    def launch(self, directory):
        self.launched.append(directory)
        return Process()
    def rss(self, process): return self.bytes
    def stop(self, process): self.stopped.append(process)


class Process:
    pid = 123
    def poll(self): return None


class Retention:
    def cleanup_orphaned_directories(self, service, max_age_s=None): pass
    def sweep(self, service, now): pass


def service(tmp_path):
    store, processes = MemoryStore(), Processes()
    queue = JobService(root=tmp_path, repository=store, processes=processes,
                       retention=Retention(), clock=lambda: 100, max_memory_mb=10)
    return queue, store, processes


def test_dispatch_and_rss_limit_execute_real_supervisor_without_native_process(tmp_path):
    queue, store, processes = service(tmp_path)
    directory = tmp_path / 'job-fixture'
    directory.mkdir()
    store.set('fixture', {'id':'fixture', 'state':'QUEUED', 'created':99,
                          'directory':str(directory), 'process':None})
    queue.tick()
    assert processes.launched == [str(directory)]
    assert store.get('fixture')['state'] == 'RUNNING'
    assert store.get('fixture')['started'] == 100
    processes.bytes = 20 * 1024**2
    queue.tick()
    assert len(processes.stopped) == 1
    assert store.get('fixture')['state'] == 'FAILED'
    assert 'RESOURCE_EXHAUSTED' in store.get('fixture')['error']
    assert (directory / 'diagnostics.json').is_file()
    assert not list(tmp_path.glob('*.sqlite3')), 'Injected store must not create a native database'
    queue.close()


def test_queue_timeout_does_not_launch_a_worker(tmp_path):
    queue, store, processes = service(tmp_path)
    queue.queue_timeout_s = 10
    directory = tmp_path / 'job-expired'
    directory.mkdir()
    store.set('expired', {'id':'expired', 'state':'QUEUED', 'created':1,
                          'directory':str(directory), 'process':None})
    queue.tick()
    assert store.get('expired')['state'] == 'TIMED_OUT'
    assert processes.launched == []
    queue.close()
