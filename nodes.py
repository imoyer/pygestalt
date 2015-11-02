#   pyGestalt Nodes Module

"""A standard set of base node classes."""


#---- INCLUDES ----
import threading
from pygestalt import core, packets


class baseVirtualNode(object):
    """Base class for all virtual nodes"""
    
    def __init__(self, *args, **kwargs):
        """Initializer for all virtual nodes.
        
        Because of the indirect way in which nodes are loaded, the arguments passed to the node
        on instantiation are stored by this routine, and then passed to additional initialization
        functions (_init_ for gestalt nodes) later after the node has been set into the node shell.
        """
        self._initArgs_ = args
        self._initKwargs_ = kwargs

    def _recursiveInit_(self, _recursionDepth_, *args, **kwargs):
        """Dummy initializer function."""
        pass

class baseGestaltNode(baseVirtualNode):
    """Base class for Gestalt nodes."""
    
    def _recursiveInit_(self, recursionDepth, *args, **kwargs):
        """Recursively initializes Gestalt node.
        
        THIS FUNCTION IS ONLY CALLED INTERNALLY BY _init_
        Initialization occurs in the following steps:
        1) parent class initialization: a call to parentClass._recursiveInit_
        2) init: user initialization routine for defining optional constants etc. that are specific to the node
        3) packets: packet templates are defined here
        4) ports: actionObjects and packets are bound to ports
        5) onLoad: anything that needs to get initialized with the ability to communicate to the node.
        """
        baseClass = self.__class__.mro()[recursionDepth] #base class is determined by the method resolution order indexed by the recursion depth.
        parentClass = self.__class__.mro()[recursionDepth + 1] #parent class is determined the same way
        parentClass._recursiveInit_(self, recursionDepth + 1, *args, **kwargs) #recursively initialize using parent class
        if 'init' in baseClass.__dict__: baseClass.init(self, *args, **kwargs) #run user initialization routine with provided arguments
        if 'initPackets' in baseClass.__dict__: baseClass.initPackets(self) #initialize packets
        if 'initPorts' in baseClass.__dict__: baseClass.initPorts(self) #initialize ports
        if 'onLoad' in baseClass.__dict__: baseClass.onLoad(self) #run after initialization is complete
        
    def _init_(self):
        """Initializes Gestalt Node.
        
        Initialization occurs by calling a sequence of specialized initialization functions. In order to
        support inheritance, and to make sure that all of the inherited functions are called, the parent
        class initialization functions must be called recursively. This function is the entry point into
        the process and starts at a recursion depth of 0.
        
        Note that _initArgs_ and _initKwargs_ are the arguments provided to the virtual node when it was
        first instantiated. They are stored by the baseVirtualNode.
        """
        self._outboundPortTable_ = {}   #stores function:port pairs as assigned by bindPort
        self._inboundPortTable_ = {} #stores port:function pairs as assigned by bindPort
        
        self._recursiveInit_(0, *self._initArgs_, **self._initKwargs_) #begin recursive initialization at a depth of 0.
    
    def init(self, *args, **kwargs):
        """User initialization routine for defining optional constants etc. that are specific to the node hardware.
        
        Examples of this might be the crystal frequency, or an ADC reference voltage.
        """
        pass
    
    def initPackets(self):
        """Initializes packet templates."""
        pass
    
    def initPorts(self):
        """Bind actionObjects and packets to ports."""
        pass
    
    def onLoad(self):
        """Run any initialization functions that must communicate with the physical node.
        
        An example might be setting some default parameters on the node.
        """
        pass
    
    def bindPort(self, port, outboundFunction = None, outboundTemplate = None, inboundFunction = None, inboundTemplate = None ):
        """Attaches actionObject classes and templates to a communication port, and initializes relevant parameters.
        
        port -- a port number ranging from 1 to 254
        outboundFunction -- an actionObject class that will transmit on the specified port
        outboundTemplate -- the packet template that should be used to encode any packets sent on the specified port
        inboundFunction -- an actionObject class taht will receive on the specified port
        inboundTemplate -- the packet template that should be used to decode any packets sent on the specified port
        
        If either inbound or outbound functions are not provided, these will be automatically generated.
        
        Note that the parameter names contain the reference "function" strictly for the benefit of the user, since in practice they behave like functions.
        """
        
        inboundPacketFlag = threading.Event()    #This flag will be used to signal to an outbound function that a reply has been received.
        
        #GENERATE actionObject CLASSES
        if outboundFunction != None:    #an outbound function has been provided
            outboundActionObjectClass = self.addDerivedType(outboundFunction)   #this is the class that will actually get called to instantiate action objects
                                                                                #during use. It is a derived class of the provided outboundFunction class. 
            outboundActionObjectClass._baseActionObject_ = outboundFunction            #store the base class for introspection use later
        else: #no outbound function has been provided, must generate one.
            typeName = "outboundActionObjectOnPort"+ str(port)    #make up a name that is unique
            outboundActionObjectClass = self.addDerivedType(core.genericOutboundActionObjectBlockOnReply, typeName)
            outboundActionObjectClass._baseActionObject_ = core.genericOutboundActionObjectBlockOnReply
        
        if inboundFunction != None: #an inbound function has been provided
            inboundActionObjectClass = self.addDerivedType(inboundFunction)
            inboundActionObjectClass._baseActionObject_ = inboundFunction
        else: #no inbound function has been provided, must generate one
            typeName = "inboundActionObjectOnPort" + str(port)    #make up a name that is unique
            inboundActionObjectClass = self.addDerivedType(core.genericInboundActionObject, typeName)
            inboundActionObjectClass._baseActionObject_ = inboundFunction
        
        #GENERATE MISSING PACKET TEMPLATES
        if outboundTemplate == None:
            templateName = 'outboundTemplateOnPort' + str(port)
            outboundTemplate = packets.emptyTemplate(templateName)  #must use an emptyTemplate type because template cannot have an empty list of tokens
        
        if inboundTemplate == None:
            templateName = 'inboundTemplateOnPort' + str(port)
            inboundTemplate = packets.emptyTemplate(templateName)
        
        #STORE PARAMETERS IN actionObject CLASSES
        outboundActionObjectClass._port_ = port #store port number
        inboundActionObjectClass._port_ = port
        
        outboundActionObjectClass._inboundPacketFlag_ = inboundPacketFlag #store inbound packet flag
        inboundActionObjectClass._inboundPacketFlag_ = inboundPacketFlag
        
        outboundActionObjectClass._outboundTemplate_ = outboundTemplate #store outbound packet template
        inboundActionObjectClass._outboundTemplate_ = outboundTemplate
        
        outboundActionObjectClass._inboundTemplate_ = inboundTemplate #store inbound packet template
        inboundActionObjectClass._inboundTemplate_ = inboundTemplate
        
        #UPDATE VIRUAL NODE PORT DICTIONARIES
        self._outboundPortTable_.update({outboundActionObjectClass:port})
        self._inboundPortTable_.update({port:inboundActionObjectClass})
    
    def addDerivedType(self, baseClass, name = None):
        """Creates a new type using baseClass as the base, and adds the baseClass entry in self.__dict__.
        
        baseClass -- the parent class from which to make a derived type.
        name -- if provided, this is the name that should be assigned to the class. If not provided,
                the baseClass __name__ will be used instead.
        
        This is an ugly thing to do, but is necessary because of the way Gestalt should work. The user
        can define actionObject classes in the virtual node. When a call gets made to the class, an
        instance of the actionObject is created. So during initialization, parameters such as which port
        the actionObject class is bound to must be set as class parameters, not instance parameters. All
        well and good except that when subclassing virtual nodes, all of the actionObject classes are not
        copied but just referenced. So there would be a conflict between all virtual nodes that share common
        actionObjects. This function solves the issue by creating a new derived actionObject class and inserting 
        it into the dict of the virtualNode instance.
        
        Note that because the entry happens at the instance level, the original actionObject class can still be accessed
        in the base virtualNode class.
        """
        if name != None:    #use provided name
            typeName = name
        else:   #reuse name of base class
            typeName = baseClass.__name__
            
        newType = type(typeName,(baseClass,) ,{}) #create new type
        self.__dict__.update({typeName:newType})
        return newType
    
