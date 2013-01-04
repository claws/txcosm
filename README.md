
# txcosm

## Introduction
txcosm is a Python Twisted package implementing the v2 Cosm ([API](https://cosm.com/docs/v2/>). Use txcosm to integrate non blocking access to the Cosm API into your Python Twisted application.

## Background 
Cosm was once known as Pachube. This package originated as _txpachube_. It has been renamed to mirror the new site name and development continues in this repository.

## Details
txcosm implements the full v2 Cosm API (Feeds, Datastreams, Datapoints, Triggers, Users, Keys) and many of the data structures (Unit, Location, Datapoint, Datastream, Environment, EnvironmentList, Trigger, TriggerList Key, KeyList, User, UserList) contained in requests and responses.

The data structures support encoding and decoding from JSON/XML formats. These structures are useful when building data to send to Cosm and also for processing Cosm data returned from queries.

The txcosm client methods take a data string argument that will be used as the body of the message sent to Cosm. How you generate this body data is up to you. You might choose to manually create the data something like this:

```python
# manually create feed data message body content 
feed_data = {"title" : "A Temporary Test Feed",
             "version" : "1.0.0"}
json_feed_data = json.dumps(feed_data)
```

The txcosm package implements many of the data structures used by Cosm requests and responses as Python objects. So the JSON formatted feed data above could also be generated using these txcosm data structure objects like this:

```python
# Define a dict of valid data structure keywords for use as
# key word arguments to the data structure initialiser.
env_kwargs = {txcosm.DataFields.Title : "A Temporary Test Feed",
              txcosm.DataFields.Version : "1.0.0"}
environment = txcosm.Environment(**env_kwargs)
json_feed_data = environment.encode()
```

Or in a more compact form once you are familiar with a data strcture's valid DataField items:

```python    
environment = txcosm.Environment(title="A Temporary Test Feed", version="1.0.0")
json_feed_data = environment.encode()
```

txcosm also implements a client that connects to the (Socket Server) PAWS service. This allows long running, persistent, connections to be made to the Cosm service. This type of client is useful for applications which require realtime updates on change of status. Realtime feed updates are available through the subscription feature exposed in the beta PAWS service.

## Dependencies

* Python
* Twisted

  - zope.interface
  - pyOpenSSL (used by Twisted for https - in our case for secure access to Cosm)


## Install

A number of methods are available to install this package.

* Using pip with PyPI as source:

```bash
$ [sudo] pip install txcosm
```

* Using pip with github source:

```bash
$ [sudo] pip install git+git://github.com/claws/txcosm.git
```

* Manually download and install the txcosm archive. For other manual download options (zip, tarball) visit the github web page of [txcosm](https://github.com/claws/txcosm):

```bash
$ git clone git://github.com/claws/txcosm.git
$ cd txcosm
$ [sudo] python setup.py install
```

### Test Installation

```bash
$ python
>>> import txcosm
>>>
```

## Examples

All examples require you to have a Cosm account and an appropriately configured (permissions set to create, update, read, delete) Cosm API key.

Example scripts can be found in the examples directory. 

Below are some simple examples to give a quick glimpse of how to use this package. 

List Cosm feeds visible to the API key supplied:

```python
#!/usr/bin/env python 
# This example demonstrates a request for feeds visible to the
# supplied API key. It initialises the Client object with a
# default API key that will be used if no api_key argument is
# passed to the various API methods.
# Parameters can be passed to customise the default results.
# In this case only 'live' feeds and 'summary' content is
# being requested.

from twisted.internet import reactor, defer
import txcosm.client

# Paste your Cosm API key here
API_KEY = ""

@defer.inlineCallbacks
def demo():
    client = txcosm.client.Client(api_key=API_KEY)
    try:
        feed_list = yield client.list_feeds(parameters={'status' : 'live', 'content' : 'summary'})
        print "Received feed list content:\n%s\n" % feed_list
    except Exception, ex:
        print "Error listing visible feeds: %s" % str(ex)
    
    reactor.callLater(0.1, reactor.stop)
    defer.returnValue(True) 

if __name__ == "__main__":
    reactor.callWhenRunning(demo)
    reactor.run()
```

Create a new feed:

```python
#!/usr/bin/env python 
# This example demonstrates the ability to create new feeds. It also
# shows an API key being passed to the create_feed method directly 
# as no default key was passed to the Client object initialiser.
# No format needs to be specified because json is the default format
# used.

from twisted.internet import reactor, defer
import txcosm
import txcosm.client

# Paste your Cosm API key here
API_KEY = ""

@defer.inlineCallbacks
def demo():
    
    client = txcosm.client.Client()
    try:
        environment = txcosm.Environment(title="A Temporary Test Feed", version="1.0.0")
        new_feed_id = yield client.create_feed(api_key=API_KEY, data=environment.encode())
        print "Created new feed with id: %s" % new_feed_id
    except Exception, ex:
        print "Error creating new feed: %s" % str(ex)
    
    reactor.callLater(0.1, reactor.stop)
    defer.returnValue(True) 
    

if __name__ == "__main__":
    reactor.callWhenRunning(demo)
    reactor.run()
```

Update a feed:

```python
#!/usr/bin/env python 
# This example show how a feed can be updated using your own generated
# data, in this case XML data. 
# The Client object has been initialised with an API key and a feed id 
# so they don't need to be passed to the update_feed method. The format 
# argument is JSON by default so it must be explicitly set as this 
# example is using XML.

from twisted.internet import reactor
import txcosm
import txcosm.client

# Paste your Cosm API key here
API_KEY = ""

# Paste you feed identifier here
FEED_ID = ""

# example feed update data
feed_data = """<?xml version="1.0" encoding="UTF-8"?>
<eeml xmlns="http://www.eeml.org/xsd/0.5.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="0.5.1" xsi:schemaLocation="http://www.eeml.org/xsd/0.5.1 http://www.eeml.org/xsd/0.5.1/0.5.1.xsd">
  <environment>
    <title>bridge19</title>
    <status>live</status>
    <description>bridge environment 19</description>
    <tag>Tag1</tag>
    <tag>Tag2</tag>
    <data id="3">
      <current_value>-312</current_value>
      <max_value>999.0</max_value>
      <min_value>7.0</min_value>
    </data>
    <data id="0">
      <current_value>11</current_value>
      <max_value>211.0</max_value>
      <min_value>7.0</min_value>
    </data>
    <data id="4">
      <current_value>-3332</current_value>
    </data>
  </environment>
</eeml>"""


if __name__ == "__main__":
    cosmClient = txcosm.client.Client(api_key=API_KEY, feed_id=FEED_ID)

    d = cosmClient.update_feed(format=txcosm.DataFormats.XML, data=feed_data)
    d.addCallback(lambda result: print "Feed updated successfully:\n%s\n" % result)
    d.addErrback(lambda reason: print "Error updating feed: %s" % str(reason))
    d.addCallback(reactor.stop)

    reactor.run()      
```

Read a feed:

```python
#!/usr/bin/env python 
# This example demonstrates a request for feed data and uses
# additional parameters to restrict the datastreams returned.
# It initialises the Client object with a default API key and
# feed id so they do not need to be passed to the read_feed
# method.

from twisted.internet import reactor, defer
import txcosm.client

# Paste your Cosm API key here
API_KEY = ""

# Paste the feed identifier you wish to be read here
FEED_ID = ""

@defer.inlineCallbacks
def demo():
    client = txcosm.client.Client(api_key=API_KEY, feed_id=FEED_ID)
    try:
        feed = yield client.read_feed(parameters={'datastream':'temperature'})
        print "Received feed content:\n%s\n" % feed
    except Exception, ex:
        print "Error reading feed: %s" % str(ex)
    
    reactor.callLater(0.1, reactor.stop)
    defer.returnValue(True) 
    
if __name__ == "__main__":
    reactor.callWhenRunning(demo)
    reactor.run()
```

Delete a feed:

```python
#!/usr/bin/env python 
# This example demonstrates the ability to delete a feed.
# WARNING: This will REALLY delete the feed identifier listed. Make sure it is only a test feed. 

from twisted.internet import reactor, defer
import txcosm.client

# Paste your Cosm API key here
API_KEY = ""

# Paste the feed identifier you wish to be DELETED here
FEED_ID = ""

@defer.inlineCallbacks
def demo():
    client = txcosm.client.Client()
    try:
        feed_delete_status = yield client.delete_feed(api_key=API_KEY, feed_id=FEED_ID)
        print "Deleted feed: %s" % feed_delete_status
    except Exception, ex:
        print "Error deleting feed: %s" % str(ex)
    
    reactor.callLater(0.1, reactor.stop)
    defer.returnValue(True) 
    

if __name__ == "__main__":
    reactor.callWhenRunning(demo)
    reactor.run()
```


Use the PAWS API to subscribe to a feed or datastream and receive updates whenever the feed/datastream value changes:

```python
#!/usr/bin/env python 

from twisted.internet import reactor
import txcosm
import txcosm.client

# Paste your Cosm API key here
API_KEY = ""

# Paste the feed identifier you wish to monitor here
FEED_ID = ""

# Paste a datastream identifier from the feed here if you only want to 
# monitor a particular datastream instead of the whole feed.
DATASTREAM_ID = ""
 
#
# Set up callback handlers
#

def updateHandler(dataStructure):
    """
    Handle a txcosm data structure object generated as a result of a
    subscription update message received from Cosm.

    The data structure returned will vary depending on the resource subscribed to.
    If a datastream is specified the returned data structure will be a txcosm.Datastream
    object. If just a feed is specified then the returned data structure will be a
    txcosm.Environment object.
    """
    print "Subscription update message received:\n%s\n" % str(dataStructure)


def do_subscribe(connected, client, resource):
    """ Subscribe to the specified resource if the connection is established """

    if connected:
        print "Connected to PAWS service"
        
        def handleSubscribeResponse(status):
            print "Subscribe response status: %s" % status
        
        print "Subscribing for updates to: %s" % resource
        token, d = client.subscribe(resource, updateHandler)
        print "Subscription token is: %s" % token
        d.addCallback(handleSubscribeResponse)

    else:
        print "Connection failed"
        reactor.callLater(0.1, reactor.stop)
        return


if __name__ == '__main__':
    if DATASTREAM_ID:
        resource = "/feeds/%s/datastreams/%s" % (FEED_ID, DATASTREAM_ID)
    else:
        resource = "/feeds/%s" % (FEED_ID)
    
    client = txcosm.client.PAWSClient(api_key=API_KEY)
    d = client.connect()
    d.addCallback(do_subscribe, client, resource)
    reactor.run()        
```

Example use case scenario:
```python
#!/usr/bin/env python

# This example demonstrates how you could use the txcosm module to
# help upload sensor data (in this scenario a CurrentCost device) to
# Cosm.
# A txcosm.Environment data structure is generated and populated
# with current value data. All the implemented data structures
# support encoding to JSON (default) and XML (EEML).
#
# In this example the CurrentCost sensor object is derived from the
# separate txcurrentcost package. If you want to run this script
# you would need to install that package.
#

from twisted.internet import reactor
import txcosm
import txcurrentcost.monitor

# Paste your Cosm API key here
API_KEY = ""

# Paste the feed identifier you wish to use here
FEED_ID = ""

CurrentCostMonitorConfigFile = "/path/to/your/config/file"


class MyCurrentCostMonitor(txcurrentcost.monitor.Monitor):
    """
    Extends the txcurrentCost.monitor.Monitor by implementing periodic update
    handler to call a supplied data handler.
    """

    def __init__(self, config_file, periodicUpdateDataHandler):
        super(MyCurrentCostMonitor, self).__init__(config_file)
        self.periodicUpdateDataHandler = periodicUpdateDataHandler

    def periodicUpdateReceived(self, timestamp, temperature, sensor_type, sensor_instance, sensor_data):
        if sensor_type == txcurrentcost.Sensors.ElectricitySensor:
            if sensor_instance == txcurrentcost.Sensors.WholeHouseSensorId:
                self.periodicUpdateDataHandler(timestamp, temperature, sensor_data)


class Monitor(object):

    def __init__(self, config):
        self.temperature_datastream_id = "temperature"
        self.energy_datastream_id = "energy"
        self.cosmClient = txcosm.client.Client(api_key=API_KEY, feed_id=FEED_ID)
        currentCostMonitorConfig = txcurrentcost.monitor.MonitorConfig(CurrentCostMonitorConfigFile)
        self.sensor = txcurrentcost.monior.Monitor(currentCostMonitorConfig,
                                                   self.handleCurrentCostPeriodicUpdateData)
        
    def start(self):
        """ Start sensor """
        self.sensor.start()
        
    def stop(self):
        """ Stop the sensor """
        self.sensor.stop()
        
    def def handleCurrentCostPeriodicUpdateData(self, timestamp, temperature, watts_on_channels):
        """ Handle latest sensor periodic update """

        # Populate a txcosm.Environment data structure object with latest data

        environment = txcosm.Environment(version="1.0.0")
        environment.setCurrentValue(self.temperature_datastream_id, "%.1f" % temperature)
        environment.setCurrentValue(self.energy_datastream_id, str(watts_on_channels[0]))

        # Update the Cosm service with latest value(s)
        d = self.cosmClient.update_feed(data=environment.encode())
        d.addCallback(lambda result: print "Cosm updated")
        d.addErrback(lambda reason: print "Cosm update failed: %s" % str(reason))


if __name__ == "__main__":
    monitor = Monitor()
    reactor.callWhenRunning(monitor.start)
    reactor.run()        
```



