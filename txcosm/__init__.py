#!/usr/bin/env python

"""
The txcosm package is a Python Twisted implements the Cosm API in Python. It is built upon the
Twisted event driven networking framework.

This implementation closely follows the documented Cosm API located
at: http://api.cosm.com/v2/

Much of the API documentation has been shamelessly duplicated within the
method docstrings. The documentation on the Cosm API is quite clear.
Embedding the documentation within the docstrings means that the Python
help(txcosm) output will be useful. Always refer back to the Cosm
site for the most recent, up to date, API documentation.

The Cosm API allows users to request data in a variety of formats.
Currently only JSON and XML are supported by this implementation.
Specifying a different format will return a string and you are free to
manipulate it as you see fit.

Dependencies (other than Python):
twisted
pyOpenSSL

"""

try:
    from lxml import etree
except ImportError:
    try:
        from xml.etree import cElementTree as etree
    except ImportError:
        import xml.etree.ElementTree as etree
import json
import logging


version = (0, 1, 0)

# store the detected XML (EEML) namespace as it is need when search elements
Namespace = None

EEML_NAMESPACE = 'eeml'
OPENSEARCH_NAMESPACE = 'opensearch'
namespace_map = {EEML_NAMESPACE: 'http://www.eeml.org/xsd/0.5.1',
                 OPENSEARCH_NAMESPACE: 'http://a9.com/-/spec/opensearch/1.1/'}
try:
    register_namespace = etree.register_namespace
except AttributeError:
    def register_namespace(prefix, uri):
        etree._namespace_map[uri] = prefix

for prefix, uri in namespace_map.items():
    register_namespace(prefix, uri)


class DataFormats(object):
    """
    Define the data formats that can be sent and received
    """
    JSON = "json"
    XML = "xml"
    CSV = "csv"
    PNG = "png"


class DataFields(object):
    """
    Define the field names used within the data passed between the client
    and Cosm.
    """
    # A selection of common environment field keys that are useful when
    # building/inspecting json format objects to be sent to Cosm.
    About = u'about'
    Access_Method = u'access_method'
    Access_Methods = u'access_methods'
    Api_Key = u'api_key'
    At = u'at'
    Creatable_Role = u'creatable_role'
    Creatable_Roles = u'creatable_roles'
    Creator = u'creator'
    Current_Value = u'current_value'
    Data = u'data'
    Datapoints = u'datapoints'
    Datastream_Id = u'datastream_id'
    Datastream_Trigger = u'datastream-trigger'
    Datastream_Triggers = u'datastream-triggers'
    Datastreams = u'datastreams'
    Datastreams_Allowed = u'datastreams_allowed'
    Datastreams_Count = u'datastreams_count'
    Deliver_Email = u'deliver_email'
    Description = u'description'
    Display_Activity = u'display_activity'
    Display_Information = u'display_information'
    Display_Stats = u'display_stats'
    Disposition = u'disposition'
    Domain = u'domain'
    Elevation = u'ele'
    Email = u'email'
    Environment = u'environment'
    Environment_Id = u'environment_id'
    Exposure = u'exposure'
    Feed = u'feed'
    Feed_Id = u'feed_id'
    First_Name = u'first_name'
    Full_Name = u'full_name'
    Icon = u'icon'
    Id = u'id'
    Key = u'key'
    Keys = u'keys'
    Label = u'label'  # unit label
    Last_Name = u'last_name'
    Latitude = u'lat'
    Location = u'location'
    Login = u'login'
    Longitude = u'lon'
    Maximum_Value = u'max_value'
    Minimum_Interval = u'minimum_interval'
    Minimum_Value = u'min_value'
    Name = u'name'
    Notified_At = u'notified_at'
    Organisation = u'organisation'
    Permission = u'permission'
    Permissions = u'permissions'
    Private = u'private'
    Private_Access = u'private_access'
    Receive_Forum_Notifications = u'receive_formum_notifications'
    Referer = u'referer'
    Resources = u'resources'
    Results = u'results'
    Role = u'role'
    Roles = u'roles'
    Source_Ip = u'source_ip'
    Status = u'status'
    Stream_Id = u'stream_id'
    Subscribed_To_Mailings = u'subscribed_to_mailings'
    Symbol = u'symbol'  # unit symbol
    Tag = u'tag'
    Tags = u'tags'
    Threshold_Value = u'threshold_value'
    Title = u'title'
    Timestamp = u'timestamp'
    Timezone = u'timezone'
    Total_Api_Access_Count = u'total_api_access_count'
    Total_Results = u'totalResults'
    Triggering_Datastream = u'triggering_datastream'
    Trigger_Type = u'trigger_type'
    Type = u'type'  # unit type
    Unit = u'unit'
    User = u'user'
    Users = u'users'
    Updated = u'updated'
    Url = u'url'
    Value = u'value'
    Version = u'version'
    Waypoints = u'waypoint'
    Waypoints = u'waypoints'
    Website = u'website'


class DataStructure(object):
    """
    Base class for Cosm data structure objects

    Serialized versions of objects deriving from this class are passed between
    the Cosm API and the txcosm client. These structures are designed in
    such a way that they can be used for JSON or XML (EEML).
    """

    def toDict(self):
        """
        Return the data structure object as a dict. This method is used as
        a helper function for JSON serialization/deserialization.
        """
        raise NotImplementedError

    def toXml(self):
        """
        Return the object as an xml ElementTree

        @return: XML representation of the object
        @rtype: etree.Element
        """
        raise NotImplementedError

    def fromDict(self, inDict):
        """
        Populate attributes from a dict
        """
        raise NotImplementedError

    def fromXml(self, element):
        """
        Populate attributes from a XML etree

        @param xml: an xml element tree
        @type xml: etree.Element
        """
        raise NotImplementedError

    def encode(self, format=DataFormats.JSON):
        """
        Return a string representation of the object encoded in the specified format
        """
        if format == DataFormats.JSON:
            return json.dumps(self.toDict())

        elif format == DataFormats.XML:
            eeml = etree.Element('eeml')
            #eeml.attrib['xmlns'] = namespace_map[EEML_NAMESPACE]
            eeml.attrib['{%s}xsi' % namespace_map[EEML_NAMESPACE]] = 'http://www.w3.org/2001/XMLSchema-instance'
            eeml.attrib['version'] = '0.5.1'
            eeml.attrib['{%s}schemaLocation' % namespace_map[EEML_NAMESPACE]] = 'http://www.eeml.org/xsd/005'
            eeml.append(self.toXml())
            return etree.tostring(eeml)

        else:
            raise Exception("Don't know how to encode %s using format %s" % (self.__class__.__name__,
                                                                             format))

    def decode(self, data, format=DataFormats.JSON):
        """
        Decode data, in the specified format, into local attributes
        """
        if format == DataFormats.JSON:
            inDict = json.loads(data)
            self.fromDict(inDict)

        elif format == DataFormats.XML:
            # parse xml string, rip off the eeml wrapper and process
            # xml elements by handing off to fromXml method. All
            # viewable (feed, datastream, datapoint) XML items come
            # wrapped in the eeml, environment tags.
            element = etree.fromstring(data)
            environment = element.find("{%s}%s" % (namespace_map[EEML_NAMESPACE], DataFields.Environment))
            if environment is not None:
                self.fromXml(environment)

        else:
            raise Exception("Don't know how to decode %s using format %s" % (self.__class__.__name__,
                                                                             format))

    def __str__(self):
        """
        Return a string representation of this datapoint
        The JSON format is fairly clear so lets just return
        a pretty printed version of that.
        """
        return json.dumps(self.toDict(), sort_keys=True, indent=2)


