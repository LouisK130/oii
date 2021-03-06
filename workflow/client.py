import traceback

import requests

from oii.utils import gen_id
from oii.ioutils import isok

from oii.workflow import PID, STATE, NEW_STATE, EVENT, MESSAGE, UPSTREAM_STATE
from oii.workflow import WAITING, RUNNING, AVAILABLE, FOREVER, COMPLETED, TTL
from oii.workflow import ROLE, ANY
from oii.workflow import HEARTBEAT, RELEASED, ERROR
from oii.workflow import UPSTREAM, PRIORITY

import httplib as http

API_PREFIX='/workflow/api/v1'
DEFAULT_PORT=9270
DEFAULT_BASE_URL='http://localhost:%d' % DEFAULT_PORT

class Busy(Exception):
    """A mutex is busy"""
    pass

class InconsistentState(Exception):
    """The workflow products are in a logically inconsistent state"""
    pass

class WorkflowClient(object):
    def __init__(self, base_url=None):
        if base_url is None:
            base_url = DEFAULT_BASE_URL
        self.base_url = base_url
    def api(self, url):
        return self.base_url + API_PREFIX + url
    def wakeup(self, pid=None):
        if pid is None:
            return requests.get(self.api('/wakeup'))
        else:
            return requests.get(self.api('/wakeup/%s' % pid))
    def start_next(self,roles,state=WAITING,ttl=None):
        if isinstance(roles,basestring):
            roles = [roles]
        url = self.api('/start_next/%s' % '/'.join(roles))
        return requests.post(url, data={
            STATE: state,
            TTL: ttl
        })
    def start_all(self,roles,expire=False,state=WAITING,ttl=None):
        while True:
            if expire:
                self.expire()
            r = self.start_next(roles,state=state,ttl=ttl)
            if not isok(r):
                return
            job = r.json()
            yield job
    def create(self,pid,**d):
        return requests.put(self.api('/create/%s' % pid), data=d)
    def update_if(self,pid, **d):
        """d must contain STATE and NEW_STATE,
        d can also contain EVENT, MESSAGE"""
        return requests.patch(self.api('/update_if/%s' % pid), data=d)
    def delete(self,pid):
        return requests.delete(self.api('/delete/%s' % pid))
    def delete_tree(self,pid):
        return requests.delete(self.api('/delete_tree/%s' % pid))
    def update(self,pid, **d):
        """d can contain STATE, EVENT, MESSAGE, TTL"""
        return requests.patch(self.api('/update/%s' % pid), data=d)
    def complete(self,pid,**d):
        """like update but sets TTL to FOREVER.
        d can contain STATE, EVENT, MESSAGE"""
        self.update(pid,**dict(d.items(),ttl=FOREVER))
    def heartbeat(self,pid,**d):
        d[EVENT] = HEARTBEAT
        return requests.patch(self.api('/update/%s' % pid), data=d)
    def depend(self,pid, upstream, role, priority=None):
        return requests.put(self.api('/depend/%s' % pid), data={
            UPSTREAM: upstream,
            ROLE: role,
            PRIORITY: priority
        })
    def expire(self):
        r = requests.delete(self.api('/expire'))
        if not isok(r):
            return 0
        return r.json()['expired']
    def most_recent(self,n=None):
        if n is None:
            n = 25
        r = requests.get(self.api('/most_recent/%d' % n))
        return r.json()
    def downstream(self,roles=[],state=None,upstream_state=None):
        if roles:
            role_frag = '/%s' % '/'.join(roles)
        else:
            role_frag = ''
        r = requests.post(self.api('/downstream%s' % role_frag), data={
            STATE: state,
            UPSTREAM_STATE: upstream_state
        })
        return r.json()
    def get_graph(self,pid):
        r = requests.get(self.api('/get_graph/%s' % pid))
        return r.json()
    def search(self,frag):
        r = requests.get(self.api('/search/%s' % frag))
        return r.json()
    def get(self,pid):
        r = requests.get(self.api('/get/%s' % pid))
        return r.json()
    def do_all_work(self,roles=[ANY],callback=None,message=None,ttl=None):
        # FIXME this would be a better decorator
        for job in self.start_all(roles,ttl=ttl):
            pid = job[PID]
            try:
                if callback is not None:
                    callback(pid,job)
                self.complete(pid,
                              state=AVAILABLE,
                              event=COMPLETED,
                              message=message)
            except Exception as e:
                self.update(pid,
                            state=ERROR,
                            event='exception',
                            message=traceback.format_exc())
                
class Mutex(object):
    """Use a specific workflow product as a mutex. Requires cooperation
    between clients. Use with the "with" statement, like this:

    with Mutex({args}) as mutex:
        {do some stuff}
        mutex.heartbeat()
        {do some more stuff}
        ...

    the "with" statement will raise Busy if the mutex is not available.
    There is no blocking form of this; a retry decorator such as
    oii.utils.retry can be used if polling is desired.
    Transparently creates the mutex product if it does not exist, but
    does not delete it; the delete() method can be used for that."""
    def __init__(self, mutex_pid, base_url=None, ttl=None, expire=True):
        """mutex_pid = the unique identifier of this mutex (will create one if does not exist)
        base_url = the workflow service base URL
        ttl = time-to-live in seconds
        expire = whether or not to expire all products on enter"""
        self.client = WorkflowClient(base_url)
        self.mutex_pid = mutex_pid
        self.ttl = ttl
        self.expire = expire
    def __enter__(self):
        # optionally expire
        if self.expire:
            self.client.expire()
        # attempt to create mutex
        r = self.client.create(self.mutex_pid, state=WAITING, ttl=self.ttl)
        # CREATED or CONFLICT are both OK because it means the mutex exists
        if r.status_code not in (http.CREATED, http.CONFLICT):
            raise Busy("mutex %s busy" % self.mutex_pid)
        # attempt to win the race to put the mutex in the RUNNING state
        # and change the ttl if necessary
        r = self.client.update_if(self.mutex_pid, state=WAITING, new_state=RUNNING, ttl=self.ttl)
        if r.status_code == http.OK: # won the race
            return self
        raise Busy("mutex %s busy" % self.mutex_pid) # lost the race
    def heartbeat(self):
        """acquire ttl additional seconds of life, to avoid expiration"""
        self.client.heartbeat(self.mutex_pid)
    def __exit__(self, exc_type, exc_value, traceback):
        # attempt to release the mutex into the WAITING state
        r = self.client.update_if(
            self.mutex_pid,
            state=RUNNING,
            new_state=WAITING,
            event=RELEASED,
            ttl=FOREVER)
        if r.status_code == http.CONFLICT:
            # another client has forced the mutex out of the RUNNING state
            raise InconsistentState("mutex %s in inconsistent state" % self.mutex_pid)
        elif r.status_code != http.OK:
            # not enough information to know what is wrong
            raise RuntimeError("mutex %s in unknown state" % self.mutex_pid)
        return False # allow exceptions to propagate
