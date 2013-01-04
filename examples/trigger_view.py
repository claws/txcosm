#!/usr/bin/env python

"""
Lists triggers visible to the supplied Cosm user API key

To use this script you must create a text file containing your API key
and pass it to this script using the --keyfile argument as follows:

List all triggers visible to supplied key:
$ trigger_view.py --keyfile=/path/to/apikey/file

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


@defer.inlineCallbacks
def demo(key):

    client = Client()

    try:
        logging.info("Requesting a trigger list")
        trigger_list = yield client.list_triggers(api_key=key)
        if trigger_list:
            logging.info("Success retrieving a trigger list:\n%s\n" % trigger_list)
        else:
            logging.error("Problem occurred listing triggers")
    except Exception, ex:
        logging.error("Error: %s" % str(ex))

    reactor.callLater(0.1, reactor.stop)
    defer.returnValue(True)


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

    reactor.callWhenRunning(demo, key)
    reactor.run()