class Unit(DataStructure):
    """ Models a Unit item within a Cosm data structure """

    # See http://www.eeml.org/#units
    Basic_Si = 'basicSI'                               # m, kg, etc
    Derived_Si = 'derivedSI'                           # newtons, ohms, hertz, etc
    Conversion_Based_Units = 'conversionBasedUnits'    # inches
    Derived_Units = 'derivedUnits'                     # miles per hour
    Context_Dependent_Units = 'contextDependentUnits'  # heartbeats per minute
    Valid_Unit_Types = [Basic_Si,
                        Derived_Si,
                        Conversion_Based_Units,
                        Derived_Units,
                        Context_Dependent_Units]

    def __init__(self, **kwargs):
        self._attributes = [DataFields.Label,
                            DataFields.Type,
                            DataFields.Symbol]
        self.label = None
        self.type = None
        self.symbol = None

        # initialise Unit attributes to specified values or None.
        self.fromDict(kwargs)

    def toDict(self):
        """
        Return the data structure object as a dict. This method is used as
        a helper function for JSON serialization/deserialization.
        """
        unitDict = dict()
        for attribute in self._attributes:
            attribute_value = getattr(self, attribute, None)
            if attribute_value:
                unitDict[attribute] = unicode(attribute_value)
        return unitDict

    def fromDict(self, inDict):
        """
        Populate attributes from a dict
        """
        for attribute in self._attributes:
            attribute_value = inDict.get(attribute, None)
            if attribute_value:
                if attribute == DataFields.Type:
                    if attribute_value not in Unit.Valid_Unit_Types:
                        raise Exception("Invalid unit type \'%s\' not in %s" % (attribute_value,
                                                                                Unit.Valid_Unit_Types))
                setattr(self, attribute, attribute_value)

    def toXml(self, parent=None):
        """
        Return the object as an xml ElementTree

        @param parent: The parent element
        @type parent: etree.Element

        @return: XML representation of the object
        @rtype: etree.Element
        """
        unit = etree.Element(DataFields.Unit)
        if self.type:
            unit.attrib[DataFields.Type] = self.type
        if self.symbol:
            unit.attrib[DataFields.Symbol] = self.symbol
        unit.text = self.label

        return unit

    def fromXml(self, element):
        """
        Populate attributes from a XML etree

        @param xml: an xml element tree
        @type xml: etree.Element
        """
        unit = element.find(DataFields.Unit)
        if unit is not None:
            unit_type = unit.attrib.get(DataFields.Type, None)
            if unit_type:
                self.type = unicode(unit_type)
            unit_symbol = unit.attrib.get(DataFields.Symbol, None)
            if unit_symbol:
                self.symbol = unicode(unit_symbol)
            self.label = unicode(unit.text)


class Waypoint(DataStructure):
    """ Models a Waypoint item within a location """

    def __init__(self, **kwargs):
        self._attributes = [DataFields.At,
                            DataFields.Latitude,
                            DataFields.Longitude,
                            DataFields.Elevation]
        self.at = None
        self.lat = None
        self.lon = None
        self.ele = None

        # initialise Waypoint attributes to specified values or None.
        self.fromDict(kwargs)

    def toDict(self):
        """
        Return the data structure object as a dict. This method is used as
        a helper function for JSON serialization/deserialization.
        """
        waypointDict = dict()
        for attribute in self._attributes:
            attribute_value = getattr(self, attribute, None)
            if attribute_value:
                waypointDict[attribute] = unicode(attribute_value)
        return waypointDict

    def fromDict(self, inDict):
        """
        Populate attributes from a dict
        """
        for attribute in self._attributes:
            attribute_value = inDict.get(attribute, None)
            if attribute_value:
                setattr(self, attribute, attribute_value)

    def toXml(self, parent=None):
        """
        Return the object as an xml ElementTree

        @param parent: The parent element
        @type parent: etree.Element

        @return: XML representation of the object
        @rtype: etree.Element
        """
        waypoint = etree.Element(DataFields.Waypoint)
        waypoint.attrib[DataFields.At] = self.at
        waypoint.text = self.value

        if self.lat:
            lat = etree.SubElement(waypoint, DataFields.Latitude)
            lat.text = unicode(self.lat)

        if self.lon:
            lon = etree.SubElement(waypoint, DataFields.Longitude)
            lon.text = unicode(self.lon)

        if self.ele:
            ele = etree.SubElement(waypoint, DataFields.Elevation)
            ele.text = unicode(self.ele)

        return waypoint

    def fromXml(self, element):
        """
        Populate attributes from a XML etree

        @param xml: an xml element tree
        @type xml: etree.Element
        """
        waypoint = element.find(DataFields.Waypoint)
        if waypoint is not None:
            at_time = waypoint.attrib.get(DataFields.At, None)
            if at_time:
                self.at = unicode(at_time)
            value = waypoint.text
            if value:
                self.value = value

            latitude = waypoint.find(DataFields.Latitude)
            if latitude is not None:
                self.lat = float(latitude.text)

            logitude = waypoint.find(DataFields.Longitude)
            if logitude is not None:
                self.lon = float(logitude.text)

            elevaltion = waypoint.find(DataFields.Elevation)
            if elevaltion is not None:
                self.ele = unicode(elevaltion.text)


class Datapoint(DataStructure):
    """ Models a Datapoint item within a datastream """

    def __init__(self, **kwargs):
        self._attributes = [DataFields.At,
                            DataFields.Value]
        self.at = None
        self.value = None

        # initialise Datapoint attributes to specified values or None.
        self.fromDict(kwargs)

    def toDict(self):
        """
        Return the data structure object as a dict. This method is used as
        a helper function for JSON serialization/deserialization.
        """
        datapointDict = dict()
        for attribute in self._attributes:
            attribute_value = getattr(self, attribute, None)
            if attribute_value:
                datapointDict[attribute] = unicode(attribute_value)
        return datapointDict

    def fromDict(self, inDict):
        """
        Populate attributes from a dict
        """
        for attribute in self._attributes:
            attribute_value = inDict.get(attribute, None)
            if attribute_value:
                setattr(self, attribute, attribute_value)

    def toXml(self, parent=None):
        """
        Return the object as an xml ElementTree

        @param parent: The parent element
        @type parent: etree.Element

        @return: XML representation of the object
        @rtype: etree.Element
        """
        value = etree.Element(DataFields.Value)
        value.attrib[DataFields.At] = self.at
        value.text = self.value
        return value

    def fromXml(self, element):
        """
        Populate attributes from a XML etree

        @param xml: an xml element tree
        @type xml: etree.Element
        """
        datapoint = element.find(DataFields.Value)
        if datapoint is not None:
            at_time = datapoint.attrib.get(DataFields.At, None)
            if at_time:
                self.at = unicode(at_time)
            value = datapoint.text
            if value:
                self.value = value


class Permission(DataStructure):
    """ Models a Permission item within a API key """

    def __init__(self, **kwargs):
        self._attributes = [DataFields.Access_Methods,
                            DataFields.Label,
                            DataFields.Minimum_Interval,
                            DataFields.Referer,
                            DataFields.Resources,
                            DataFields.Source_Ip]

        self.access_methods = None
        self.label = None
        self.minimum_interval = None
        self.referer = None
        self.resources = None
        self.source_ip = None

        # initialise Permissions attributes to specified values or None.
        self.fromDict(kwargs)

    def toDict(self):
        """
        Return the data structure object as a dict. This method is used as
        a helper function for JSON serialization/deserialization.
        """
        permissionDict = dict()
        for attribute in self._attributes:
            attribute_value = getattr(self, attribute, None)
            if attribute_value:
                if attribute == DataFields.Access_Methods:
                    permissionDict[attribute] = attribute_value
                else:
                    permissionDict[attribute] = unicode(attribute_value)
        return permissionDict

    def fromDict(self, inDict):
        """
        Populate attributes from a dict
        """
        for attribute in self._attributes:
            attribute_value = inDict.get(attribute, None)
            if attribute_value:
                setattr(self, attribute, attribute_value)

    def toXml(self, parent=None):
        """
        Return the object as an xml ElementTree

        @param parent: The parent element
        @type parent: etree.Element

        @return: XML representation of the object
        @rtype: etree.Element
        """
        permission = etree.Element(DataFields.Permission)
        access_methods = etree.SubElement(permission, DataFields.Access_Methods)
        for p in self.access_methods:
            access_method = etree.SubElement(access_methods, DataFields.Access_Method)
            access_method.text = p
        return permission

    def fromXml(self, element):
        """
        Populate attributes from a XML etree

        @param xml: an xml element tree
        @type xml: etree.Element
        """
        permission = element.find(DataFields.Permission)
        if permission is not None:
            access_methods = permission.find(DataFields.Access_Methods)
            if access_methods is not None:
                self.access_methods = []
                for access_method in access_methods.findall(DataFields.Access_Method):
                    self.access_methods.append(access_method.text)


