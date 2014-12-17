import plistlib, sys, os, inspect

class ExObjectSchema(dict):
    def __init__(self):
        # General:
        self['name'] =''
        self['time_stamp'] = 0
        self['type'] = 'camera'
        self['user'] = ''
        self['group'] = []
        self['ref'] =[]
        self['asset_type'] = ''
        self['asset_name'] = ''
        self['locked'] = False
        self['tags'] = []
        self['comments'] = []
        self['status'] = 'active'
        self['version'] = 0
        self['doc'] = 'This is an empy doc string.'

        #Debug:
        self['host_name'] = ''
        self['host_version'] =''
        self['schema_version'] = 0.1

        # Transformation:
        self['xform'] = [(1.0,0.0,0.0,0.0, 0.0,1.0,0.0,0.0, 0.0,0.0,1.0,0.0, 0.0,0.0,0.0,1.0)]
        self['scene_path'] = '/obj'
        self['parent'] = []


class Camera(ExObjectSchema):
    def __init__(self):
        super(Camera, self).__init__()

        # Camera specific:
        self['focal'] = [50.0]
        self['fov'] = [45.0]
        self['haperture'] = [41.4214]
        self['vaperture'] = [0.0]
        self['resx'] = [1280]
        self['resy'] = [720]
        self['pixelAspect'] = [1.0]
        self['renderCam'] = True
        self['focus']   = [5.0]
        self['fstop']   = [5.6]
        self['shutter'] = [0.5]
        self['far']     = [1000.0]
        self['near']    = [0.01]
        self['cropl'] = [0.0]
        self['cropr'] = [1.0]
        self['cropt'] = [1.0]
        self['cropb'] = [0.0]
        self['start_frame'] = 1
        self['end_frame']   = 100
        self['fps']         = 25
        self['background'] = ''



class Asset(ExObjectSchema):
    def __init__(self):
        super(Asset, self).__init__()

        # Specific:
        self['geometries'] = []
        self['material']   = []


class Geometry(ExObjectSchema):
    def __init__(self):
        super(Geometry, self).__init__()

        # Specific:
        self['cache_files'] = {'high':'', 
                               'low' :'', 
                               'proxy':''}

        self['bounds']      = [[1.0,1.0,1.0], 
                               [-1.0,-1.0,-1.0]]

        self['material']    = {'all':''}



class Material(ExObjectSchema):
    def __init__(self):
        super(Material, self).__init__()

        # Textures:
        self['diffuse_texture']      = ''
        self['reflection_texture']   = ''
        self['reflection2_texture']  = ''
        self['sss_texture']          = ''
        self['refraction_texture']   = ''

        # Paramaters:
        self['diffuse']   = [(1.0, 1.0, 1.0)]
        self['diffuse_routhness'] = [0.5]
        self['specular']  = [(1.0, 1.0, 1.0)]
        self['specular2'] = [(1.0, 1.0, 1.0)]
        self['sss']       = [(1.0, 1.0, 1.0)]
        self['refraction']= [(1.0, 1.0, 1.0)]
        



class Locator(ExObjectSchema):
      def __init__(self):
        super(Locator, self).__init__()
        self['lookat'] = []
        self['upvector'] = [0.0, 0.0, 0.0]




def main():

    # Iterate over global name-space to find all children of ExObjectSchema
    # and save creators into files as *.plist xml schemas.
    for item in globals():
        cls = globals()[item]
        if hasattr(cls, '__bases__'):
            if ExObjectSchema in cls.__bases__:
                path = '/STUDIO/studio-packages/ha/exchange/config/%s.xml' % item
                with open(path , 'wb') as fp:
                    print "Creatnig %s from %s" % (path, cls)
                    plistlib.writePlist(cls(), fp)
     






if __name__ == '__main__': main()