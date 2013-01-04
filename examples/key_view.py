#!/usr/bin/env python

"""
Lists key(s) detail(s) visible to the supplied Cosm user API key

To use this script you must create a text file containing your API key
and pass it to this script using the --keyfile argument as follows:

List all keys visible to supplied key:
$ key_view.py --keyfile=/path/to/apikey/file

List details for a particular key
$ key_view.py --keyfile=path/to/apikey/file --key=XXX

txcosm must be installed or visible on the PYTHONPATH.
"""

import logging
from optparse import OptionParser
import os
import sys
from twisted.internet import reactor, defer
from txcosm.client import Client


parser = OptionParser("")
parser.add_option("-k", "--keyfile", dest="keyfile", default=None, help="Path to file containing your Cosm API key")
parser.add_option("-i", "--key", dest="key_id", default=None, help="A specific Cosm key id to view")


@defer.inlineCallbacks
def demo(key, key_id):

    client = Client()

    try:
        if key_id:
            # request key details for the supplied key only
            logging.info("Requesting key details for key: %s" % key_id)
            dataStructure = yield client.read_api_key(api_key=key, key_id=key_id)
        else:
            # request key details for all keys visible to the key supplied
            logging.info("Requesting a key listing")
            dataStructure = yield client.list_api_keys(api_key=key)

        logging.info("Received response from Cosm:\n%s\n" % dataStructure)

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