class Location(DataStructure):

    # Exposure kinds
    Indoor = "indoor"
    Outdoor = "outdoor"
    Valid_Exposure_Kinds = [Indoor, Outdoor]

    # Domina kinds
    Physical = 'physical'
    Virtual = 'virtual'
    Valid_Domain_Kinds = [Physical, Virtual]

    # Disposition kinds
    Fixed = 'fixed'
    Mobile = 'mobile'
    Valid_Disposition_Kinds = [Fixed, Mobile]

    def __init__(self, **kwargs):
        self._attributes = [DataFields.Disposition,
                            DataFields.Domain,
                            DataFields.Elevation,
                            DataFields.Exposure,
                            DataFields.Latitude,
                            DataFields.Longitude,
                            DataFields.Name,
                            DataFields.Waypoints]
        self.disposition = None
        self.domain = None
        self.ele = None
        self.exposure = None
        self.lat = None
        self.lon = None
        self.name = None
        self.waypoints = []

        # initialise attributes to specified values.
        self.fromDict(kwargs)

    def toDict(self):
        """
        Return the data structure object as a dict. This method is used as
        a helper function for JSON serialization/deserialization.
        """
        locationDict = dict()
        for attribute in self._attributes:
            attribute_value = getattr(self, attribute, None)
            if attribute_value:
                if attribute == DataFields.Waypoints:
                    waypoints = attribute_value
                    locationDict[attribute] = list()
                    for waypoint in waypoints:
                        locationDict[attribute].append(waypoint.toDict())
                else:
                    locationDict[attribute] = attribute_value
        return locationDict

    def fromDict(self, inDict):
        """
        Populate attributes from a dict
        """
        for attribute in self._attributes:
            attribute_value = inDict.get(attribute, None)
            if attribute_value:
                if attribute == DataFields.Disposition:
                    if attribute_value not in Location.Valid_Disposition_Kinds:
                        raise Exception("Invalid disposition \'%s\' not in %s" % (attribute_value,
                                                                                  Location.Valid_Disposition_Kinds))
                if attribute == DataFields.Domain:
                    if attribute_value not in Location.Valid_Domain_Kinds:
                        raise Exception("Invalid domain \'%s\' not in %s" % (attribute_value,
                                                                             Location.Valid_Domain_Kinds))

                if attribute == DataFields.Exposure:
                    if attribute_value not in Location.Valid_Exposure_Kinds:
                        raise Exception("Invalid exposure \'%s\' not in %s" % (attribute_value,
                                                                               Location.Valid_Exposure_Kinds))
                if attribute == DataFields.Waypoints:
                    waypoints = getattr(self, DataFields.Waypoints)
                    waypoints = []
                    for waypointKwargs in attribute_value:
                        waypoints.append(Waypoint(**waypointKwargs))
                    setattr(self, attribute, waypoints)
                else:
                    setattr(self, attribute, attribute_value)

    def toXml(self, parent=None):
        """
        Return the object as an xml ElementTree

        @param parent: The parent element
        @type parent: etree.Element

        @return: XML representation of the object
        @rtype: etree.Element
        """
        location = etree.Element(DataFields.Location)
        if self.domain:
            location.attrib[DataFields.Domain] = self.domain
        if self.exposure:
            location.attrib[DataFields.Exposure] = self.exposure
        if self.disposition:
            location.attrib[DataFields.Disposition] = self.disposition

        if self.name:
            name = etree.SubElement(location, DataFields.Name)
            name.text = self.name
        if self.lat:
            lat = etree.SubElement(location, DataFields.Latitude)
            lat.text = unicode(self.lat)
        if self.lon:
            lon = etree.SubElement(location, DataFields.Longitude)
            lon.text = unicode(self.lon)
        if self.ele:
            ele = etree.SubElement(location, DataFields.Elevation)
            ele.text = unicode(self.ele)

        if self.waypoints:
            waypoints = etree.SubElement(location, DataFields.Waypoints)
            for waypoint in self.waypoints:
                waypoints.append(waypoint.toXml())

        return location

    def fromXml(self, element):
        """
        Populate attributes from a XML etree

        @param xml: an xml element tree
        @type xml: etree.Element
        """
        location = element.find(DataFields.Location)
        if location is not None:
            domain = location.attrib.get(DataFields.Domain, None)
            if domain:
                self.domain = domain
            exposure = location.attrib.get(DataFields.Exposure, None)
            if exposure:
                self.exposure = exposure
            disposition = location.attrib.get(DataFields.Disposition, None)
            if disposition:
                self.disposition = disposition

            name = location.find(DataFields.Name)
            if name is not None:
                self.name = name.text

            latitude = location.find(DataFields.Latitude)
            if latitude is not None:
                self.lat = float(latitude.text)

            logitude = location.find(DataFields.Longitude)
            if logitude is not None:
                self.lon = float(logitude.text)

            elevaltion = location.find(DataFields.Elevation)
            if elevaltion is not None:
                self.ele = unicode(elevaltion.text)


class Datastream(DataStructure):
    """ Models a datastream structure within an environment """

    def __init__(self, **kwargs):
        self._attributes = [DataFields.At,
                            DataFields.Current_Value,
                            DataFields.Datapoints,
                            DataFields.Id,
                            DataFields.Maximum_Value,
                            DataFields.Minimum_Value,
                            DataFields.Tags,
                            DataFields.Unit,
                            DataFields.Updated]
        self.id = None
        self.at = None
        self.current_value = None
        self.max_value = None
        self.min_value = None
        self.updated = None
        self.datapoints = []
        self.tags = []
        self.unit = None

        # initialise attributes to specified values.
        self.fromDict(kwargs)

    def toDict(self):
        """
        Return the data structure object as a dict. This method is used as
        a helper function for JSON serialization/deserialization.
        """
        datastreamDict = dict()
        for attribute in self._attributes:
            attribute_value = getattr(self, attribute, None)
            if (attribute_value is not None) and (attribute_value != []):
                if attribute == DataFields.Datapoints:
                    datapoints = attribute_value
                    datastreamDict[attribute] = list()
                    for datapoint in datapoints:
                        datastreamDict[attribute].append(datapoint.toDict())

                elif attribute == DataFields.Unit:
                    unit = attribute_value
                    datastreamDict[attribute] = unit.toDict()
                else:
                    datastreamDict[attribute] = unicode(attribute_value)
        return datastreamDict

    def fromDict(self, inDict):
        """
        Populate attributes from a dict
        """
        for attribute in self._attributes:
            attribute_value = inDict.get(attribute, None)
            if (attribute_value is not None) and (attribute_value != []):
                if attribute == DataFields.Datapoints:
                    if not hasattr(self, DataFields.Datapoints):
                        setattr(self, attribute, list())
                    datapoints = getattr(self, DataFields.Datapoints)
                    datapoints_list = attribute_value
                    for datapointsKwargs in datapoints_list:
                        datapoints.append(Datapoint(**datapointsKwargs))
                    setattr(self, attribute, datapoints)

                elif attribute == DataFields.Unit:
                    unitKwargs = attribute_value
                    setattr(self, attribute, Unit(**unitKwargs))
                else:
                    setattr(self, attribute, attribute_value)

    def toXml(self, parent=None):
        """
        Return the object as an xml ElementTree

        @param parent: The parent element
        @type parent: etree.Element

        @return: XML representation of the object
        @rtype: etree.Element
        """
        data = etree.Element(DataFields.Data)
        data.attrib[DataFields.Datastream_Id] = unicode(self.id)

        if self.tags:
            for tag_label in self.tags:
                tag = etree.SubElement(data, DataFields.Tag)
                tag.text = tag_label

        if self.current_value:
            current_value = etree.SubElement(data, DataFields.Current_Value)
            current_value.text = self.current_value

        if self.max_value:
            max_value = etree.SubElement(data, DataFields.Maximum_Value)
            max_value.text = unicode(self.max_value)

        if self.min_value:
            min_value = etree.SubElement(data, DataFields.Minimum_Value)
            min_value.text = unicode(self.min_value)

        if self.unit:
            data.append(self.unit.toXml())

        if self.updated:
            updated = etree.SubElement(data, DataFields.Updated)
            updated.text = self.updated

        if self.datapoints:
            datapoints = etree.SubElement(data, DataFields.Datapoints)
            for datapoint in self.datapoints:
                datapoints.append(datapoint.toXml())

        return data

    def fromXml(self, element):
        """
        Populate attributes from a XML etree

        @param xml: an xml element tree
        @type xml: etree.Element
        """
        data = element.find(DataFields.Data)
        if data is not None:
            id = data.attrib.get(DataFields.Datastream_Id, None)
            if id:
                self.id = id

            if data.find(DataFields.Tag) is not None:
                self.tags = []
                for tag in data.findall(DataFields.Tag):
                    self.tags.append(tag.text)

            current_value = data.find(DataFields.Current_Value)
            if current_value is not None:
                self.current_value = unicode(current_value.text)
                at_time = current_value.attrib.get(DataFields.At, None)
                if at_time:
                    self.at = unicode(at_time)

            max_value = data.find(DataFields.Maximum_Value)
            if max_value is not None:
                self.max_value = max_value.text

            min_value = data.find(DataFields.Minimum_Value)
            if min_value is not None:
                self.min_value = min_value.text

            unit = data.find(DataFields.Unit)
            if unit is not None:
                self.unit = Unit()
                self.unit.fromXml(unit)

            updated = data.find(DataFields.Updated)
            if updated is not None:
                self.updated = unicode(updated.text)

            datapoints = data.find(DataFields.Datapoints)
            if datapoints is not None:
                self.datapoints = []
                for value in datapoints.findall(DataFields.Value):
                    d = Datapoint()
                    d.fromXml(value)
                    self.datapoints.append(d)

    def setCurrentValue(self, value):
        """
        Set the current value of the datastream.

        @param value: the current value for the datastream
        @type value: string
        """
        self.current_value = value

    def addDatapoint(self, timestamp, value):
        """
        Add a historical datapoint to the datastream.

        @param timestamp: An timestamp in ISO8601 format
        @type timestamp: string
        @param value: the current value for the datastream
        @type value: string
        """
        inDict = {DataFields.At: timestamp, DataFields.Value: value}
        self.datapoints.append(Datapoint(**inDict))

    def clear(self):
        """
        Clear current value and datapoints. This method exists so that the
        datapoints and current value can be cleared after they have been posted
        to Cosm. This would only be necessary if users wanted to keep this
        object between Cosm updates.
        """
        self.current_value = None
        del self.datapoints[:]


