#!/usr/bin/env python

"""
Thie script is used to test the timeout functionality.

It sets a ridiculously low value for the timeout to force a request
timeout.

To use this script you must create a text file containing your API key
and pass it to this script using the -k or --keyfile argument as follows:

List all keys visible to supplied key:
$ test_timeout.py --keyfile=/path/to/apikey/file

txcosm must be installed or visible on the PYTHONPATH.
"""

import logging
from optparse import OptionParser
import os
import sys
from twisted.internet import reactor, defer
from txcosm.HTTPClient import HTTPClient


parser = OptionParser("")
parser.add_option("-k", "--keyfile", dest="keyfile", default=None, help="Path to file containing your Cosm API key")


@defer.inlineCallbacks
def demo(key):

    client = HTTPClient()

    # set a REALLY low value to force timeout functionality
    client.request_timeout = 0.2

    try:
        # request key details for all keys visible to the key supplied
        logging.info("Requesting a key listing")
        dataStructure = yield client.list_api_keys(api_key=key)

        if dataStructure:
            logging.info("Received response from Cosm:\n%s\n" % dataStructure)
        else:
            logging.error("Unable to retrieve key list")

        reactor.callLater(0.1, reactor.stop)
        defer.returnValue(True)

    except Exception, ex:
        logging.exception(ex)
        reactor.callLater(0.1, reactor.stop)
        defer.returnValue(False)


if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s : %(message)s")

    (options, args) = parser.parse_args()

    # confirm keyfile is suppplied and valid
    if options.keyfile is None:
        print parser.get_usage()
        sys.exit(1)

    keyfile = os.path.expanduser(options.keyfile)
    if not os.path.exists(keyfile):
        logging.error("Invalid API key file path: %s" % keyfile)
        sys.exit(1)

    fd = open(keyfile, 'r')
    key = fd.read().strip()
    fd.close()

    reactor.callWhenRunning(demo, key, options.key_id)
    reactor.run()
