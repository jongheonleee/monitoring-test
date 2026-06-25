from threading import Lock 
from prometheus_client.core import GaugeMetricFamily, REGISTRY

class StateMetrics(object):

    def __init__(self):
        self._resource_states = {}
        self._STATES = ["STARTING", "RUNNING", "STOPPING", "TERMINATED"]
        self._mutex = Lock()

    def set_state(self, resource, state):
        with self._mutex:
            self._resource_states[resource] = state 

    def collect(self):
        family = GaugeMetricFamily(
            "resource_state",
            "The current state of resources",
            labels=["resource_state", "resource"]
        )

        with self._mutex:
            for resource, state in self._resource_states.items():
                for s in self._STATES:
                    family.add_metric([s, resource], 1 if s == state else 0)
        
        yield family


sm = StateMetrics()
REGISTRY.register(sm)

sm.set_state("blaa", "RUNNING")

if __name__ == "__main__":
    import time 
    import random 
    from prometheus_client import start_http_server 

    start_http_server(8004)
    print("listening: http://localhost:8004/metrics")

    resources = ["blaa", "foo", "bar"]
    states = ["STARTING", "RUNNING", "STOPPING", "TERMINATED"]

    while True:
        r = random.choice(resources)
        s = random.choice(states)

        sm.set_state(r, s)

        time.sleep(2)