class Environment(DataStructure):
    """ Models a Cosm Environment (feed) object """

    def __init__(self, **kwargs):
        self._attributes = [DataFields.Creator,
                            DataFields.Datastreams,
                            DataFields.Description,
                            DataFields.Feed,
                            DataFields.Icon,
                            DataFields.Id,
                            DataFields.Location,
                            DataFields.Private,
                            DataFields.Status,
                            DataFields.Tags,
                            DataFields.Title,
                            DataFields.Updated,
                            DataFields.Version,
                            DataFields.Website]
        self.creator = None
        self.datastreams = {}
        self.description = None
        self.feed = None
        self.icon = None
        self.id = None
        self.location = None
        self.private = None
        self.status = None
        self.tags = None
        self.title = None
        self.updated = None
        self.version = version
        self.website = None

        # initialise attributes to specified values.
        self.fromDict(kwargs)

    def toDict(self):
        """
        Return the data structure object as a dict. This method is used as
        a helper function for JSON serialization/deserialization.
        """
        environmentDict = dict()
        for attribute in self._attributes:
            attribute_value = getattr(self, attribute, None)
            if attribute_value:
                if attribute == DataFields.Id:
                    environmentDict[attribute] = attribute_value

                elif attribute == DataFields.Location:
                    environmentDict[attribute] = self.location.toDict()

                elif attribute == DataFields.Datastreams:
                    datastreams = []
                    for datastream_id, datastream in self.datastreams.items():
                        datastreams.append(datastream.toDict())
                        environmentDict[DataFields.Datastreams] = datastreams
                else:
                    environmentDict[attribute] = attribute_value
        return environmentDict

    def fromDict(self, inDict):
        """
        Populate attributes from a dict
        """
        for attribute in self._attributes:
            attribute_value = inDict.get(attribute, None)
            if attribute_value:

                if attribute == DataFields.Location:
                    locationKwargs = attribute_value
                    setattr(self, attribute, Location(**locationKwargs))

                elif attribute == DataFields.Datastreams:
                    if not hasattr(self, DataFields.Datastreams):
                        setattr(self, attribute, dict())
                    datastreams = getattr(self, DataFields.Datastreams)
                    datastreamsKwargs = attribute_value
                    for datastreamKwargs in datastreamsKwargs:
                        datastream = Datastream(**datastreamKwargs)
                        datastreams[datastream.id] = datastream

                else:
                    setattr(self, attribute, attribute_value)

    def toXml(self):
        """
        Return the object as an xml ElementTree

        @return: XML representation of the object
        @rtype: etree.Element
        """
        env = etree.Element(DataFields.Environment)
        if self.creator:
            env.attrib[DataFields.Creator] = self.creator
        if self.id:
            env.attrib[DataFields.Id] = unicode(self.id)
        if self.updated:
            env.attrib[DataFields.Updated] = unicode(self.updated)

        if self.description:
            desc = etree.SubElement(env, DataFields.Description)
            desc.text = unicode(self.description)
        if self.feed:
            feed = etree.SubElement(env, DataFields.Feed)
            feed.text = unicode(self.feed)
        if self.icon:
            icon = etree.SubElement(env, DataFields.Icon)
            icon.text = unicode(self.icon)
        if self.private:
            private = etree.SubElement(env, DataFields.Private)
            private.text = unicode(self.private)
        if self.status:
            status = etree.SubElement(env, DataFields.Status)
            status.text = unicode(self.status)
        if self.tags:
            for tag_text in self.tags:
                tag = etree.SubElement(env, DataFields.Tag)
                tag.text = unicode(tag_text)
        if self.title:
            title = etree.SubElement(env, DataFields.Title)
            title.text = unicode(self.title)
        if self.version:
            version = etree.SubElement(env, DataFields.Version)
            version.text = unicode(self.version)
        if self.website:
            website = etree.SubElement(env, DataFields.Website)
            website.text = unicode(self.website)

        if self.location:
            env.append(self.location.toXml())

        if self.datastreams:
            for datastream_id, datastream in self.datastreams.items():
                env.append(datastream.toXml())

        return env

    def fromXml(self, element):
        """
        Populate attributes from a XML etree

        @param xml: an xml element tree
        @type xml: etree.Element
        """
        environment = element.find(DataFields.Environment)
        if environment is not None:
            creator = environment.attrib.get(DataFields.Creator, None)
            if creator:
                self.creator = creator
            id = environment.attrib.get(DataFields.Id, None)
            if id:
                self.id = id
            updated = environment.attrib.get(DataFields.Updated, None)
            if updated:
                self.updated = updated

            description = environment.find(DataFields.Description, None)
            if description is not None:
                self.description = description
            feed = environment.find(DataFields.Feed, None)
            if feed is not None:
                self.feed = feed.text
            icon = environment.find(DataFields.Icon, None)
            if icon is not None:
                self.icon = icon.text
            private = environment.find(DataFields.Private, None)
            if private is not None:
                self.private = private.text
            status = environment.find(DataFields.Status, None)
            if status is not None:
                self.status = status.text
            tag = environment.find(DataFields.Tag, None)
            if tag is not None:
                self.tags = []
                for tag in environment.findall(DataFields.Tag):
                    self.tags.append(tag.text)
            title = environment.find(DataFields.Title, None)
            if title is not None:
                self.title = title.text
            version = environment.find(DataFields.Version, None)
            if version is not None:
                self.version = version.text
            website = environment.find(DataFields.Website, None)
            if website is not None:
                self.website = website.text

            location = environment.find(DataFields.Location)
            if location is not None:
                loc = Location()
                loc.fromXml(location)
                self.location = loc

            data_element = environment.find(DataFields.Data)
            if data_element is not None:
                self.datastreams = []
                for datastream in environment.findall(DataFields.Data):
                    ds = Datastream()
                    ds.fromXml(datastream)
                    self.datastreams.append(ds)

    def setCurrentValue(self, datastream_id, value):
        """
        Set the current value for a datastream.

        @param datastream_id: The identifier of the datastream to be updated
        @type datastream_id: string
        @param value: The current value for the datastream
        @type value: string
        """
        if datastream_id not in self.datastreams:
            inDict = {DataFields.Id: datastream_id}
            self.datastreams[datastream_id] = Datastream(**inDict)
        datastream = self.datastreams[datastream_id]
        datastream.setCurrentValue(value)

    def addDatapoint(self, datastream_id, at_time, value):
        """
        Set a datepoint in a datastream.

        @param datastream_id: The identifier of the datastream to be updated
        @type datastream_id: string
        @param at_time: The timestamp for the datapoint, in ISO8601 format
        @type at_time: string
        @param value: The current value for the datastream
        @type value: string
        """
        if datastream_id not in self.datastreams:
            inDict = {DataFields.Id: datastream_id}
            self.datastreams[datastream_id] = Datastream(**inDict)
        datastream = self.datastreams[datastream_id]
        datastream.addDatapoint(at_time, value)

    def setLocation(self, name=None, exposure=None, domain=None, disposition=None,
                    latitude=None, longitude=None, elevation=None):
        """
        Set the location data for this environment

        @param name: The name of the location
        @type name: string
        @param exposure: Defines the exposure of the environment. Use
                         constants from the Location data structure:
                         eg. Location.Outdoor | lLocation.Indoor
        @type exposure: string
        @param domain: Defines the domain of the enviromnment. Use
                       constants from the Location data structure:
                       Location.Physical | Location.Virtual
        @type domain: string
        @param disposition: Defines the disposition of the enviromnment. Use
                            constants from the Location data structure:
                            Location.Fixed | Location.Mobile
        @type name: string
        @param latitude: The latitude of the environment
        @type latitude: float
        @param longitude: The longitude of the environment
        @type longitude: float
        @param elevation: The elevation of the environment
        @type elevation: float
        """
        locationKwargs = dict()
        if name:
            locationKwargs[DataFields.Name] = name
        if exposure:
            locationKwargs[DataFields.Exposure] = exposure
        if domain:
            locationKwargs[DataFields.Domain] = domain
        if disposition:
            locationKwargs[DataFields.Disposition] = disposition
        if latitude:
            locationKwargs[DataFields.Latitude] = latitude
        if longitude:
            locationKwargs[DataFields.Longitude] = longitude
        if elevation:
            # elevation is stored internally as a string
            locationKwargs[DataFields.Elevation] = "%.1f" % elevation
        self.location = Location(**locationKwargs)


