
'''
This module implements a 'Cosm Advanced Web-scale Socket server (PAWS)'
This provides a capability communication with the Cosm API over a
persistent TCP connection.
'''

import json
import logging
import txcosm
import uuid
from twisted.internet import reactor, defer
from twisted.internet.protocol import Protocol, ReconnectingClientFactory


class PAWSProtocol(Protocol):
    """
    A instance of this protocol communications with the Cosm PAWS service
    """

    delimiter = '\n'

    def __init__(self):
        self.buffer = ""

    def connectionMade(self):
        # register this protocol with the factory so it can be
        # disconnected later if necessary.
        #peer = self.transport.getPeer()
        #addr = "%s:%s" % (peer.host, peer.port)
        self.factory.registerConnection(self)

    def disconnect(self):
        self.transport.loseConnection()

    def dataReceived(self, data):
        """
        Store data received from PAWS service in a buffer until a
        message delimiter is encountered then pass any messages
        back to the client through the factory's messageHandler.
        """
        self.buffer += data
        if PAWSProtocol.delimiter in self.buffer:
            msgs = self.buffer.split(PAWSProtocol.delimiter)
            for msg in msgs[:-1]:
                self.factory.messageHandler(msg)
            self.buffer = msgs[-1]
        else:
            logging.debug("No message delimiter found yet.")

    def send(self, data):
        """
        Send data to the PAWS service
        """
        self.transport.write(data)


class PAWSProtocolFactory(ReconnectingClientFactory):
    """
    This factory is responsible for managing connections to the PAWS
    service. Only one protocol instance is required per client. This
    factory will also attempt to automatically reconnect if an exisitng
    connection is lost.
    """

    port = 8081
    host = 'api.cosm.com'

    def __init__(self, messageHandler):
        self.connection = None
        self.connected = False
        self.messageHandler = messageHandler

        # These attributes are used during the connect/disconnect sequence
        # to inform caller that the sequence has completed and to provide
        # the state of the connect/disconnect request.
        self._connectDeferred = None
        self._disconnectDeferred = None

    def _connectionStateHandler(self, state):
        """
        Store internal connected-ness state and fire any pending deferred's
        waiting on notification of requested connect/disconnect actions.
        """
        self.connected = state

        # call any pending connection state notifiers
        if self._connectDeferred:
            self._connectDeferred.callback(state)
            self._connectDeferred = None

        if self._disconnectDeferred:
            # Invert the connection state to obtain the success state
            # of a disconnection request.
            disconnectedState = not state
            self._disconnectDeferred.callback(disconnectedState)
            self._disconnectDeferred = None

    def connect(self):
        """
        Establish a connection to the Cosm PAWS service if there
        is no current connection established.

        @return: A deferred which fires with a boolean representing the
                 success of the connection request.
        @rtype: defer.Deferred
        """
        if self.connection is None:
            reactor.connectTCP(PAWSProtocolFactory.host,
                               PAWSProtocolFactory.port,
                               self)
            self._connectDeferred = defer.Deferred()
            return self._connectDeferred
        else:
            logging.warning("Already connected, ignoring connect request")
            return defer.succeed(True)

    def disconnect(self):
        """
        Break the connection to the Cosm PAWS service.

        @return: A deferred which fires with a boolean representing the
                 success of the disconnection request.
        @rtype: defer.Deferred
        """
        if self.connection:
            self.connection.disconnect()
            self.continueTrying = False  # disable automatic reconnection attempts
            self._disconnectDeferred = defer.Deferred()
            return self._disconnectDeferred
        else:
            logging.warning("Already disconnected, ignoring disconnect request")
            return defer.succeed(True)

    def registerConnection(self, proto):
        """
        Called from the protocol to inform the factory that a connection
        has been made to the PAWS service.

        @param proto: The protocol connected to the PAWS service
        @type proto: a PAWSProtocol instance
        """
        self.connection = proto
        self._connectionStateHandler(True)

        # add a trigger to shut down cleanly upon exit
        reactor.addSystemEventTrigger('before', 'shutdown', self.disconnect)

    def buildProtocol(self, addr):
        """
        Builds an instance of the PAWSProtocol. Called from witihin the
        reactor.connectTCP method.
        """
        # allow automatic reconneciton attempts, that might have been
        # diabled through the disconnect method.
        self.continueTrying = True
        # initialise reconnection attempt delay
        self.resetDelay()
        p = PAWSProtocol()
        p.factory = self
        return p

    def clientConnectionLost(self, connector, reason):
        logging.debug('PAWS connection lost. Reason: %s' % reason)
        self._connectionStateHandler(False)
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        logging.error('PAWS connection failed. Reason: %s' % reason)
        self._connectionStateHandler(False)
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)

    def send(self, data):
        """
        Send a string of data to the PAWS service through the single connection.
        This is a convenience wrapper around the protocol.
        """
        self.connection.send(data)


