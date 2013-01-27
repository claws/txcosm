#!/usr/bin/env python

'''
This module implements Cosm clients that are able to communicate
with the Cosm API using HTTP and PAWS.
'''

import logging
import txcosm
import urllib
import uuid
from StringIO import StringIO
from twisted.internet import reactor, defer
from twisted.internet.protocol import Protocol
from twisted.web.client import Agent, ResponseDone, FileBodyProducer
from twisted.web.http_headers import Headers


def ignore_cancelled_error(failure):
    ''' Ignore errors raised by deferreds being cancelled '''
    failure.trap(defer.CancelledError)


class ResponseBodyProtocol(Protocol):
    """
    This object is used to receive the response body data
    after a request to a remote server.
    """
    def __init__(self, finished, response):
        self.finished = finished
        self.response = response
        self.buffer = []

    def dataReceived(self, bytes):
        """
        Receive and store some bytes of the response data
        """
        self.buffer.append(bytes)

    def connectionLost(self, reason):
        """
        Return the response and the response body via the finished deferred.
        """
        r = reason.trap(ResponseDone)
        if r == ResponseDone:
            logging.debug(reason.getErrorMessage())
            responseData = "".join(self.buffer)
            self.buffer = []
            result = (self.response, responseData)
            self.finished.callback(result)
        else:
            logging.error("Problem reading response body: %s" % reason.getErrorMessage())


