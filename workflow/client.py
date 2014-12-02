import requests

from oii.utils import gen_id

from oii.workflow.orm import STATE, NEW_STATE, EVENT, MESSAGE
from oii.workflow.orm import WAITING, RUNNING, AVAILABLE
from oii.workflow.orm import ROLE, ANY
from oii.workflow.orm import HEARTBEAT
from oii.workflow.orm import UPSTREAM

import httplib as http

DEFAULT_BASE_URL='http://localhost:8080'

class Busy(Exception):
    """A mutex is busy"""
    pass

class InconsistentState(Exception):
    """The workflow products are in a logically inconsistent state"""
    pass

def isok(r):
    return r.status_code < 400

class WorkflowClient(object):
    def __init__(self, base_url=None):
        if base_url is None:
            base_url = DEFAULT_BASE_URL
        self.base_url = base_url
    def api(self, url):
        return self.base_url + url
    def wakeup(self, pid=None):
        if pid is None:
            return requests.get(self.api('/wakeup'))
        else:
            return requests.get(self.api('/wakeup/%s' % pid))
    def start_next(self,roles):
        if isinstance(roles,basestring):
            roles = [roles]
        return requests.get(self.api('/start_next/%s' % '/'.join(roles)))
    def create(self,pid,**d):
        return requests.post(self.api('/create/%s' % pid), data=d)
    def update_if(self,pid, **d):
        """d must contain STATE and NEW_STATE,
        d can also contain EVENT, MESSAGE"""
        return requests.post(self.api('/update_if/%s' % pid), data=d)
    def delete(self,pid):
        return requests.delete(self.api('/delete/%s' % pid))
    def delete_tree(self,pid):
        return requests.delete(self.api('/delete_tree/%s' % pid))
    def update(self,pid, **d):
        """d can contain STATE, EVENT, MESSAGE"""
        return requests.post(self.api('/update/%s' % pid), data=d)
    def heartbeat(self,pid,**d):
        d[EVENT] = HEARTBEAT
        return requests.post(self.api('/update/%s' % pid), data=d)
    def depend(self,pid, upstream, role):
        return requests.post(self.api('/depend/%s' % pid), data={
            UPSTREAM: upstream,
            ROLE: role
        })
    def expire(self):
        return requests.post(self.api('/expire'))

class Mutex(WorkflowClient):
    """Use a specific workflow product as a mutex. Requires cooperation
    between clients. Use with the "with" statement, like this:

    with Mutex({mutex product pid}, {client base URL}):
        {do some stuff}

    the "with" statement will raise Busy if the mutex is not available.
    There is no blocking form of this; a retry decorator such as
    oii.utils.retry can be used if polling is desired.
    Transparently creates the mutex product if it does not exist, but
    does not delete it; the delete() method can be used for that."""
    def __init__(self, mutex_pid, ttl=None, base_url=None):
        super(Mutex,self).__init__(base_url)
        self.mutex_pid = mutex_pid
        self.ttl = ttl
    def __enter__(self):
        # attempt to create mutex
        r = self.create(self.mutex_pid, state=WAITING, ttl=self.ttl)
        # CREATED or CONFLICT are both OK because it means the mutex exists
        if r.status_code not in (http.CREATED, http.CONFLICT):
            raise Busy("mutex %s busy" % self.mutex_pid)
        # attempt to win the race to put the mutex in the RUNNING state
        # and change the ttl if necessary
        r = self.update_if(self.mutex_pid, state=WAITING, new_state=RUNNING, ttl=self.ttl)
        if r.status_code == http.OK: # won the race
            return self
        raise Busy("mutex %s busy" % self.mutex_pid) # lost the race
    def __exit__(self, exc_type, exc_value, traceback):
        # attempt to release the mutex into the WAITING state
        r = self.update_if(self.mutex_pid, state=RUNNING, new_state=WAITING)
        if r.status_code == http.CONFLICT:
            # another client has forced the mutex out of the RUNNING state
            raise InconsistentState("mutex %s in inconsistent state" % self.mutex_pid)
        elif r.status_code != http.OK:
            # not enough information to know what is wrong
            raise RuntimeError("mutex %s in unknown state" % self.mutex_pid)
        return False # allow exceptions to propagate