class PAWSClient(object):
    """
    A Cosm Advanced Web-scale Socket-server (PAWS) client.

    This class does everything the standard client does and more.

    The main feature of this class is its ability to subscribe to
    resource paths (e.g. feeds, datastreams) and receive push
    notifications of updates when they occur.
    """

    def __init__(self, api_key=None, feed_id=None):
        """
        @param api_key: The api key, with appropriate authorization privileges to use.
        @type api_key: string
        @param feed_id: The default feed identifier to use
        @type feed_id: string
        """
        self.api_key = api_key
        self.feed_id = feed_id

        # Store the response callback processing chains associated with each request.
        # Responses can be associated to the originating requests through the token.
        # the token forms the key in this dict.
        self.pendingResponses = dict()

        # Subscriptions use the same token approach to map the message data to the
        # originating request. The values of each dict item is a tuple of the
        # callback handler function to pass the response data to and a txcosm
        # data structure class that is used to decode the data upon its receipt.
        self.subscriptionHandlers = dict()

        self.headers = {'X-ApiKey': self.api_key}

        self.factory = PAWSProtocolFactory(self._messageHandler)

    def connect(self):
        """
        Establish a connection to the Cosm PAWS service.

        @return: Returns a deferred that fires when the connection
                 is completed.
        @rtype: defer.Deferred
        """
        return self.factory.connect()

    def disconnect(self):
        """
        Break a connection to the Cosm PAWS service

        @return: Returns a deferred that fires when the disconnection
                 is completed.
        @rtype: defer.Deferred
        """
        return self.factory.disconnect()

    @property
    def connected(self):
        """
        A convenience property to check the connection state.

        @return: The connection state of the PAWSClient
        @rtype: boolean
        """
        return self.factory.connected

    def _messageHandler(self, msg):
        """
        Receive a message from the PAWS service. Use the token found in the response
        to find the correct pending response deferred so the response processing
        chain can process the message and return it to the caller.
        """
        logging.debug("PAWSClient has received a message:\n%s\n" % msg)
        data = json.loads(msg)
        token = data['token']

        if token in self.pendingResponses:
            self.pendingResponses[token].callback(data)
            del self.pendingResponses[token]

        elif token in self.subscriptionHandlers:
            body = self._getResponseBody(data)
            handler, dataStructureClass = self.subscriptionHandlers[token]
            dataStructure = dataStructureClass(**body)
            handler(dataStructure)

        else:
            logging.error("Unrecognised message with token %s not in pendingResponses or subscriptionHandlers" % token)
            logging.error("pendingResponses tokens = %s" % str(self.pendingResponses.keys()))
            logging.error("subscriptionHandlers tokens = %s" % str(self.subscriptionHandlers.keys()))
            logging.error("No handler to process:\n%s\n" % json.dumps(data, sort_keys=True, indent=2))

    def _generateToken(self):
        """
        Make a unique token that can be used to match requests with the response.
        """
        return str(uuid.uuid1())

    #
    # Callbacks
    #

    def _getResponseBody(self, response):
        """
        Most responses need to deliver the response body data. Some need
        to return data from the header only. This method returns just the
        response body data.
        """
        return response['body']

    def _convertToCosmStructure(self, data, kind):
        """
        Convert the data into a DataStructure object
        """
        dataStructureClass = txcosm.getDataStructure(kind)
        dataStructure = dataStructureClass()
        dataStructure.decode(data)
        return dataStructure

    def _getResponseCodeStatusFromHeader(self, response):
        """
        Most responses need to deliver the response body data. Some need
        to return data from the header only. This method provides the
        ability to return a success/fail criteria based on the response
        header code received.
        """
        responseCode = response['status']
        success = responseCode == 200
        if not success:
            logging.error("Expected status response code 200, received %s" % (responseCode))
        return success

    def _getLocationFromHeader(self, response):
        """
        Extract and return the location of the created item
        from the 'Location' field in the response header.
        """
        if response['status'] == 201:
            # created ok
            if 'LOCATION' in response['headers']:
                location = response['headers']["LOCATION"]
                return location
            else:
                err_str = "No response header \'Location\' field found"
                logging.error(err_str)
                raise Exception(err_str)
        else:
            err_str = "Unexpected response. Expected 201 but got => %s" % (response['status'])
            logging.error(err_str)
            raise Exception(err_str)

    def _sendRequest(self, method, resource, parameters=None, body=None, token=None):
        """
        Send a request to the url, where the method argument defines the kind of request.
        Returns a deferred that returns a tuple containing the response header and the
        response body.

        @param method: The kind of request to make. [get|put|post|delete]
        @type method: string
        @param resource: The resource used during the request
        @type resource: string
        @param headers: A dict of header key value pairs to be used in the request
        @type headers: dict
        @param body: THe content used for the request body data.

        @return:  A deferred that returns a the response.
        @rtype: twisted.internet.defer.Deferred
        """

        message = dict()
        message['method'] = method
        message['resource'] = resource
        message['headers'] = self.headers
        if parameters:
            message['parameters'] = parameters
        if body:
            message['body'] = body
        if token is None:
            token = self._generateToken()
        message['token'] = token

        logging.debug("About to send:\n%s\n" % json.dumps(message, sort_keys=True, indent=2))

        if self.connected:
            self.factory.send(json.dumps(message))
            self.pendingResponses[token] = defer.Deferred()
            return self.pendingResponses[token]
        else:
            logging.error("Send failed, no connection exists")

    def _get(self, resource, parameters=None):
        """
        Perform a get at the specified url

        @param resource: The resource used during the request
        @type resource: string

        @return:  A deferred that returns the response.
        @rtype: twisted.internet.defer.Deferred
        """
        return self._sendRequest("get", resource)

    def _put(self, resource, data):
        """
        Perform a put at the specified resource

        @param resource: The resource used during the request
        @type resource: string
        @param body: The content that forms the body of the request.
        @type body: string

        @return:  A deferred that returns the response.
        @rtype: twisted.internet.defer.Deferred
        """
        return self._sendRequest("put", resource, body=data)

    def _post(self, resource, data):
        """
        Perform a post at the specified resource

        @param resource: The resource used during the request
        @type resource: string
        @param body: The content that forms the body of the request.
        @type body: string

        @return:  A deferred that returns the response.
        @rtype: twisted.internet.defer.Deferred
        """
        return self._sendRequest("post", resource, body=data)

    def _delete(self, resource):
        """
        Perform a delete at the specified url

        @param resource: The resource used during the request
        @type resource: string

        @return:  A deferred that returns the response.
        @rtype: twisted.internet.defer.Deferred
        """
        return self._sendRequest("delete", resource)

    @defer.inlineCallbacks
    def _subscribe(self, resource):
        """
        Perform a subscribe at the specified url

        @param resource: The resource used during the request
        @type resource: string

        @return: A tuple containing the token used for subscription and
                 the result of the subscribe response. The token is needed
                 later to unsubscribe.
        @rtype: tuple
        """
        token = self._generateToken()
        response = yield self._sendRequest("subscribe", resource, token=token)
        # _sendRequest returns a deferred allowing the caller to chain
        # up processing actions to be called when the resposne arrives.
        # By default _sendRequest add this deferred to a pendingResponses
        # dict using the message token as the dict key. As responses are
        # processed, the normal action is to remove the token from the dict
        # as they are only used by the req/reply pair.
        # Subscription responses use the same token forever. This means
        # we can't simply remove the matching token item from the dict and
        # continue to be able to process the messages.
        # So a separate dict is used to store the token and associated
        # callback handlers for subscription messages.
        # However, by default we still end up with an entry in the
        # pendingResponses dict. Conveniently each subscribe/unsubscribe
        # request is responded to with an acknomledge response. Processing
        # this message results in the identical token in the pendingResponses
        # being removed. All good.
        result = (token, response)
        defer.returnValue(result)

    def _unsubscribe(self, resource, token):
        """
        Perform a subscribe at the specified url

        @param resource: The resource used during the request
        @type resource: string
        @param token: : The token generated from the initial subscription.
        @type token: string

        @return: A deferred that returns a result of the subscribe
                 response.
        @rtype: string
        """
        return self._sendRequest("unsubscribe", resource, token=token)

    #
    # Environments (Feeds)
    #

    @defer.inlineCallbacks
    def list_feeds(self, parameters=None):
        """
        Returns a paged list of Cosm's feeds that are viewable by
        the authenticated account with a default page size of 50 feeds.

        @param parameters: Additional parameters to configure the search query.
        @type parameters: dict

        @return: A deferred that returns the response body which is a paged
                 list of feeds (default 50 per page) viewable by the api_key
                 provided.
        @rtype: string (in the format specified by the format argument)


        Available settings for parameters:

        page
            Integer indicating which page of results you are requesting. Starts from 1.
            http://api.cosm.com/v2/feeds?page=2

        per_page
            Integer defining how many results to return per page (1 to 1000).
            http://api.cosm.com/v2/feeds?per_page=5

        content
            String parameter ('full' or 'summary') describing whether we
            want full or summary results. Full results means all datastream
            values are returned, summary just returns the environment meta
            data for each feed.
            http://api.cosm.com/v2/feeds?content=summary

        q
            Full text search parameter. Should return any feeds matching this string.
            http://api.cosm.com/v2/feeds?q=arduino

        tag
            Returns feeds containing datastreams tagged with the search query.
            http://api.cosm.com/v2/feeds?tag=temperature

        user
            Returns feeds created by the user specified.
            http://api.cosm.com/v2/feeds.xml?user=cosm

        units
            Returns feeds containing datastreams with units specified by the
            search query.
            http://api.cosm.com/v2/feeds.xml?units=celsius

        status
            Possible values ('live', 'frozen', or 'all'). Whether to search
            for only live feeds, only frozen feeds, or all feeds. Defaults to all.
            http://api.cosm.com/v2/feeds.xml?status=frozen

        order
            Order of returned feeds. Possible values ('created_at', 'retrieved_at',
            or 'relevance').
            http://api.cosm.com/v2/feeds.xml?order=created_at

        show_user
            Include user login and user level for each feed.
            Possible values: true, false (default).
            http://api.cosm.com/v2/feeds.xml?show_user=true


        The following additional advanced parameters are more intensive
        queries that are restricted to particular account types:

        lat
            Used to find feeds located around this latitude.
            Used if ids/_datastreams_ are not specified.
            lat=51.5235375648154

        lon
            Used to find feeds located around this longitude.
            Used if ids/_datastreams_ are not specified.
            lon=-0.0807666778564453

        distance
            search radius
            distance=5.0

        distance_units
            miles or kms (default).
            distance_units=miles

        """
        response = yield self._get("/feeds", parameters)
        body = self._getResponseBody(response)
        dataStructure = self._convertToCosmStructure(body, txcosm.List_Feeds_Msg)
        defer.returnValue(dataStructure)

    @defer.inlineCallbacks
    def create_feed(self, data=None):
        """
        Creates a new feed.

        @param data: A string detailing the environment to be created.
        @type data: string

        @return: A deferred that returns the feed_id of the newly created feed.
        @rtype: string

        """
        response = yield self._post('/feeds', data)
        location = self._getLocationFromHeader(response)
        feed_id = location.split("/")[-1]
        defer.returnValue(feed_id)

    @defer.inlineCallbacks
    def read_feed(self, feed_id, parameters=None):
        """
        Returns the most recent datastreams for environment [feed_id], viewable by the api_key provided

        @param feed_id: The feed identifier
        @type feed_id: string
        @param parameters: Additional parameters to configure the search query.
        @type parameters: dict

        @return: A deferred that returns a txcosm.Environment object populated
                 from the body of the response.
        @rtype: txcosm.Environment


        Available settings for parameters:
        datastream
            Filter the returned datastreams. Comma separated datastream IDs.
            http://api.cosm.com/v2/feeds/123.json?datastreams=energy,power

        show_user
            Include user login and user level for each feed.
            Possible values: true, false (default).
            http://api.cosm.com/v2/feeds/123.xml?show_user=true (json/xml only)


        Available settings for parameters supporting historical queries:
        start:
            Defines the starting point of the query as a timestamp,
            e.g. 2010-05-20T11:01:46Z. The default value is blank.

        end:
        Defines the end point of the data returned as a timestamp,
        e.g. 2010-05-21T11:01:46Z. The default value is set to the current timestamp.

        duration:
            Specifies the duration of the query.
            If used in conjunction with end it will request the data prior to the end date.
            If used in conjunction with start it will request the data after the start date.
            If used by itself it will give the most recent data for the duration specified.
            It is incorrect to specify start, end and duration

            The format is <number><time unit> e.g. 10minutes, 6hours

            The valid time units are:
            seconds
            minute(s)
            hour(s)
            day(s)
            week(s)
            month(s)
            year(s)

        page:
            Defines which page we are looking at of the matching results.
            If not set, the default value is 1

        per_page:
            Defines how many results are returned per page.
            If not set this value defaults to 100. Maximum value is 1000

        time:
            Returns the feed with the values as they were at the specified timestamp.
            There are a few points to note about this functionality:
                Only the values of the datastream and their timestamps are changed,
                all other metadata reflects the current state of the feed and its datastreams
                If a datastream had no values at the time specified (either because it didn't
                exist or because it hadn't been updated) it will be excluded from the output

        find_previous:
            Will also return the previous value to the date range being requested.
            Note that this is useful for any graphing because if you want to draw a graph of
            the date range you specified you would end up with a small gap until the first value.

        interval_type:
            If set to "discrete" the data will be returned in fixed time interval format
            according to the inverval value supplied. If this is not set, the raw datapoints
            will be returned.

        interval:
            Determines what interval of data is requested and is defined in seconds between
            the datapoints. If a value is passed in which does not match one of these values,
            it is rounded up to the next value.
            The acceptable values are currently:
                Value    Description                     Maximum range in one query
                0        Every snapshot stored            6 hours
                30       30 second interval data          12 hours
                60       One snapshot every minute        24 hours
                300      One snapshot every 5 minutes     5 days
                900      One snapshot every 15 minutes    14 days
                3600     One snapshot per hour            31 days
                10800    One snapshot per three hours     90 days
                21600    One snapshot per six hours       180 days
                43200    One snapshot per twelve hours    1 year
                86400    One snapshot per day             1 year
        """
        resource = '/feeds/%s' % feed_id
        response = yield self._get(resource, parameters)
        body = self._getResponseBody(response)
        dataStructure = self._convertToCosmStructure(body, txcosm.View_Feed_Msg)
        defer.returnValue(dataStructure)

    @defer.inlineCallbacks
    def update_feed(self, feed_id, data=None):
        """
        Updates [environment ID]'s environment and datastreams. If successful, the
        current datastream values are stored and any changes in environment metadata
        overwrite previous values. Cosm stores a server-side timestamp in the
        "updated" attribute and sets the feed to "live" if it wasn't before.

        @param feed_id: The feed identifier
        @type feed_id: string
        @param data: A representation of the feed in the appropriate format.
        @type data: string

        @return: A deferred that returns the success of the update based on
                 the response header data.
        @rtype: boolean
        """
        resource = '/feeds/%s' % feed_id
        response = yield self._put(resource, data)
        status_code = self._getResponseCodeStatusFromHeader(response)
        defer.returnValue(status_code)

    @defer.inlineCallbacks
    def delete_feed(self, feed_id):
        """
        The DELETE request does not require a format to be used. A request made to
        this URL will delete the object referred to by the ID.
        WARNING: This is final and cannot be undone.

        @param feed_id: The feed identifier
        @type feed_id: string

        @return: A deferred that returns the success of the delete based on
                 the response header data.
        @rtype: boolean
        """
        resource = '/feeds/%s' % feed_id
        response = yield self._delete(resource)
        status_code = self._getResponseCodeStatusFromHeader(response)
        defer.returnValue(status_code)

    #
    # Datastreams
    #

    @defer.inlineCallbacks
    def create_datastream(self, feed_id, datastream_id, data=None):
        """
        Creates new datastream(s) in environment [feed ID]. The body of the request
        should contain a JSON, XML or CSV representation of the datastream to be created.

        @param feed_id: The feed identifier
        @type feed_id: string
        @param datastream_id: A datastream identifier
        @type datastream_id: string
        @param data: A representation of the datastream to be created. Cosm currently requires
                     that the datastream be wrapped in an environment. So the minimum data
                     (in JSON format) necessary to create a new datastream is:
                        {
                         "version": "1.0.0"
                         "datastreams": [
                            {
                              "id": "test_datastream"
                            }
                          ],
                        }
        @type data: string

        @return: A deferred that returns the location of the datastream created.
        @rtype: boolean
        """
        resource = '/feeds/%s/datastreams/%s' % (feed_id, datastream_id)
        response = yield self._post(resource, data)
        location = self._getLocationFromHeader(response)
        datastream_id = location.split("/")[-1]
        defer.returnValue(datastream_id)

    @defer.inlineCallbacks
    def read_datastream(self, feed_id, datastream_id, parameters=None):
        """
        Read the requested datastream.

        @param feed_id: The feed identifier
        @type feed_id: string
        @param datastream_id: A datastream identifier
        @type datastream_id: string
        @param parameters: Additional parameters to configure the png output.
        @type parameters: dict

        @return: A deferred that returns a txcosm.Datastream object or None.
        @rtype: txcosm.Datastream


        Available settings for parameters supporting historical queries:
        start:
            Defines the starting point of the query as a timestamp,
            e.g. 2010-05-20T11:01:46Z. The default value is blank.

        end:
        Defines the end point of the data returned as a timestamp,
        e.g. 2010-05-21T11:01:46Z. The default value is set to the current timestamp.

        duration:
            Specifies the duration of the query.
            If used in conjunction with end it will request the data prior to the end date.
            If used in conjunction with start it will request the data after the start date.
            If used by itself it will give the most recent data for the duration specified.
            It is incorrect to specify start, end and duration

            The format is <number><time unit> e.g. 10minutes, 6hours

            The valid time units are:
            seconds
            minute(s)
            hour(s)
            day(s)
            week(s)
            month(s)
            year(s)

        page:
            Defines which page we are looking at of the matching results.
            If not set, the default value is 1

        per_page:
            Defines how many results are returned per page.
            If not set this value defaults to 100. Maximum value is 1000

        time:
            Returns the feed with the values as they were at the specified timestamp.
            There are a few points to note about this functionality:
                Only the values of the datastream and their timestamps are changed,
                all other metadata reflects the current state of the feed and its datastreams
                If a datastream had no values at the time specified (either because it didn't
                exist or because it hadn't been updated) it will be excluded from the output

        find_previous:
            Will also return the previous value to the date range being requested.
            Note that this is useful for any graphing because if you want to draw a graph of
            the date range you specified you would end up with a small gap until the first value.

        interval_type:
            If set to "discrete" the data will be returned in fixed time interval format
            according to the inverval value supplied. If this is not set, the raw datapoints
            will be returned.

        interval:
            Determines what interval of data is requested and is defined in seconds between
            the datapoints. If a value is passed in which does not match one of these values,
            it is rounded up to the next value.
            The acceptable values are currently:
                Value    Description                     Maximum range in one query
                0        Every snapshot stored            6 hours
                30       30 second interval data          12 hours
                60       One snapshot every minute        24 hours
                300      One snapshot every 5 minutes     5 days
                900      One snapshot every 15 minutes    14 days
                3600     One snapshot per hour            31 days
                10800    One snapshot per three hours     90 days
                21600    One snapshot per six hours       180 days
                43200    One snapshot per twelve hours    1 year
                86400    One snapshot per day             1 year


        This request can also make use of the PNG format.

        Requesting the datastram as a PNG image will generate a graph. The time
        period that is shown is controlled by the history parameters passed to
        the request and the look and feel of this graph can be controlled by the
        following parameters:

        Parameter    Description    Example
        w    width in pixels         600
        h    height in pixels        400
        c    colour in hex           FFCC33
        t    title                   My Favourite Graph
        l    legend                  Legend For My Graph
        s    strokesize in pixels    4
        b    show axis labels        true / false
        g    show detailed grid      true / false

        If api_key or feed_id arguments are not set when calling this method then the
        values set during this object's instantiation (ie. in __init__) are used.
        """
        resource = '/feeds/%s/datastreams/%s' % (feed_id, datastream_id)
        response = yield self._get(resource, parameters)
        body = self._getResponseBody(response)
        dataStructure = self._convertToCosmStructure(body, txcosm.View_Datastream_Msg)
        defer.returnValue(dataStructure)

    @defer.inlineCallbacks
    def update_datastream(self, feed_id, datastream_id, data):
        """
        Update a single datastream

        @param feed_id: The feed identifier
        @type feed_id: string
        @param datastream_id: A datastream identifier
        @type datastream_id: string
        @param format: The format to request the results in [json|xml|csv]
        @type format: string
        @param data: A representation of the datastream in the appropriate format.
        @type data: string

        @return: A deferred that returns the success status of the update.
        @rtype: boolean
        """
        resource = '/feeds/%s/datastreams/%s' % (feed_id, datastream_id)
        response = yield self._put(resource, data)
        status_code = self._getResponseCodeStatusFromHeader(response)
        defer.returnValue(status_code)

    @defer.inlineCallbacks
    def delete_datastream(self, feed_id, datastream_id):
        """
        The DELETE request does not require a format to be used. A request made to
        this URL will delete the object referred to by the ID.
        WARNING: This is final and cannot be undone.

        @param feed_id: The feed identifier
        @type feed_id: string
        @param datastream_id: A datastream identifier
        @type datastream_id: string

        @return: A deferred that returns the success status of the delete.
        @rtype: boolean
        """
        resource = '/feeds/%s/datastreams/%s' % (feed_id, datastream_id)
        response = yield self._delete(resource)
        status_code = self._getResponseCodeStatusFromHeader(response)
        defer.returnValue(status_code)

    @defer.inlineCallbacks
    def subscribe(self, resource, subscriptionHandler):
        """
        Subscribe to the resource for updates of changes.

        @param resource: The resource to access
        @type resource: string
        @param subscriptionHandler: A callable that will receive the data structure
                                   returned periodically as a result of the subscription.
        @type subscriptionHandler: callable

        @return: A tuple containing the token used for subscription and a deferred
                that returns the state of the subscription request. The token is
                needed to unsubscribe later.
        @rtype: string
        """
        # determine the expected response object kind based on
        # the resource being subscribed to.
        if 'datastreams' in resource:
            dataStructureClass = txcosm.Datastream
        else:
            dataStructureClass = txcosm.Environment

        (token, response) = yield self._subscribe(resource)
        response_code = self._getResponseCodeStatusFromHeader(response)
        self.subscriptionHandlers[token] = (subscriptionHandler, dataStructureClass)
        result = (token, response_code)
        defer.returnValue(result)

    @defer.inlineCallbacks
    def unsubscribe(self, resource, token):
        """
        Unsubscribe from receiving update from the specified resource.

        @param resource: The resource to access
        @type resource: string
        @param token: : The token generated from the initial subscription.
        @type token: string

        @return: A deferred that returns the state of the unsubscription request
        @rtype: boolean
        """
        if token in self.subscriptionHandlers:
            del self.subscriptionHandlers[token]

        response = yield self._unsubscribe(resource, token)
        status_code = self._getResponseCodeStatusFromHeader(response)
        defer.returnValue(status_code)