class EnvironmentList(DataStructure):
    """
    Models a Cosm Environment (feed) list object - this object is returned
    from client list_feeds method.
    """

    def __init__(self, **kwargs):

        self.total_results = None
        self.feeds = []

        # initialise attributes to specified values.
        self.fromDict(kwargs)

    def toDict(self):
        """
        Return the data structure object as a dict. This method is used as
        a helper function for JSON serialization/deserialization.
        """
        environmentListDict = dict()
        environmentListDict[DataFields.Total_Results] = self.total_results
        results = []
        for feed in self.feeds:
            results.append(feed.toDict())
        environmentListDict[DataFields.Results] = results

        return environmentListDict

    def fromDict(self, inDict):
        """
        Populate attributes from a dict
        """
        total_results = inDict.get(DataFields.Total_Results, None)
        if total_results:
            self.total_results = total_results

        results = inDict.get(DataFields.Results, None)
        if results:
            self.feeds = []
            for result in results:
                self.feeds.append(Environment(**result))

    # The txcosm implementation never sends this structure to Cosm.
    # It only ever receives environment lists from Cosm.
    # Therefore toXml and encode methods are not really required.
    def toXml(self):
        """
        Return the object as an xml ElementTree

        @return: XML representation of the object
        @rtype: etree.Element
        """
        return None

    def fromXml(self, element):
        """
        Populate attributes from a XML etree

        @param xml: an xml element tree
        @type xml: etree.Element
        """
        total_results = element.find('{%s}%s' % (namespace_map[OPENSEARCH_NAMESPACE], DataFields.Total_Results))
        if total_results is not None:
            self.total_results = total_results.text

        environment = element.find(DataFields.Environment)
        if environment is not None:
            self.feeds = []
            for environment in element.findall(DataFields.Environment):
                env = Environment()
                env.fromXml(environment)
                self.feeds.append(env)

    def encode(self, format=DataFormats.JSON):
        """
        Return a string representation of the object encoded in the specified format.
        Override the default inherited implementation so we can add the opensearch
        element.

        NOTE: The txcosm implementation only ever receives environment lists from
        Cosm. It never sends them, hence this method is never really used. It is
        only implemented here to suppport test cases.

        Return a string representation of the object encoded in the specified format
        """
        if format == DataFormats.JSON:
            return json.dumps(self.toDict())

        elif format == DataFormats.XML:
            eeml = etree.Element('eeml')
            #eeml.attrib['xmlns'] = namespace_map[EEML_NAMESPACE]
            eeml.attrib['{%s}xsi' % namespace_map[EEML_NAMESPACE]] = 'http://www.w3.org/2001/XMLSchema-instance'
            eeml.attrib['{%s}opensearch' % namespace_map[EEML_NAMESPACE]] = namespace_map[OPENSEARCH_NAMESPACE]
            eeml.attrib['version'] = '0.5.1'
            eeml.attrib['{%s}schemaLocation' % namespace_map[EEML_NAMESPACE]] = 'http://www.eeml.org/xsd/005'
            total_results = etree.SubElement(eeml, '{%s}%s' % (namespace_map[OPENSEARCH_NAMESPACE], DataFields.Total_Results))
            total_results.text = str(self.total_results)
            startIndex = etree.SubElement(eeml, '{%s}startIndex' % (namespace_map[OPENSEARCH_NAMESPACE]))
            startIndex.text = "0"
            itemsPerPage = etree.SubElement(eeml, '{%s}itemsPerPage' % (namespace_map[OPENSEARCH_NAMESPACE]))
            itemsPerPage.text = "50"
            for feed in self.feeds:
                eeml.append(feed.toXml())
            return etree.tostring(eeml, encoding='utf-8')

        else:
            raise Exception("Don't know how to encode %s using format %s" % (self.__class__.__name__,
                                                                             format))

    def decode(self, data, format=DataFormats.JSON):
        """
        Decode data, in the specified format, into local attributes
        """
        # The EnvironmentList object must specialise the decode method because it
        # needs to obtain data from the eeml header which is stripped off in the
        # inherited implementation.
        #
        if format == DataFormats.JSON:
            inDict = json.loads(data)
            self.fromDict(inDict)

        elif format == DataFormats.XML:
            # parse xml string, rip off the eeml wrapper and process
            # xml elements by handing off to fromXml method. All
            # viewable (feed, datastream, datapoint) XML items come
            # wrapped in the eeml, environment
            element = etree.fromstring(data)
            self.fromXml(element)

        else:
            raise Exception("Don't know how to decode %s using format %s" % (self.__class__.__name__,
                                                                             format))


class Trigger(DataStructure):
    """ Models a Trigger item """

    def __init__(self, **kwargs):
        self._attributes = [DataFields.Threshold_Value,
                            DataFields.User,
                            DataFields.Notified_At,
                            DataFields.Url,
                            DataFields.Trigger_Type,
                            DataFields.Id,
                            DataFields.Environment_Id,
                            DataFields.Stream_Id]
        self.threshold_value = None
        self.user = None
        self.notified_at = None
        self.url = None
        self.trigger_type = None
        self.id = None
        self.environment_id = None
        self.stream_id = None

        # initialise attributes to specified values or None.
        self.fromDict(kwargs)

    def toDict(self):
        """
        Return the data structure object as a dict. This method is used as
        a helper function for JSON serialization/deserialization.
        """
        triggerDict = dict()
        for attribute in self._attributes:
            attribute_value = getattr(self, attribute, None)
            if attribute_value:
                if attribute in [DataFields.Id, DataFields.Environment_Id]:
                    triggerDict[attribute] = attribute_value
                else:
                    triggerDict[attribute] = attribute_value
        return triggerDict

    def fromDict(self, inDict):
        """
        Populate attributes from a dict
        """
        for attribute in self._attributes:
            attribute_value = inDict.get(attribute, None)
            if attribute_value:
                if attribute in [DataFields.Id, DataFields.Environment_Id]:
                    int_value = int(attribute_value)
                    setattr(self, attribute, int_value)
                else:
                    setattr(self, attribute, attribute_value)

    def toXml(self, parent=None):
        """
        Return the object as an xml ElementTree

        @param parent: The parent element
        @type parent: etree.Element

        @return: XML representation of the object
        @rtype: etree.Element
        """
        datastream_trigger = etree.Element(DataFields.Datastream_Trigger)
        id = etree.SubElement(datastream_trigger, DataFields.Id)
        id.attrib['type'] = 'integer'
        id.text = unicode(self.id)

        if self.url:
            url = etree.SubElement(datastream_trigger, DataFields.Url)
            url.text = self.url
        if self.trigger_type:
            trigger_type = etree.SubElement(datastream_trigger, DataFields.Trigger_Type.replace("_", "-"))
            trigger_type.text = self.trigger_type
        if self.threshold_value:
            threshold_value = etree.SubElement(datastream_trigger, DataFields.Threshold_Value.replace("_", "-"))
            threshold_value.attrib['type'] = 'float'
            threshold_value.text = self.threshold_value
        if self.notified_at:
            notified_at = etree.SubElement(datastream_trigger, DataFields.Notified_At.replace("_", "-"))
            notified_at.attrib['type'] = 'datetime'
            notified_at.text = self.notified_at
        if self.user:
            user = etree.SubElement(datastream_trigger, DataFields.User)
            user.text = self.user
        if self.environment_id:
            environment_id = etree.SubElement(datastream_trigger, DataFields.Environment_Id.replace("_", "-"))
            environment_id.attrib['type'] = 'integer'
            environment_id.text = unicode(self.environment_id)
        if self.stream_id:
            stream_id = etree.SubElement(datastream_trigger, DataFields.Stream_Id)
            stream_id.text = self.stream_id

        return datastream_trigger

    def fromXml(self, element):
        """
        Populate attributes from a XML etree

        @param xml: an xml element tree
        @type xml: etree.Element
        """
        datastream_trigger = element.find(DataFields.Datastream_Trigger)
        if datastream_trigger is not None:
            id = datastream_trigger.find(DataFields.Id)
            if id is not None:
                self.id = int(id.text)
            url = datastream_trigger.find(DataFields.Url)
            if url is not None:
                self.url = url.text
            trigger_type = datastream_trigger.find(DataFields.Trigger_Type.replace("_", "-"))
            if trigger_type is not None:
                self.trigger_type = trigger_type.text
            threshhold_value = datastream_trigger.find(DataFields.Threshold_Value.replace("_", "-"))
            if threshhold_value is not None:
                self.threshhold_value = float(threshhold_value.text)
            notified_at = datastream_trigger.find(DataFields.Notified_At.replace("_", "-"))
            if notified_at is not None:
                self.notified_at = notified_at.text
            user = datastream_trigger.find(DataFields.User)
            if user is not None:
                self.user = user.text
            environment_id = datastream_trigger.find(DataFields.Environment_Id.replace("_", "-"))
            if environment_id is not None:
                self.environment_id = int(environment_id.text)
            stream_id = datastream_trigger.find(DataFields.Stream_Id)
            if stream_id is not None:
                self.stream_id = stream_id.text

    def encode(self, format=DataFormats.JSON):
        """
        Return a string representation of the object encoded in the specified format
        """
        if format == DataFormats.JSON:
            return json.dumps(self.toDict())

        elif format == DataFormats.XML:
            # This XML structure is not wrapped in EEML headers
            return etree.tostring(self.toXml(), encoding='utf-8')

        else:
            raise Exception("Don't know how to encode %s using format %s" % (self.__class__.__name__,
                                                                             format))

    def decode(self, data, format=DataFormats.JSON):
        """
        Decode data, in the specified format, into local attributes
        """
        if format == DataFormats.JSON:
            inDict = json.loads(data)
            self.fromDict(inDict)

        elif format == DataFormats.XML:
            # This XML structure is not wrapped in EEML headers
            element = etree.fromstring(data)
            if element is not None:
                self.fromXml(element)

        else:
            raise Exception("Don't know how to decode %s using format %s" % (self.__class__.__name__,
                                                                             format))


