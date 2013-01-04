#!/usr/bin/env python

"""
A distutils installation script for txcosm.
"""

from distutils.core import setup
import txcosm


long_description = """txcosm is a Python Twisted package to communicate with the Cosm API. Use it to integrate non blocking access to the Cosm API into your Python Twisted application.

It implements the full Cosm API (Feeds, Datastreams, Datapoints, Triggers, Users, Keys) and many of the data structures (Unit, Location, Datapoint, Datastream, Environment, EnvironmentList, Trigger, TriggerList Key, KeyList, User, UserList) contained in requests and responses.

The data structures support encoding and decoding from JSON/XML formats. These structures are useful when building data to send to Cosm and also for processing Cosm data returned from queries.
"""


setup(name='txcosm',
      version='.'.join([str(x) for x in txcosm.version]),
      description='txcosm is a Python Twisted package to communicate with the Cosm API.',
      long_description=long_description,
      author='Chris Laws',
      author_email='clawsicus@gmail.com',
      license='http://www.opensource.org/licenses/mit-license.php',
      url='https://github.com/claws/txcosm',
      download_url='https://github.com/claws/txcosm/tarball/master',
      packages=['txcosm'],
      classifiers=['Development Status :: 4 - Beta',
                   'Environment :: Console',
                   'Intended Audience :: End Users/Desktop',
                   'Intended Audience :: Developers',
                   'License :: OSI Approved :: MIT License',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python',
                   'Framework :: Twisted',
                   'Topic :: Communications',
                   'Topic :: Home Automation',
                   'Topic :: System :: Monitoring',
                   'Topic :: Software Development :: Libraries :: Python Modules']
      )