class HTTPClient(object):
    """
    Encapsulates the Cosm API on top of the nonblocking, event driven
    twisted framework.
    """

    api_url = "api.cosm.com/v2"

    def __init__(self, api_key=None, feed_id=None, use_http=False, timezone=None):
        """
        @param api_key: The default api key, with appropriate authorization privileges,
                        to use.
        @type api_key: string
        @param feed_id: The default feed identifier to use
        @type feed_id: string
        @param use_http: A flag instructing this object to use http instead of
                         the default https.
        @type use_http: boolean
        @param timezone: By default all get requests return results in UTC.
                         Defining a timezone results in the returned data
                         having local timestamps. For more information on
                         the available settings see:
                         http://api.cosm.com/#time-zones
        @type timezone: string (eg. +3.5 or Adelaide)

        """
        self.feed_id = feed_id
        self.api_key = api_key

        prefix = "https"
        if use_http:
            prefix = "http"

        self.api_url = "%s://api.cosm.com/v2" % (prefix)

        self.timezone = None
        if timezone:
            self.timezone = "timezone=%s" % timezone

        # The agent web client is responsible for handling all
        # requests to and responses from the Cosm site.
        self.agent = Agent(reactor)

        # Common header settings used in every request.
        self.headers = {'User-Agent': 'txcosm Client',
                        'Content-Type': 'application/x-www-form-urlencoded'}

        self._request_timeout = 10.0  # default request timeout in seconds

        # this dict holds a unique identifier for each request made
        # and has values of two deferreds for each request. One deferred
        # is for the actual request while the other is for the timeout.
        self.pendingRequests = {}
        self.pendingResponses = {}
        self.pendingTimeouts = {}

    @property
    def request_timeout(self):
        ''' Return the request timeout value '''
        return self._request_timeout

    @request_timeout.setter
    def request_timeout(self, value):
        ''' Update the request timeout value '''
        self._request_timeout = value

    def _handle_request_timeout(self, request_id, url):
        ''' Handle a request timeout '''
        logging.error("Request timeout: %s" % url)
        del self.pendingTimeouts[request_id]  # cleanup

        # cancel deferred that would have returned request result.
        request_d = self.pendingRequests[request_id]
        request_d.addErrback(ignore_cancelled_error)
        request_d.cancel()

        # pass result back indicating failure
        self.pendingResponses[request_id].callback(None)

    @defer.inlineCallbacks
    def _handle_response(self, response, request_id, url):
        ''' Handle a response '''
        del self.pendingRequests[request_id]  # cleanup

        # cancel the timeout for this request now we have response
        self.pendingTimeouts[request_id].cancel()

        response, responseBody = yield self._handleResponseHeader(response, url)
        result = (response, responseBody)
        # pass result back indicating failure
        response_d = self.pendingResponses[request_id]
        del self.pendingResponses[request_id]  # cleanup
        response_d.callback(result)

    def _handleResponseHeader(self, response, url):
        """
        Called upon successful receipt of the response headers. The response's
        body is then retrieved. Upon completion of the body retrieval the
        returned deferred is fired returning a tuple containing the response
        and the response body.

        @param response: The response object
        @type response: twisted.web.client.Response
        @param url: The url used during the request
        @type url: string

        @return:  A deferred that returns a result tuple containing the response,
        and the response body.
        @rtype: twisted.internet.defer.Deferred
        """
        logging.debug("Success communicating with url: %s" % (url))
        finished = defer.Deferred()
        response.deliverBody(ResponseBodyProtocol(finished, response))
        return finished

    def _convertToCosmStructure(self, data, format, kind):
        """
        Convert the data into a DataStructure object
        """
        dataStructureClass = txcosm.getDataStructure(kind)
        dataStructure = dataStructureClass()
        dataStructure.decode(data, format)
        return dataStructure

    def _getResponseCodeStatusFromHeader(self, response):
        """
        Most responses need to deliver the response body data. Some need
        to return data from the header only. This method provides the
        ability to return a success/fail criteria based on the response
        header code received.
        """
        success = response.code == 200
        if not success:
            logging.error("Unexpected response: %s : %s" % (response.code, response.phrase))
        return success

    def _getLocationFromHeader(self, response):
        """
        Extract and return the location of the created item
        from the 'Location' field in the response header.
        """
        if response.code == 201:
            # created ok
            if response.headers.hasHeader("Location"):
                locations = response.headers.getRawHeaders("Location")
                if locations:
                    if len(locations) > 1:
                        logging.warning("Unexpected number of location items in response header: %s" % locations)
                        # for now just return the first occurrence
                    location = locations[0]
                    return location
                else:
                    err_str = "No content in response header \'Location\' field"
                    logging.error(err_str)
                    raise Exception(err_str)
            else:
                err_str = "No response header \'Location\' field found"
                logging.error(err_str)
                raise Exception(err_str)
        else:
            err_str = "Unexpected response => %s:%s" % (response.code, response.phrase)
            logging.error(err_str)
            raise Exception(err_str)

    def _sendRequest(self, method, url, headers, bodyProducer):
        """
        Send a request to the url, where the method argument defines the kind
        of request.
        Returns a deferred that returns a tuple containing the response header
        and the response body.

        @param method: The kind of request to make. [GET|PUT|POST|DELETE]
        @type method: string
        @param url: The url used during the request
        @type url: string
        @param headers: A dict of header key value pairs to be used in the
          request
        @type headers: dict
        @param bodyProducer: An object implementing IBodyProducer that is
          capable of being used to send the request body data.

        @return:  A deferred that returns a result tuple containing the
        response, and the response body.
        @rtype: twisted.internet.defer.Deferred
        """
        headers.update(self.headers)
        logging.debug("method=%s, url=%s, headers=%s, bodyLength=%s" % (method,
                                                                        url,
                                                                        str(headers),
                                                                        bodyProducer.length if bodyProducer else 0))
        request_id = uuid.uuid4().hex

        headers = dict([(k, [v]) for k, v in headers.items()])
        request_d = self.agent.request(method=method,
                                       uri=url,
                                       headers=Headers(headers),
                                       bodyProducer=bodyProducer)
        request_d.addCallback(self._handle_response, request_id, url)
        request_d.addErrback(ignore_cancelled_error)
        self.pendingRequests[request_id] = request_d

        # set up a timer to timeout request if no response is received
        # witihin a specified time interval.
        timeout = reactor.callLater(self._request_timeout,
                                    self._handle_request_timeout,
                                    request_id,
                                    url)
        self.pendingTimeouts[request_id] = timeout

        response_d = defer.Deferred()
        self.pendingResponses[request_id] = response_d
        return response_d

    def _get(self, url, headers):
        """
        Perform a get at the specified url

        @param url: The url used during the request
        @type url: string
        @param headers: A dict of header key value pairs to be used in the
          request
        @type headers: dict

        @return:  A deferred that returns a result tuple containing the
          response,
        and the response body.
        @rtype: twisted.internet.defer.Deferred
        """
        return self._sendRequest("GET", url, headers, None)

    def _put(self, url, headers, data):
        """
        Perform a put at the specified url

        @param url: The url used during the request
        @type url: string
        @param headers: A dict of header key value pairs to be used in the
          request
        @type headers: dict
        @param data: The data that forms the body of the request.
        @type data: string

        @return:  A deferred that returns a result tuple containing the
          response, and the response body.
        @rtype: twisted.internet.defer.Deferred
        """
        return self._sendRequest("PUT", url, headers,
                                 FileBodyProducer(StringIO(data)))

    def _post(self, url, headers, data):
        """
        Perform a post at the specified url

        @param url: The url used during the request
        @type url: string
        @param headers: A dict of header key value pairs to be used in the
          request
        @type headers: dict
        @param data: The data that forms the body of the request.
        @type data: string

        @return:  A deferred that returns a result tuple containing the
          response,
        and the response body.
        @rtype: twisted.internet.defer.Deferred
        """
        return self._sendRequest("POST", url, headers,
                                 FileBodyProducer(StringIO(data)))

    def _delete(self, url, headers):
        """
        Perform a delete at the specified url

        @param url: The url used during the request
        @type url: string
        @param headers: A dict of header key value pairs to be used in the
          request
        @type headers: dict

        @return:  A deferred that returns a result tuple containing the
          response,
        and the response body.
        @rtype: twisted.internet.defer.Deferred
        """
        return self._sendRequest("DELETE", url, headers, None)

    #
    # Environments (Feeds)
    #

    @defer.inlineCallbacks
    def list_feeds(self, api_key=None, format=txcosm.DataFormats.JSON,
                   parameters=None):
        """
        Returns a paged list of Cosm's feeds that are viewable by
        the authenticated account with a default page size of 50 feeds.

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param format: The format to request the results in [json|xml|csv]
        @type format: string
        @param parameters: Additional parameters to configure the search query.
        @type parameters: dict

        @return: A deferred that returns the response body which is a paged
                 list of feeds (default 50 per page) viewable by the api_key
                 provided. If the request fails None will be returned.
        @rtype: string (in the format specified by the format argument) or None


        Available settings for parameters:

        page
            Integer indicating which page of results you are requesting.
            Starts from 1.
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
            Full text search parameter. Should return any feeds matching this
            string.
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
            for only live feeds, only frozen feeds, or all feeds. Defaults to
            all.
            http://api.cosm.com/v2/feeds.xml?status=frozen

        order
            Order of returned feeds. Possible values ('created_at',
            'retrieved_at' or 'relevance').
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

        If api_key argument is not set when calling this method then the
        value set during this object's instantiation (ie. in __init__) is used.
        """

        url = "%s/feeds.%s" % (self.api_url, format)

        if parameters:
            params = urllib.urlencode(parameters)
            url = "%s?%s" % (url, params)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._get(url, headers)
        if result:
            response, responseBody = result
            if response.code == 200:
                dataStructure = self._convertToCosmStructure(responseBody, format, txcosm.List_Feeds_Msg)
                defer.returnValue(dataStructure)
            else:
                logging.error('Problem retrieving feed list. Expected response code 200 got %s' % response.code)
                defer.returnValue(None)
        else:
            logging.error('Problem retrieving feed list. Request failed')
            defer.returnValue(None)

    @defer.inlineCallbacks
    def create_feed(self, api_key=None, format=txcosm.DataFormats.JSON,
                    data=None):
        """
        Creates a new feed.

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param format: The format to request the results in [json|xml|csv]
        @type format: string
        @param data: A string detailing the environment to be created.
        @type data: string

        @return: A deferred that returns the feed_id of the newly created feed
                 or None.
        @rtype: string or None

        If api_key argument is not set when calling this method then the
        value set during this object's instantiation (ie. in __init__) is used.
        """
        if format == txcosm.DataFormats.CSV:
            raise Exception("CSV format is not supported for creating feeds")

        url = "%s/feeds.%s" % (self.api_url, format)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._post(url, headers, data)
        if result:
            response, responseBody = result
            if response.code == 201:
                location = self._getLocationFromHeader(response)
                feed_id = location.split("/")[-1]
                defer.returnValue(feed_id)
            else:
                logging.error('Problem creating feed. Expected response code 201 got %s' % response.code)
                defer.returnValue(None)
        else:
            logging.error('Problem creating new feed. Request failed')
            defer.returnValue(None)

    @defer.inlineCallbacks
    def read_feed(self, api_key=None, feed_id=None,
                  format=txcosm.DataFormats.JSON, parameters=None):
        """
        Returns the most recent datastreams for environment [feed_id],
        viewable by the api_key provided

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param feed_id: The feed identifier
        @type feed_id: string
        @param format: The format to request the results in [json|xml|csv]
        @type format: string
        @param parameters: Additional parameters to configure the search query.
        @type parameters: dict

        @return: A deferred that returns a txcosm.Environment object populated
                 from the body of the response or None.
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
        e.g. 2010-05-21T11:01:46Z. The default value is set to the current
        timestamp.

        duration:
            Specifies the duration of the query.
            If used in conjunction with end it will request the data prior to
            the end date. If used in conjunction with start it will request
            the data after the start date. If used by itself it will give the
            most recent data for the duration specified. It is incorrect to
            specify start, end and duration.

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
            Returns the feed with the values as they were at the specified
            timestamp.
            There are a few points to note about this functionality:

            Only the values of the datastream and their timestamps are
            changed, all other metadata reflects the current state of the feed
            and its datastreams. If a datastream had no values at the time
            specified (either because it didn't exist or because it hadn't
            been updated) it will be excluded from the output

        find_previous:
            Will also return the previous value to the date range being
            requested.
            Note that this is useful for any graphing because if you want to
            draw a graph of the date range you specified you would end up with
            a small gap until the first value.

        interval_type:
            If set to "discrete" the data will be returned in fixed time
            interval format according to the inverval value supplied. If this
            is not set, the raw datapoints will be returned.

        interval:
            Determines what interval of data is requested and is defined in
            seconds between the datapoints. If a value is passed in which does
            not match one of these values, it is rounded up to the next value.
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

        If api_key or feed_id arguments are not set when calling this method
        then the values set during this object's instantiation
        (ie. in __init__) are used.
        """

        if feed_id is None:
            feed_id = self.feed_id

        url = "%s/feeds/%s.%s" % (self.api_url, feed_id, format)

        if parameters:
            params = urllib.urlencode(parameters)
            url = "%s?%s" % (url, params)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._get(url, headers)
        if result:
            response, responseBody = result
            if response.code == 200:
                dataStructure = self._convertToCosmStructure(responseBody,
                                                             format,
                                                             txcosm.View_Feed_Msg)
                defer.returnValue(dataStructure)
            else:
                logging.error('Problem reading feed. Expected response code 200 got %s' % response.code)
                defer.returnValue(None)
        else:
            logging.error('Problem reading feed. Request failed')
            defer.returnValue(None)

    @defer.inlineCallbacks
    def update_feed(self, api_key=None, feed_id=None,
                    format=txcosm.DataFormats.JSON, data=None):
        """
        Updates [environment ID]'s environment and datastreams. If successful,
        the current datastream values are stored and any changes in environment
        metadata overwrite previous values. Cosm stores a server-side timestamp
        in the "updated" attribute and sets the feed to "live" if it wasn't
        before.

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param feed_id: The feed identifier
        @type feed_id: string
        @param format: The format to request the results in [json|xml|csv]
        @type format: string
        @param data: A representation of the feed in the appropriate format.
        @type data: string

        @return: A deferred that returns the success of the update based on
                 the response header data.
        @rtype: boolean

        If api_key or feed_id arguments are not set when calling this method
        then the values set during this object's instantiation
        (ie. in __init__) are used.
        """
        if feed_id is None:
            feed_id = self.feed_id

        url = "%s/feeds/%s.%s" % (self.api_url, feed_id, format)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._put(url, headers, data)
        if result:
            response, responseBody = result
            defer.returnValue(self._getResponseCodeStatusFromHeader(response))
        else:
            logging.error('Problem updating feed. Request failed')
            defer.returnValue(False)

    @defer.inlineCallbacks
    def delete_feed(self, api_key=None, feed_id=None):
        """
        The DELETE request does not require a format to be used. A request
        made to this URL will delete the object referred to by the ID.

        WARNING: This is final and cannot be undone.

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param feed_id: The feed identifier
        @type feed_id: string

        @return: A deferred that returns the success of the delete based on
                 the response header data.
        @rtype: boolean

        If api_key or feed_id arguments are not set when calling this method
        then the values set during this object's instantiation
        (ie. in __init__) are used.
        """
        if feed_id is None:
            feed_id = self.feed_id

        url = "%s/feeds/%s" % (self.api_url, feed_id)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._delete(url, headers)
        if result:
            response, responseBody = result
            defer.returnValue(self._getResponseCodeStatusFromHeader(response))
        else:
            logging.error('Problem deleting feed. Request failed')
            defer.returnValue(False)

    #
    # Datastreams
    #

    @defer.inlineCallbacks
    def create_datastream(self, api_key=None, feed_id=None,
        format=txcosm.DataFormats.JSON, data=None):
        """
        Creates new datastream(s) in environment [feed ID]. The body of the
        request should contain a JSON, XML or CSV representation of the
        datastream to be created.

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param feed_id: The feed identifier
        @type feed_id: string
        @param format: The format to request the results in [json|xml|csv]
        @type format: string
        @param data: A representation of the datastream to be created. Cosm
          currently requires that the datastream be wrapped in an environment.
          So the minimum data (in JSON format) necessary to create a new
          datastream is:
                        {
                         "version": "1.0.0"
                         "datastreams": [
                            {
                              "id": "test_datastream"
                            }
                          ],
                        }
        @type data: string

        @return: A deferred that returns the datastream_id of the created
         datastream or None.
        @rtype: boolean

        If api_key or feed_id arguments are not set when calling this method
        then the values set during this object's instantiation
         (ie. in __init__) are used.
        """
        if feed_id is None:
            feed_id = self.feed_id

        url = "%s/feeds/%s/datastreams.%s" % (self.api_url, feed_id, format)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._post(url, headers, data)
        if result:
            response, responseBody = result
            if response.code == 201:
                location = self._getLocationFromHeader(response)
                datastream_id = location.split("/")[-1]
                defer.returnValue(datastream_id)
            else:
                logging.error('Problem creating datastream. Expected response code 201 got %s' % response.code)
                defer.returnValue(None)
        else:
            logging.error('Problem creating datastream. Request failed')
            defer.returnValue(None)

    @defer.inlineCallbacks
    def read_datastream(self, api_key=None, feed_id=None, datastream_id=None,
                        format=txcosm.DataFormats.JSON, parameters=None):
        """
        Read the requested datastream.

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param feed_id: The feed identifier
        @type feed_id: string
        @param datastream_id: A datastream identifier
        @type datastream_id: string
        @param format: The format to request the results in [json|xml|csv|png]
        @type format: string
        @param parameters: Additional parameters to configure the png output.
        @type parameters: dict

        @return: A deferred that returns a txcosm.Datastream object or PNG
          file content. If a problem occurs None is returned.
        @rtype: txcosm.Datastream or None


        Available settings for parameters supporting historical queries:
        start:
            Defines the starting point of the query as a timestamp,
            e.g. 2010-05-20T11:01:46Z. The default value is blank.

        end:
        Defines the end point of the data returned as a timestamp,
        e.g. 2010-05-21T11:01:46Z. The default value is set to the current
        timestamp.

        duration:
            Specifies the duration of the query.
            If used in conjunction with end it will request the data prior to
            the end date.
            If used in conjunction with start it will request the data after
            the start date.
            If used by itself it will give the most recent data for the
            duration specified.
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
            Returns the feed with the values as they were at the specified
            timestamp.
            There are a few points to note about this functionality:

            Only the values of the datastream and their timestamps are changed,
            all other metadata reflects the current state of the feed and its
            datastreams. If a datastream had no values at the time specified
            (either because it didn't exist or because it hadn't been updated)
            it will be excluded from the output.

        find_previous:
            Will also return the previous value to the date range being
            requested. Note that this is useful for any graphing because if
            you want to draw a graph of the date range you specified you would
            end up with a small gap until the first value.

        interval_type:
            If set to "discrete" the data will be returned in fixed time
            interval format according to the inverval value supplied. If this
            is not set, the raw datapoints will be returned.

        interval:
            Determines what interval of data is requested and is defined in
            seconds between the datapoints. If a value is passed in which does
            not match one of these values, it is rounded up to the next value.
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

        Requesting the datastram as a PNG image will generate a graph. The
        time period that is shown is controlled by the history parameters
        passed to the request and the look and feel of this graph can be
        controlled by the following parameters:

        Parameter    Description    Example
        w    width in pixels         600
        h    height in pixels        400
        c    colour in hex           FFCC33
        t    title                   My Favourite Graph
        l    legend                  Legend For My Graph
        s    strokesize in pixels    4
        b    show axis labels        true / false
        g    show detailed grid      true / false

        If api_key or feed_id arguments are not set when calling this method
        then the values set during this object's instantiation
        (ie. in __init__) are used.
        """
        if feed_id is None:
            feed_id = self.feed_id

        url = "%s/feeds/%s/datastreams/%s.%s" % (self.api_url,
                                                 feed_id,
                                                 datastream_id,
                                                 format)

        if parameters:
            params = urllib.urlencode(parameters)
            url = "%s?%s" % (url, params)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._get(url, headers)
        if result:
            response, responseBody = result
            if response.code == 200:
                if format == txcosm.DataFormats.PNG:
                    defer.returnValue(responseBody)
                else:
                    dataStructure = self._convertToCosmStructure(responseBody,
                                                                 format,
                                                                 txcosm.View_Datastream_Msg)
                    defer.returnValue(dataStructure)
            else:
                logging.error('Problem reading datastream. Expected response code 200 got %s' % response.code)
                defer.returnValue(None)
        else:
            logging.error('Problem reading datastream. Request failed')
            defer.returnValue(None)

    @defer.inlineCallbacks
    def update_datastream(self, api_key=None, feed_id=None, datastream_id=None,
                          format=txcosm.DataFormats.JSON, data=None):
        """
        Update a single datastream

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param feed_id: The feed identifier
        @type feed_id: string
        @param datastream_id: A datastream identifier
        @type datastream_id: string
        @param format: The format to request the results in [json|xml|csv]
        @type format: string
        @param data: A representation of the datastream in the appropriate
          format.
        @type data: string

        @return: A deferred that returns the success of the create based on
                 the response header data.
        @rtype: boolean

        If api_key or feed_id arguments are not set when calling this method
        then the values set during this object's instantiation
        (ie. in __init__) are used.
        """
        if feed_id is None:
            feed_id = self.feed_id

        url = "%s/feeds/%s/datastreams/%s.%s" % (self.api_url,
                                                 feed_id,
                                                 datastream_id,
                                                 format)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._put(url, headers, data)
        if result:
            response, responseBody = result
            defer.returnValue(self._getResponseCodeStatusFromHeader(response))
        else:
            logging.error('Problem updating datastream. Request failed')
            defer.returnValue(False)

    @defer.inlineCallbacks
    def delete_datastream(self, api_key=None, feed_id=None,
                          datastream_id=None):
        """
        The DELETE request does not require a format to be used. A request
        made to this URL will delete the object referred to by the ID.

        WARNING: This is final and cannot be undone.

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param feed_id: The feed identifier
        @type feed_id: string
        @param datastream_id: A datastream identifier
        @type datastream_id: string

        @return: A deferred that returns the success status of the datastream
          delete.
        @rtype: boolean

        If api_key or feed_id arguments are not set when calling this method
        then the values set during this object's instantiation
        (ie. in __init__) are used.
        """
        if feed_id is None:
            feed_id = self.feed_id

        url = "%s/feeds/%s/datastreams/%s" % (self.api_url, feed_id, datastream_id)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._delete(url, headers)
        if result:
            response, responseBody = result
            defer.returnValue(self._getResponseCodeStatusFromHeader(response))
        else:
            logging.error('Problem deleting datastream. Request failed')
            defer.returnValue(False)

    #
    # Datapoints
    #

    @defer.inlineCallbacks
    def create_datapoints(self, api_key=None, feed_id=None, datastream_id=None,
                          format=txcosm.DataFormats.JSON, data=None):
        """
        Creates new datapoints for datastream. The body of the request
        should contain a JSON, XML or CSV representation of the datastream to
        be created.

        This enables you to insert datapoints into the history of the
        datastream.
        Datapoints should have a unique timestamp, which can to be specified
        down to the sub-second level. Sending new datapoints with the same
        timestamp as existing ones will overwrite the old data with the new.
        If a single update contains multiple values with the same timestamp
        (along with other records), then the result will be datapoints
        recorded for all unique timestamps, but for any duplicated ones, we
        will only record the last record processed.

        Currently you can only send a maximum of 500 datapoints in a single
        update.
        Attempting to send more than that will result in an error, and in that
        case none of your datapoints will be stored.

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param feed_id: The feed identifier
        @type feed_id: string
        @param datastream_id: A datastream identifier
        @type datastream_id: string
        @param format: The format to request the results in [json|xml|csv]
        @type format: string
        @param data: A representation of the datastream in the appropriate
          format.
        @type data: string

        @return: A deferred that returns the success status of the create
          action.
        @rtype: boolean

        If api_key or feed_id arguments are not set when calling this method
        then the values set during this object's instantiation
        (ie. in __init__) are used.
        """
        if feed_id is None:
            feed_id = self.feed_id

        url = "%s/feeds/%s/datastreams/%s/datapoints.%s" % (self.api_url,
                                                            feed_id,
                                                            datastream_id,
                                                            format)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._post(url, headers, data)
        if result:
            response, responseBody = result
            defer.returnValue(self._getResponseCodeStatusFromHeader(response))
        else:
            logging.error('Problem creating datapoints. Request failed')
            defer.returnValue(None)

    @defer.inlineCallbacks
    def read_datapoint(self, api_key=None, feed_id=None, datastream_id=None,
                       format=txcosm.DataFormats.JSON, timestamp=None):
        """
        Read a specific datapoint from the specified timestamp.

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param feed_id: The feed identifier
        @type feed_id: string
        @param datastream_id: A datastream identifier
        @type datastream_id: string
        @param format: The format to request the results in [json|xml|csv|png]
        @type format: string
        @param timestamp: An ISO8601 formatted datapoint timestamp. Examples:
                          2012-02-22T11:22:31Z
                          2012-02-22T11:22:31.130138Z
                          2012-02-22T11:22:31.130138+09:30
        @type timestamp: string

        @return: A deferred that returns the a txcosm.Datapoint object or None
        @rtype: string (in the format specified by the format argument)

        If api_key or feed_id arguments are not set when calling this method
        then the values set during this object's instantiation
        (ie. in __init__) are used.
        """
        if feed_id is None:
            feed_id = self.feed_id

        url = "%s/feeds/%s/datastreams/%s/datapoints/%s.%s" % (self.api_url,
                                                               feed_id,
                                                               datastream_id,
                                                               timestamp,
                                                               format)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._get(url, headers)
        if result:
            response, responseBody = result
            if response.code == 200:
                if "Not found" in responseBody:
                    logging.info("The specified datapoint [%s] could not be found" % timestamp)
                    defer.returnValue(None)
                else:
                    dataStructure = self._convertToCosmStructure(responseBody,
                                                                 format,
                                                                 txcosm.View_Datapoint_Msg)
                    defer.returnValue(dataStructure)
            else:
                logging.error('Problem reading datapoint. Expected response code 200 got %s' % response.code)
                defer.returnValue(None)
        else:
            logging.error('Problem reading datapoint. Request failed')
            defer.returnValue(None)

    @defer.inlineCallbacks
    def update_datapoint(self, api_key=None, feed_id=None, datastream_id=None,
                         format=txcosm.DataFormats.JSON, timestamp=None,
                         data=None):
        """
        Modify the value of a datapoint at the specified timestamp

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param feed_id: The feed identifier
        @type feed_id: string
        @param datastream_id: A datastream identifier
        @type datastream_id: string
        @param format: The format to request the results in [json|xml|csv|png]
        @type format: string
        @param timestamp: An ISO8601 formatted datapoint timestamp. Examples:
                          2012-02-22T11:22:31Z
                          2012-02-22T11:22:31.130138Z
                          2012-02-22T11:22:31.130138+09:30
        @type timestamp: string
        @param data: A representation of the updated datapoint in the
          appropriate format.
        @type data: string

        @return: A deferred that returns the success status from updating the
          datapoint
        @rtype: boolean

        If api_key or feed_id arguments are not set when calling this method
        then the values set during this object's instantiation
        (ie. in __init__) are used.
        """
        if feed_id is None:
            feed_id = self.feed_id

        url = "%s/feeds/%s/datastreams/%s/datapoints/%s.%s" % (self.api_url,
                                                               feed_id,
                                                               datastream_id,
                                                               timestamp,
                                                               format)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._put(url, headers, data)
        if result:
            response, responseBody = result
            defer.returnValue(self._getResponseCodeStatusFromHeader(response))
        else:
            logging.error('Problem updating datapoint. Request failed')
            defer.returnValue(None)

    @defer.inlineCallbacks
    def delete_datapoint(self, api_key=None, feed_id=None, datastream_id=None,
                         timestamp=None):
        """
        Delete a single datapoint at the specified timestamp.
        This request does not require a format to be used.

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param feed_id: The feed identifier
        @type feed_id: string
        @param datastream_id: A datastream identifier
        @type datastream_id: string
        @param timestamp: An ISO8601 formatted datapoint timestamp. Examples:
                          2012-02-22T11:22:31Z
                          2012-02-22T11:22:31.130138Z
                          2012-02-22T11:22:31.130138+09:30
        @type parameters: string

        @return: A deferred that returns the success of the create based on
                 the response header data.
        @rtype: boolean

        If api_key or feed_id arguments are not set when calling this method
        then the values set during this object's instantiation
        (ie. in __init__) are used.
        """
        if feed_id is None:
            feed_id = self.feed_id

        url = "%s/feeds/%s/datastreams/%s/datapoints/%s" % (self.api_url,
                                                            feed_id,
                                                            datastream_id,
                                                            timestamp)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._delete(url, headers)
        if result:
            response, responseBody = result
            defer.returnValue(self._getResponseCodeStatusFromHeader(response))
        else:
            logging.error('Problem deleting datapoint. Request failed')
            defer.returnValue(None)

    @defer.inlineCallbacks
    def delete_datapoints(self, api_key=None, feed_id=None, datastream_id=None,
                          parameters=None):
        """
        Remove a range of datapoints for this datastream.
        This request does not require a format to be used

        By providing a start and end timestamp as query parameters, you may
        remove a all datapoints that lie between those dates.
        If you send your request with only a start timestamp, all datapoints
        after the value will be removed.
        Likewise, providing an end timestamp will remove all datapoints prior
        to the supplied value.
        Additionally this endpoint supports a duration parameter
        (e.g. "duration=3hours") that will delete all datapoints from a start
        timestamp to the start timestamps + duration if a start parameter is
        provided, or from an end timestamp to the end timestamp - duration if
        an end parameter is provided.

        Available settings for parameters:
        start
            Define the start time (in ISO8601 format) from which to begin
            deleting datapoints.
            http://api.cosm.com/v2/feeds/1977/datastreams?start=2010-05-20T11:01:46.000000Z

        end
            Define the end time (in ISO8601 format) at which to stop deleting
            datapoints.
            http://api.cosm.com/v2/feeds/1977/datastreams?end=2011-05-20T11:01:46.000000Z
            http://api.cosm.com/v2/feeds/1977/datastreams?start=2010-05-20T11:01:46.000000Zend=2011-05-20T11:01:46.000000Z

        duration
            Define a duration across which to delete datapoints.
            When used with a start time then datapoints from the start
            timestamp to the start timestamps + duration will be deleted.
            When used with an end time then datapoints from the end timestamp
            to the end timestamp - duration will be deleted.
            http://api.cosm.com/v2/feeds/1977/datastreams?start=2010-05-20T11:01:46.000000Z&duration=3days


        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param feed_id: The feed identifier
        @type feed_id: string
        @param datastream_id: A datastream identifier
        @type datastream_id: string
        @param parameters: Additional parameters to configure the png output.
        @type parameters: dict

        @return: A deferred that returns the success of the create based on
                 the response header data.
        @rtype: boolean

        If api_key or feed_id arguments are not set when calling this method
        then the values set during this object's instantiation
        (ie. in __init__) are used.
        """
        if feed_id is None:
            feed_id = self.feed_id

        url = "%s/feeds/%s/datastreams/%s/datapoints" % (self.api_url,
                                                         feed_id,
                                                         datastream_id)

        if parameters:
            params = urllib.urlencode(parameters)
            url = "%s?%s" % (url, params)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._delete(url, headers)
        if result:
            response, responseBody = result
            defer.returnValue(self._getResponseCodeStatusFromHeader(response))
        else:
            logging.error('Problem deleting datapoints. Request failed')
            defer.returnValue(None)
    #
    # Triggers
    #

    @defer.inlineCallbacks
    def list_triggers(self, api_key=None, format=txcosm.DataFormats.JSON):
        """
        Retrieve a list of all triggers for the authenticated account

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param format: The format to request the results in [json|xml]
        @type format: string

        @return: A deferred that returns a list of triggers success of the
          create based on the response header data.
        @rtype: boolean

        If api_key argument is not set when calling this method then the
        default value set during this object's instantiation
        (ie. in __init__) is used.
        """
        url = "%s/triggers.%s" % (self.api_url, format)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._get(url, headers)
        if result:
            response, responseBody = result
            if response.code == 200:
                dataStructure = self._convertToCosmStructure(responseBody,
                                                             format,
                                                             txcosm.List_Triggers_Msg)
                defer.returnValue(dataStructure)
            else:
                logging.error('Problem listing triggers. Expected response code 200 got %s' % response.code)
                defer.returnValue(None)
        else:
            logging.error('Problem listing triggers. Request failed')
            defer.returnValue(None)

    @defer.inlineCallbacks
    def create_trigger(self, api_key=None, format=txcosm.DataFormats.JSON,
                       data=None):
        """
        Create a trigger

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param format: The format to request the results in [json|xml|csv]
        @type format: string
        @param data: Trigger definition in the appropriate format.
        @type data: string

        @return: A deferred that returns the trigger_id of the newly created
          trigger.
        @rtype: string

        If api_key argument is not set when calling this method then the
        default value set during this object's instantiation
        (ie. in __init__) is used.

        """
        url = "%s/triggers.%s" % (self.api_url, format)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._post(url, headers, data)
        if result:
            response, responseBody = result
            if response.code == 201:
                location = self._getLocationFromHeader(response)
                trigger_id = location.split("/")[-1]
                defer.returnValue(trigger_id)
            else:
                logging.error('Problem creating trigger. Expected response code 201 got %s' % response.code)
                defer.returnValue(None)
        else:
            logging.error('Problem creating trigger. Request failed')
            defer.returnValue(None)

    @defer.inlineCallbacks
    def read_trigger(self, api_key=None, trigger_id=None,
                     format=txcosm.DataFormats.JSON):
        """
        Returns a representation of a trigger

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param trigger_id: The trigger identifier
        @type trigger_id: string
        @param format: The format to request the results in [json|xml]
        @type format: string

        @return: A deferred that returns a txcosm.Trigger object or None.
        @rtype: string

        If api_key argument is not set when calling this method then the
        default value set during this object's instantiation
        (ie. in __init__) is used.
        """
        url = "%s/triggers/%s.%s" % (self.api_url, trigger_id, format)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._get(url, headers)
        if result:
            response, responseBody = result
            if response.code == 200:
                dataStructure = self._convertToCosmStructure(responseBody,
                                                             format,
                                                             txcosm.View_Trigger_Msg)
                defer.returnValue(dataStructure)
            else:
                logging.error('Problem reading trigger. Expected response code 200 got %s' % response.code)
                defer.returnValue(None)
        else:
            logging.error('Problem reading trigger. Request failed')
            defer.returnValue(None)

    @defer.inlineCallbacks
    def update_trigger(self, api_key=None, trigger_id=None,
                       format=txcosm.DataFormats.JSON, data=None):
        """
        Updates an existing trigger object.

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param trigger_id: The trigger identifier
        @type trigger_id: string
        @param format: The format to request the results in [json|xml]
        @type format: string
        @param data: A representation of the trigger in the appropriate format.
        @type data: string

        @return: A deferred that returns the success status of the update
          action or None.
        @rtype: boolean

        If api_key argument is not set when calling this method then the
        default value set during this object's instantiation
        (ie. in __init__) is used.
        """
        url = "%s/triggers/%s.%s" % (self.api_url, trigger_id, format)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._put(url, headers, data)
        if result:
            response, responseBody = result
            defer.returnValue(self._getResponseCodeStatusFromHeader(response))
        else:
            logging.error('Problem updating trigger. Request failed')
            defer.returnValue(None)

    @defer.inlineCallbacks
    def delete_trigger(self, api_key=None, trigger_id=None):
        """
        Delete a trigger.

        WARNING: This is final and cannot be undone.

        @param api_key: An api key with authorization settings allowing this
         action to be performed
        @type api_key: string
        @param trigger_id: The trigger identifier
        @type trigger_id: string

        @return: A deferred that returns the success status of the delete
         action or None.
        @rtype: boolean

        If api_key argument is not set when calling this method then the
        default value set during this object's instantiation
        (ie. in __init__) is used.
        """
        url = "%s/triggers/%s" % (self.api_url, trigger_id)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._delete(url, headers)
        if result:
            response, responseBody = result
            defer.returnValue(self._getResponseCodeStatusFromHeader(response))
        else:
            logging.error('Problem deleting trigger. Request failed')
            defer.returnValue(None)

    #
    # Users
    #

    @defer.inlineCallbacks
    def list_users(self, api_key=None, format=txcosm.DataFormats.JSON):
        """
        Retrieve a list of all users for the authenticated account

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param format: The format to request the results in [json|xml]
        @type format: string

        @return: A deferred that returns a list of users in the format
          specified by the format argument.
        @rtype: boolean

        If api_key argument is not set when calling this method then the
        default value set during this object's instantiation
        (ie. in __init__) is used.
        """
        url = "%s/users.%s" % (self.api_url, format)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._get(url, headers)
        if result:
            response, responseBody = result
            if response.code == 200:
                dataStructure = self._convertToCosmStructure(responseBody,
                                                             format,
                                                             txcosm.List_Users_Msg)
                defer.returnValue(dataStructure)
            else:
                logging.error('Problem listing users. Expected response code 200 got %s' % response.code)
                defer.returnValue(None)
        else:
            logging.error('Problem listing users. Request failed')
            defer.returnValue(None)

    @defer.inlineCallbacks
    def create_user(self, api_key=None, format=txcosm.DataFormats.JSON,
                    data=None):
        """
        Create a user

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param format: The format to request the results in [json|xml|csv]
        @type format: string
        @param data: User definition in the appropriate format.
        @type data: string

        @return: A deferred that returns the user id of the created user or
         None.
        @rtype: boolean

        If api_key argument is not set when calling this method then the
        default value set during this object's instantiation
        (ie. in __init__) is used.
        """
        url = "%s/users.%s" % (self.api_url, format)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._post(url, headers, data)
        if result:
            response, responseBody = result
            if response.code == 201:
                location = self._getLocationFromHeader(response)
                new_user = location.split("/")[-1]
                defer.returnValue(new_user)
            else:
                logging.error('Problem creating user. Expected response code 201 got %s' % response.code)
                defer.returnValue(None)
        else:
            logging.error('Problem creating user. Request failed')
            defer.returnValue(None)

    @defer.inlineCallbacks
    def read_user(self, api_key=None, user_id=None,
                  format=txcosm.DataFormats.JSON):
        """
        Returns the details of a specific user

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param user_id: The user identifier
        @type user_id: string
        @param format: The format to request the results in [json|xml]
        @type format: string

        @return: A deferred that returns a txcosm.User object or None
        @rtype: string

        If api_key argument is not set when calling this method then the
        default value set during this object's instantiation
        (ie. in __init__) is used.
        """
        url = "%s/users/%s.%s" % (self.api_url, user_id, format)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._get(url, headers)
        if result:
            response, responseBody = result
            if response.code == 200:
                dataStructure = self._convertToCosmStructure(responseBody,
                                                             format,
                                                             txcosm.View_User_Msg)
                defer.returnValue(dataStructure)
            else:
                logging.error('Problem reading user. Expected response code 200 got %s' % response.code)
                defer.returnValue(None)
        else:
            logging.error('Problem reading user. Request failed')
            defer.returnValue(None)

    @defer.inlineCallbacks
    def update_user(self, api_key=None, user_id=None,
                    format=txcosm.DataFormats.JSON, data=None):
        """
        Updates details of an existing user object.

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param user_id: The user identifier
        @type user_id: string
        @param format: The format to request the results in [json|xml]
        @type format: string
        @param data: Details of the user in the appropriate format.
        @type data: string

        @return: A deferred that returns the success status of the update user
         action or None.
        @rtype: boolean

        If api_key argument is not set when calling this method then the
        default value set during this object's instantiation
        (ie. in __init__) is used.
        """
        url = "%s/users/%s.%s" % (self.api_url, user_id, format)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._put(url, headers, data)
        if result:
            response, responseBody = result
            defer.returnValue(self._getResponseCodeStatusFromHeader(response))
        else:
            logging.error('Problem updating user. Request failed')
            defer.returnValue(None)

    @defer.inlineCallbacks
    def delete_user(self, api_key=None, user_id=None):
        """
        Delete a user.
        WARNING: This is final and cannot be undone.

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param user_id: The user identifier
        @type user_id: string

        @return: A deferred that returns the success status of the delete user
          action.
        @rtype: boolean

        If api_key argument is not set when calling this method then the
        default value set during this object's instantiation
        (ie. in __init__) is used.
        """
        url = "%s/users/%s.%s" % (self.api_url, user_id, format)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._delete(url, headers)
        if result:
            response, responseBody = result
            defer.returnValue(self._getResponseCodeStatusFromHeader(response))
        else:
            logging.error('Problem deleting user. Request failed')
            defer.returnValue(None)

    #
    # API Keys
    #

    @defer.inlineCallbacks
    def list_api_keys(self, api_key=None, format=txcosm.DataFormats.JSON):
        """
        Retrieve a list of all keys for the authenticated account.

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param format: The format to request the results in [json|xml]
        @type format: string

        @return: A deferred that returns a txcom.List_Keys_Msg or None.
        @rtype: A txcom.List_Keys_Msg or None

        If api_key argument is not set when calling this method then the
        default value set during this object's instantiation
        (ie. in __init__) is used.
        """
        url = "%s/keys.%s" % (self.api_url, format)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._get(url, headers)
        if result:
            response, responseBody = result
            if response.code == 200:
                dataStructure = self._convertToCosmStructure(responseBody,
                                                             format,
                                                             txcosm.List_Keys_Msg)
                defer.returnValue(dataStructure)
            else:
                logging.error('Problem reading API keys. Expected response code 200 got %s' % response.code)
                defer.returnValue(None)
        else:
            logging.error('Problem listing API keys. Request failed')
            defer.returnValue(None)

    @defer.inlineCallbacks
    def create_api_key(self, api_key=None, format=txcosm.DataFormats.JSON,
                       data=None):
        """
        Create a new API key

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param format: The format to request the results in [json|xml|csv|png]
        @type format: string
        @param data: key definition in the appropriate format.
        @type data: string

        @return: A deferred that returns the api key of the new key.
        @rtype: string

        If api_key argument is not set when calling this method then the
        default value set during this object's instantiation
        (ie. in __init__) is used.

        """
        url = "%s/keys.%s" % (self.api_url, format)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._post(url, headers, data)
        if result:
            response, responseBody = result
            if response.code == 201:
                location = self._getLocationFromHeader(response)
                new_api_key = location.split("/")[-1]
                defer.returnValue(new_api_key)
            else:
                logging.error('Problem creating API key. Expected response code 201 got %s' % response.code)
                defer.returnValue(None)
        else:
            logging.error('Problem creating API key. Request failed')
            defer.returnValue(None)

    @defer.inlineCallbacks
    def read_api_key(self, api_key=None, key_id=None,
                     format=txcosm.DataFormats.JSON):
        """
        Returns the details of a specific API Key

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param key_id: The API key identifier
        @type key_id: string
        @param format: The format to request the results in [json|xml]
        @type format: string

        @return: A deferred that returns a txcosm.Key object or None
        @rtype: string

        If api_key argument is not set when calling this method then the
        default value set during this object's instantiation
        (ie. in __init__) is used.
        """
        url = "%s/keys/%s.%s" % (self.api_url, key_id, format)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._get(url, headers)
        if result:
            response, responseBody = result
            if response.code == 200:
                dataStructure = self._convertToCosmStructure(responseBody,
                                                             format,
                                                             txcosm.View_Key_Msg)
                defer.returnValue(dataStructure)
            else:
                logging.error('Problem reading API key. Expected response code 200 got %s' % response.code)
                defer.returnValue(None)
        else:
            logging.error('Problem listing API key. Request failed')
            defer.returnValue(None)

    @defer.inlineCallbacks
    def delete_api_key(self, api_key=None, key_id=None):
        """
        Delete a API key.
        WARNING: This is final and cannot be undone.

        @param api_key: An api key with authorization settings allowing this
          action to be performed
        @type api_key: string
        @param key_id: The API key identifier
        @type key_id: string

        @return: A deferred that returns the success of the delete key action.
        @rtype: boolean

        If api_key argument is not set when calling this method then the
        default value set during this object's instantiation
        (ie. in __init__) is used.
        """
        url = "%s/keys/%s" % (self.api_url, key_id)

        if api_key is None:
            api_key = self.api_key

        headers = {'X-ApiKey': api_key}

        result = yield self._delete(url, headers)
        if result:
            response, responseBody = result
            defer.returnValue(self._getResponseCodeStatusFromHeader(response))
        else:
            logging.error('Problem deleting API key. Request failed')
            defer.returnValue(None)