class gestaltNode(baseGestaltNode):
    """The standard Gestalt node class.
    
    This class defines the standard functionality that any gestalt node must exhibit, including:
    - provisions for acquiring the node on a network
    - setting the node address
    - coming out of bootloader mode (if applicable)
    
    The key distinction between gestaltNode and baseGestaltNode is that gestaltNode is written
    exactly the same way that a user of the library would write their own virtual nodes. All of the hidden
    functionality is captured in baseGestaltNode. The intention is that this class gets subclassed by all
    Gestalt virtual nodes.
    """
    def init(self):
        """Initialiation routine for gestalt node."""
        self.bootPageSize = 128     #bootloader page size in bytes
    
    def initPackets(self):
        """Define packet templates."""
        
        #Node Status
        self.statusResponsePacket = packets.template('statusResponse',
                                                     packets.pString('status', 1),  #status is encoded as 'b' for bootloader, and 'a' for application
                                                     packets.unsignedInt('appValidity', 1)) #application validity byte, gets set to 170 if valid
        
        #Bootloader Command
        self.bootCommandRequestPacket = packets.template('bootCommandRequest',
                                                         packets.unsignedInt('commandCode', 1))
        
        self.bootCommandResponsePacket = packets.template('bootCommandResponse',
                                                          packets.unsignedInt('responseCode', 1),
                                                          packets.unsignedInt('pageNumber', 2))
        #Bootloader Write
        self.bootWriteRequestPacket = packets.template('bootWriteRequest',
                                                       packets.unsignedInt('commandCode', 1),
                                                       packets.unsignedInt('pageNumber', 2),
                                                       packets.pList('writeData', self.bootPageSize))
        
        self.bootWriteResponsePacket = packets.template('bootWriteResponse',
                                                        packets.unsignedInt('responseCode', 1),
                                                        packets.unsignedInt('pageNumber', 2))
        #Bootloader Read
        self.bootReadRequestPacket = packets.template('bootReadRequest',
                                                      packets.unsignedInt('pageNumber',2))
        
        self.bootReadResponsePacket = packets.template('bootReadResponse',
                                                       packets.pList('readData', self.bootPageSize))
        
        #Request URL
        self.urlResponsePacket = packets.template('urlResponse',
                                                  packets.pString('URL'))
        
        #Set Address
        self.setAddressRequestPacket = packets.template('setAddressRequest',
                                                   packets.pList('setAddress', 2))
        
        self.setAddressResponsePacket = packets.template('setAddressResponse',
                                                    packets.pString('URL'))
        
    def initPorts(self):
        """Bind ports to functions and packet templates."""
        
        #Node Status
        self.bindPort(port = 1, outboundFunction = self.statusRequest, inboundTemplate = self.statusResponsePacket)
        
        #Bootloader Command
        self.bindPort(port = 2, outboundFunction = self.bootCommandRequest, outboundTemplate = self.bootCommandRequestPacket,
                      inboundTemplate = self.bootCommandResponsePacket)
        
        #Bootloader Write
        self.bindPort(port = 3, outboundFunction = self.bootWriteRequest, outboundTemplate = self.bootWriteRequestPacket,
                      inboundTemplate = self.bootWriteResponsePacket)
        
        #Bootloader Read
        self.bindPort(port = 4, outboundFunction = self.bootReadRequest, outboundTemplate = self.bootReadRequestPacket,
                      inboundTemplate = self.bootReadResponsePacket)
        
        #URL Request
        self.bindPort(port = 5, outboundFunction = self.urlRequest, inboundTemplate = self.urlResponsePacket)
        
        #Set Address
        self.bindPort(port = 6, outboundFunction = self.setAddressRequest, outboundTemplate = self.setAddressRequestPacket,
                      inboundTemplate = self.setAddressResponsePacket)
        
        #Identify Node
        self.bindPort(port = 7, outboundFunction = self.identifyRequest)
        
        #Reset Node
        self.bindPort(port = 255, outboundFunction = self.resetRequest)
        
        
    