class TriggerList(DataStructure):
    """
    Models a Trigger list item

    The json structure of this object is actually a list while all
    the others are a dict. To allow object initialisation using the
    normal **kwargs approach (and to allow decoding) we need to wrap
    the list in a dict. The wrapper dict uses the key DataFields.Datastream_Trigger.
    """

    def __init__(self, **kwargs):
        self.triggers = []

        # initialise attributes to specified values or None.
        self.fromDict(kwargs)

    def toDict(self):
        """
        Return the data structure object as a dict. This method is used as
        a helper function for JSON serialization/deserialization.
        """
        # This object is actually contained in a list
        triggers = []
        for trigger in self.triggers:
            triggers.append(trigger.toDict())
        return triggers

    def fromDict(self, inDict):
        """
        Populate attributes from a dict
        """
        # The json structure of this object is actually a list. To allow
        # this object to be initialised and decoded, the list is wrapped
        # in a dict with a key identical to the XML verison which is
        # DataFields.Datastream_Trigger.
        # This provides a consistent interface (dict/kwargs input).
        # Remove the wrapper dict to access triggers list, but check
        # that it exists first because the object should be initialisable
        # without kwargs present at all.
        #
        triggersList = inDict.get(DataFields.Datastream_Trigger, None)
        if triggersList:
            self.triggers = []
            for triggerDict in triggersList:
                self.triggers.append(Trigger(**triggerDict))

    def toXml(self, parent=None):
        """
        Return the object as an xml ElementTree

        @param parent: The parent element
        @type parent: etree.Element

        @return: XML representation of the object
        @rtype: etree.Element
        """
        datastream_triggers = etree.Element(DataFields.Datastream_Triggers)
        datastream_triggers.attrib['type'] = 'array'
        for trigger in self.triggers:
            datastream_triggers.append(trigger.toXml())

        return datastream_triggers

    def fromXml(self, element):
        """
        Populate attributes from a XML etree

        @param xml: an xml element tree
        @type xml: etree.Element
        """
        datastream_triggers = element.find(DataFields.Datastream_Triggers)
        if datastream_triggers:
            self.triggers = []
            for datastream_trigger in datastream_triggers.findall(DataFields.Datastream_Trigger):
                trigger = Trigger()
                trigger.fromXml(datastream_trigger)
                self.triggers.append(trigger)

    def encode(self, format=DataFormats.JSON):
        """
        Return a string representation of the object encoded in the specified format
        """
        if format == DataFormats.JSON:
            return json.dumps(self.toDict())

        elif format == DataFormats.XML:
            # This XML structure is not wrapped in EEML headers
            return etree.tostring(self.toXml(), encoding='utf-8')

        else:
            raise Exception("Don't know how to encode %s using format %s" % (self.__class__.__name__,
                                                                             format))

    def decode(self, data, format=DataFormats.JSON):
        """
        Decode data, in the specified format, into local attributes
        """
        if format == DataFormats.JSON:
            # The json structure of this object is actually a list.
            # wrap it in a dict for a consistent input to fromDict
            inDict = {DataFields.Datastream_Trigger: json.loads(data)}
            self.fromDict(inDict)

        elif format == DataFormats.XML:
            # This XML structure is not wrapped in EEML headers
            element = etree.fromstring(data)
            if element is not None:
                self.fromXml(element)

        else:
            raise Exception("Don't know how to decode %s using format %s" % (self.__class__.__name__,
                                                                             format))


class Key(DataStructure):
    """ Models a API Key item """

    def __init__(self, **kwargs):
        self._attributes = [DataFields.Api_Key,
                            DataFields.Label,
                            DataFields.Permissions,
                            DataFields.Private_Access]

        self.api_key = None
        self.label = None
        self.permissions = None
        self.private_access = None

        # initialise attributes to specified values or None.
        self.fromDict(kwargs)

    def toDict(self):
        """
        Return the data structure object as a dict. This method is used as
        a helper function for JSON serialization/deserialization.
        """
        keyDict = dict()
        keyAttrsDict = dict()
        for attribute in self._attributes:
            if attribute == DataFields.Permissions:
                permissions_list = list()
                if self.permissions:
                    for permission in self.permissions:
                        permissions_list.append(permission.toDict())
                keyAttrsDict[attribute] = permissions_list
            else:
                attribute_value = getattr(self, attribute, None)
                if attribute_value:
                    keyAttrsDict[attribute] = attribute_value
        keyDict[DataFields.Key] = keyAttrsDict
        return keyDict

    def fromDict(self, inDict):
        """
        Populate attributes from a dict
        """
        keyDict = inDict.get(DataFields.Key, None)

        # There is an inconsistency between viewing a single API key and viewing
        # a list of API keys. The key object returned from a request to view a
        # single key is wrapped in a dict with a key called 'key'. For example:
        #{
        #  "key":{
        #    "api_key":"CeWzga_cNja15kjwSVN5x5Mut46qj5akqKPvFxKIec0",
        #    "label":"sharing key",
        #    "permissions":[
        #      {
        #        "access_methods":["get","put"]
        #      }
        #    ]
        #  }
        #}
        #
        #
        # But each key object returned from a request to view multiple keys is
        # not wrapped in the same structure. For example:
        #{"keys":[
        #  {
        #    "api_key":"CeWzga_cNja15kjwSVN5x5Mut46qj5akqKPvFxKIec0",
        #    "label": "sharing key 1",
        #    "permissions":[
        #      {
        #        "access_methods":["get"],
        #      }
        #    ]
        #  },
        #  {
        #    "api_key":"zR9eEw3WfrSY1-abcdefghasdfaoisdj109usasdf0a9sf",
        #    "label": "sharing key 2",
        #    "permissions":[
        #      {
        #        "access_methods":["put"],
        #        "source_ip":"123.12.123.123"
        #      }
        #    ]
        #  }
        #]}
        #
        # Each item in the keys list is supposed to be a key yet it does not follow
        # the same key definition structure. It is missing the encolsing 'key' dict.
        #
        # This makes it slightly harder to simply pass each key section in a
        # multiple key listing response to the Key initialiser - because it is
        # expecting a normal key structure.
        # So as a workaround to cater for the two different specifications of a
        # key we first attempt to crack the inDict using the expected structure
        # and if that fails we then look into the inDict and check if it contains
        # the expected key attributes.
        #
        if keyDict is None:
            inDictlooksLikeAKeyDict = False
            for attribute in self._attributes:
                if attribute in inDict:
                    inDictlooksLikeAKeyDict = True
            if inDictlooksLikeAKeyDict:
                keyDict = inDict

        if keyDict:
            for attribute in self._attributes:
                attribute_value = keyDict.get(attribute, None)
                if attribute_value:
                    if attribute == DataFields.Permissions:
                        self.permissions = []
                        for permissionDict in attribute_value:
                            self.permissions.append(Permission(**permissionDict))
                    else:
                        setattr(self, attribute, attribute_value)

    def toXml(self, parent=None):
        """
        Return the object as an xml ElementTree

        @param parent: The parent element
        @type parent: etree.Element

        @return: XML representation of the object
        @rtype: etree.Element
        """
        key = etree.Element(DataFields.Key)

        if self.api_key:
            api_key = etree.SubElement(key, DataFields.Api_Key)
            api_key.text = self.api_key
        if self.label:
            label = etree.SubElement(key, DataFields.Label)
            label.text = self.label
        if self.private_access:
            private_access = etree.SubElement(key, DataFields.Private_Access)
            private_access.text = unicode(self.private_access)
        if self.permissions:
            permissions = etree.SubElement(key, DataFields.Permissions)
            for permission in self.permissions:
                permissions.append(permission.toXml())
        return key

    def fromXml(self, element):
        """
        Populate attributes from a XML etree

        @param xml: an xml element tree
        @type xml: etree.Element
        """

        key = element.find(DataFields.Key)
        if key is not None:
            api_key = key.find(DataFields.Api_Key)
            if api_key is not None:
                self.api_key = api_key.text
            label = key.find(DataFields.Label)
            if label is not None:
                self.label = label.text
            private_access = key.find(DataFields.Private_Access)
            if private_access is not None:
                self.private_access = private_access.text == "True"
            permissions = key.find(DataFields.Permissions)
            if permissions is not None:
                permission_elements = permissions.findall(DataFields.Permission)
                if permission_elements:
                    self.permissions = list()
                    for permission_element in permission_elements:
                        permission = Permission()
                        permission.fromXml(permission_element)
                        self.permissions.append(permission)

    def encode(self, format=DataFormats.JSON):
        """
        Return a string representation of the object encoded in the specified format
        """
        if format == DataFormats.JSON:
            return json.dumps(self.toDict())

        elif format == DataFormats.XML:
            # This XML structure is not wrapped in EEML headers
            return etree.tostring(self.toXml(), encoding='utf-8')

        else:
            raise Exception("Don't know how to encode %s using format %s" % (self.__class__.__name__,
                                                                             format))

    def decode(self, data, format=DataFormats.JSON):
        """
        Decode data, in the specified format, into local attributes
        """
        if format == DataFormats.JSON:
            inDict = json.loads(data)
            self.fromDict(inDict)

        elif format == DataFormats.XML:
            # This XML structure is not wrapped in EEML headers
            element = etree.fromstring(data)
            if element is not None:
                self.fromXml(element)

        else:
            raise Exception("Don't know how to decode %s using format %s" % (self.__class__.__name__,
                                                                             format))


