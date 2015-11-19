{"stat" :
    {
        "description" : "Program to stat the alien format.  If not defined, ipipe will be used to load the geometry",
        "type" : [ "string", "object" ],
        "optional" : true,
        "properties" :
        {
            "command" : { "type":"string", "optional":false },
            "format" : { "type":"string", "optional":true },
            "binary" : { "type":"boolean", "optional":true },
            "expand" : { "type":"boolean", "optional":true }
        }
    }
}