class KeyList(DataStructure):
    """ Models a API key list item """

    def __init__(self, **kwargs):

        self.keys = []

        # initialise attributes to specified values or None.
        self.fromDict(kwargs)

    def toDict(self):
        """
        Return the data structure object as a dict. This method is used as
        a helper function for JSON serialization/deserialization.
        """
        keysDict = dict()
        keyList = []
        for key in self.keys:
            keyList.append(key.toDict())
        keysDict[DataFields.Keys] = keyList
        return keysDict

    def fromDict(self, inDict):
        """
        Populate attributes from a dict
        """
        keysList = inDict.get(DataFields.Keys, None)
        if keysList:
            self.keys = []
            for keyDict in keysList:
                key = Key(**keyDict)
                self.keys.append(key)

    def toXml(self, parent=None):
        """
        Return the object as an xml ElementTree

        @param parent: The parent element
        @type parent: etree.Element

        @return: XML representation of the object
        @rtype: etree.Element
        """
        keys = etree.Element(DataFields.Keys)
        for key in self.keys:
            keys.append(key.toXml())

        return keys

    def fromXml(self, element):
        """
        Populate attributes from a XML etree

        @param xml: an xml element tree
        @type xml: etree.Element
        """

        keys = element.find(DataFields.Keys)
        if keys is not None:
            self.keys = []
            for key_element in keys.findall(DataFields.Key):
                key = Key()
                key.fromXml(key_element)
                self.keys.append(key)

    def encode(self, format=DataFormats.JSON):
        """
        Return a string representation of the object encoded in the specified format
        """
        if format == DataFormats.JSON:
            return json.dumps(self.toDict())

        elif format == DataFormats.XML:
            # This XML structure is not wrapped in EEML headers
            return etree.tostring(self.toXml(), encoding='utf-8')

        else:
            raise Exception("Don't know how to encode %s using format %s" % (self.__class__.__name__,
                                                                             format))

    def decode(self, data, format=DataFormats.JSON):
        """
        Decode data, in the specified format, into local attributes
        """
        if format == DataFormats.JSON:
            inDict = json.loads(data)
            self.fromDict(inDict)

        elif format == DataFormats.XML:
            # This XML structure is not wrapped in EEML headers
            element = etree.fromstring(data)
            if element is not None:
                self.fromXml(element)

        else:
            raise Exception("Don't know how to decode %s using format %s" % (self.__class__.__name__,
                                                                             format))


class User(DataStructure):
    """ Models a User item """

    def __init__(self, **kwargs):
        self._attributes = [DataFields.About,
                            DataFields.Api_Key,
                            DataFields.Creatable_Roles,
                            DataFields.Datastreams_Allowed,
                            DataFields.Datastreams_Count,
                            DataFields.Deliver_Email,
                            DataFields.Display_Activity,
                            DataFields.Display_Information,
                            DataFields.Display_Stats,
                            DataFields.Email,
                            DataFields.First_Name,
                            DataFields.Full_Name,
                            DataFields.Last_Name,
                            DataFields.Login,
                            DataFields.Organisation,
                            DataFields.Receive_Forum_Notifications,
                            DataFields.Roles,
                            DataFields.Subscribed_To_Mailings,
                            DataFields.Timezone,
                            DataFields.Total_Api_Access_Count,
                            DataFields.Website]

        self.about = None
        self.api_key = None
        self.creatable_roles = None
        self.datastreams_allowed = None
        self.datastreams_count = None
        self.deliver_email = None
        self.display_activity = None
        self.display_information = None
        self.display_stats = None
        self.email = None
        self.first_name = None
        self.full_name = None
        self.last_name = None
        self.login = None
        self.organisation = None
        self.receive_forum_notifications = None
        self.roles = None
        self.subscribed_to_mailing = None
        self.timezone = None
        self.website = None

        # initialise attributes to specified values or None.
        self.fromDict(kwargs)

    def toDict(self):
        """
        Return the data structure object as a dict. This method is used as
        a helper function for JSON serialization/deserialization.
        """
        userDict = dict()
        for attribute in self._attributes:
            attribute_value = getattr(self, attribute, None)
            if attribute_value:
                userDict[attribute] = attribute_value

        topDict = dict()
        topDict[DataFields.User] = userDict
        return topDict

    def fromDict(self, inDict):
        """
        Populate attributes from a dict
        """
        userDict = inDict.get(DataFields.User, None)
        if userDict:
            for attribute in self._attributes:
                attribute_value = userDict.get(attribute, None)
                if attribute_value:
                    setattr(self, attribute, attribute_value)

    def toXml(self, parent=None):
        """
        Return the object as an xml ElementTree

        @param parent: The parent element
        @type parent: etree.Element

        @return: XML representation of the object
        @rtype: etree.Element
        """
        user = etree.Element(DataFields.User)

        if self.about:
            about = etree.SubElement(user, DataFields.About)
            about.text = self.about
        if self.api_key:
            api_key = etree.SubElement(user, DataFields.Api_Key)
            api_key.text = self.api_key
        if self.creatable_roles:
            creatable_roles = etree.SubElement(user, DataFields.Creatable_Roles)
            for role_text in self.creatable_roles:
                creatable_role = etree.SubElement(creatable_roles, DataFields.Creatable_Role)
                creatable_role.text = role_text
        if self.datastreams_allowed:
            datastreams_allowed = etree.SubElement(user, DataFields.Datastreams_Allowed)
            datastreams_allowed.text = unicode(self.datastreams_allowed)
        if self.datastreams_count:
            datastreams_count = etree.SubElement(user, DataFields.Datastreams_Count)
            datastreams_count.text = unicode(self.datastreams_count)
        if self.deliver_email:
            deliver_email = etree.SubElement(user, DataFields.Deliver_Email)
            deliver_email.text = self.deliver_email
        if self.display_activity:
            display_activity = etree.SubElement(user, DataFields.Display_Activity)
            display_activity.text = self.display_activity
        if self.display_information:
            display_information = etree.SubElement(user, DataFields.Display_Information)
            display_information.text = self.display_information
        if self.display_stats:
            display_stats = etree.SubElement(user, DataFields.Display_Stats)
            display_stats.text = self.display_stats
        if self.email:
            email = etree.SubElement(user, DataFields.Email)
            email.text = self.email
        if self.first_name:
            first_name = etree.SubElement(user, DataFields.First_Name)
            first_name.text = self.first_name
        if self.full_name:
            full_name = etree.SubElement(user, DataFields.Full_Name)
            full_name.text = self.full_name
        if self.about:
            about = etree.SubElement(user, DataFields.About)
            about.text = self.about
        if self.last_name:
            last_name = etree.SubElement(user, DataFields.Last_Name)
            last_name.text = self.last_name
        if self.login:
            login = etree.SubElement(user, DataFields.Login)
            login.text = self.login
        if self.organisation:
            organisation = etree.SubElement(user, DataFields.Organisation)
            organisation.text = self.organisation
        if self.receive_forum_notifications:
            receive_forum_notifications = etree.SubElement(user, DataFields.Receive_Forum_Notifications)
            receive_forum_notifications.text = self.receive_forum_notifications
        if self.roles:
            roles = etree.SubElement(user, DataFields.Roles)
            for role_text in self.roles:
                role = etree.SubElement(roles, DataFields.Role)
                role.text = role_text
        if self.subscribed_to_mailing:
            subscribed_to_mailing = etree.SubElement(user, DataFields.Subscribed_To_Mailings)
            subscribed_to_mailing.text = self.subscribed_to_mailing
        if self.timezone:
            timezone = etree.SubElement(user, DataFields.Timezone)
            timezone.text = self.timezone
        if self.website:
            website = etree.SubElement(user, DataFields.Website)
            website.text = self.website

        return user

    def fromXml(self, element):
        """
        Populate attributes from a XML etree

        @param xml: an xml element tree
        @type xml: etree.Element
        """

        user = element.find(DataFields.User)
        if user is not None:
            about = user.find(DataFields.About)
            if about is not None:
                self.about = about.text
            api_key = user.find(DataFields.Api_Key)
            if api_key is not None:
                self.api_key = api_key.text
            creatable_roles = user.find(DataFields.Creatable_Roles)
            if creatable_roles is not None:
                self.creatable_roles = []
                for creatable_role in creatable_roles.findall(DataFields.Creatable_Role):
                    self.creatable_roles.append(creatable_role.text)
            datastreams_allowed = user.find(DataFields.Datastreams_Allowed)
            if datastreams_allowed is not None:
                self.datastreams_allowed = datastreams_allowed.text
            datastreams_count = user.find(DataFields.Datastreams_Count)
            if datastreams_count is not None:
                self.datastreams_count = datastreams_count.text
            deliver_email = user.find(DataFields.Deliver_Email)
            if deliver_email is not None:
                self.deliver_email = deliver_email.text
            display_activity = user.find(DataFields.Display_Activity)
            if display_activity is not None:
                self.display_activity = display_activity.text
            display_information = user.find(DataFields.Display_Information)
            if display_information is not None:
                self.display_information = display_information.text
            display_stats = user.find(DataFields.Display_Stats)
            if display_stats is not None:
                self.display_stats = display_stats.text
            email = user.find(DataFields.Email)
            if email is not None:
                self.email = email.text
            first_name = user.find(DataFields.First_Name)
            if first_name is not None:
                self.first_name = first_name.text
            full_name = user.find(DataFields.Full_Name)
            if full_name is not None:
                self.full_name = full_name.text
            last_name = user.find(DataFields.Last_Name)
            if last_name is not None:
                self.last_name = last_name.text
            login = user.find(DataFields.Login)
            if login is not None:
                self.login = login.text
            organisation = user.find(DataFields.Organization)
            if organisation is not None:
                self.organisation = organisation.text
            receive_forum_notifications = user.find(DataFields.Receive_Forum_Notifications)
            if receive_forum_notifications is not None:
                self.receive_forum_notifications = receive_forum_notifications.text
            roles = user.find(DataFields.Roles)
            if roles is not None:
                self.roles = []
                for role in roles.findall(DataFields.Role):
                    self.roles.append(role.text)
            subscribed_to_mailing = user.find(DataFields.Subscribed_To_Mailings)
            if subscribed_to_mailing is not None:
                self.subscribed_to_mailing = subscribed_to_mailing.text
            timezone = user.find(DataFields.Timezone)
            if timezone is not None:
                self.timezone = timezone.text
            website = user.find(DataFields.Website)
            if website is not None:
                self.website = website.text

    def encode(self, format=DataFormats.JSON):
        """
        Return a string representation of the object encoded in the specified format
        """
        if format == DataFormats.JSON:
            return json.dumps(self.toDict())

        elif format == DataFormats.XML:
            # This XML structure is not wrapped in EEML headers
            return etree.tostring(self.toXml(), encoding='utf-8')

        else:
            raise Exception("Don't know how to encode %s using format %s" % (self.__class__.__name__,
                                                                             format))

    def decode(self, data, format=DataFormats.JSON):
        """
        Decode data, in the specified format, into local attributes
        """
        if format == DataFormats.JSON:
            inDict = json.loads(data)
            self.fromDict(inDict)

        elif format == DataFormats.XML:
            # This XML structure is not wrapped in EEML headers
            element = etree.fromstring(data)
            if element is not None:
                self.fromXml(element)

        else:
            raise Exception("Don't know how to decode %s using format %s" % (self.__class__.__name__,
                                                                             format))


class UserList(DataStructure):
    """ Models a User list item """

    def __init__(self, **kwargs):

        self.users = []

        # initialise attributes to specified values or None.
        self.fromDict(kwargs)

    def toDict(self):
        """
        Return the data structure object as a dict. This method is used as
        a helper function for JSON serialization/deserialization.
        """
        # this item is actually a list
        usersList = list()
        for user in self.users:
            usersList.append(user.toDict())
        return usersList

    def fromDict(self, inDict):
        """
        Populate attributes from a dict
        """
        # The json structure of this object is actually a list. To allow
        # this object to be initialised and decoded, the list is wrapped
        # in a dict with a key identical to the XML verison which is
        # DataFields.Users.
        # This provides a consistent interface (dict/kwargs input).
        # Remove the wrapper dict to access users list, but check
        # that it exists first because the object should be initialisable
        # without kwargs present at all.
        #
        usersList = inDict.get(DataFields.Users, None)
        if usersList:
            self.users = []
            for userDict in usersList:
                user = User(**userDict)
                self.users.append(user)

    def toXml(self, parent=None):
        """
        Return the object as an xml ElementTree

        @param parent: The parent element
        @type parent: etree.Element

        @return: XML representation of the object
        @rtype: etree.Element
        """
        users = etree.Element(DataFields.Keys)
        users.attrib['type'] = 'array'
        for user in self.users:
            users.append(user.toXml())
        return users

    def fromXml(self, element):
        """
        Populate attributes from a XML etree

        @param xml: an xml element tree
        @type xml: etree.Element
        """

        users = element.find(DataFields.Users)
        if users is not None:
            self.users = []
            for user_element in users.findall(DataFields.User):
                user = User()
                user.fromXml(user_element)
                self.users.append(user)

    def encode(self, format=DataFormats.JSON):
        """
        Return a string representation of the object encoded in the specified format
        """
        if format == DataFormats.JSON:
            return json.dumps(self.toDict())

        elif format == DataFormats.XML:
            # This XML structure is not wrapped in EEML headers
            return etree.tostring(self.toXml(), encoding='utf-8')

        else:
            raise Exception("Don't know how to encode %s using format %s" % (self.__class__.__name__,
                                                                             format))

    def decode(self, data, format=DataFormats.JSON):
        """
        Decode data, in the specified format, into local attributes
        """
        if format == DataFormats.JSON:
            # The json structure of this object is actually a list.
            # wrap it in a dict for a consistent input to fromDict
            inDict = {DataFields.Users: json.loads(data)}
            self.fromDict(inDict)

        elif format == DataFormats.XML:
            # This XML structure is not wrapped in EEML headers
            element = etree.fromstring(data)
            if element is not None:
                self.fromXml(element)

        else:
            raise Exception("Don't know how to decode %s using format %s" % (self.__class__.__name__,
                                                                             format))


# Define a mapping of data structure label to object that
# can be used to resolve the appropriate data structure
# to create when parsing response data from Cosm.
List_Feeds_Msg = 'feeds_list'
View_Feed_Msg = 'feed'
View_Datastream_Msg = 'datastream'
View_Datapoint_Msg = 'datapoint'
List_Keys_Msg = 'keys_list'
View_Key_Msg = 'key'
List_Triggers_Msg = 'triggers_list'
View_Trigger_Msg = 'trigger'
List_Users_Msg = 'users_list'
View_User_Msg = 'user'
StructuresMap = {List_Feeds_Msg: EnvironmentList,
                 View_Feed_Msg: Environment,
                 View_Datastream_Msg: Datastream,
                 View_Datapoint_Msg: Datapoint,
                 List_Keys_Msg: KeyList,
                 View_Key_Msg: Key,
                 List_Triggers_Msg: TriggerList,
                 View_Trigger_Msg: Trigger,
                 List_Users_Msg: UserList,
                 View_User_Msg: User}


def getDataStructure(msg_kind):
    if msg_kind not in StructuresMap:
        err_str = "Invalid structure \'%s\', can't convert" % msg_kind
        logging.error(err_str)
        raise Exception(err_str)
    return StructuresMap[msg_kind]
