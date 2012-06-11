#!/usr/bin/python
# -*- coding: utf8 -*-

class PluginMount(type):
    def __init__(cls, name, bases, attrs):
        if not hasattr(cls, 'plugins'):
            # This branch only executes when processing the mount point itself.
            # So, since this is a new plugin type, not an implementation, this
            # class shouldn't be registered as a plugin. Instead, it sets up a
            # list where plugins can be registered later.
            cls.plugins = []
        else:
            # This must be a plugin implementation, which should be registered.
            # Simply appending it to the list is all that's needed to keep
            # track of it later.
            cls.plugins.append(cls)

    def get_plugins(self):
        plugin_dict = {}
        for p in self.plugins:
            obj = p()
            plugin_dict[obj.title] = obj
        return plugin_dict


class OrthographyConverter(object):
    """
    Mount point for orthography conversion plugins.

    Plugins implementing this reference should provide the following interface:

    @title  Title to be displayed
    @desc   Text describing converter

    @convert    Main conversion method. Takes single token as input, returns
    list of possible conversions
    """
    __metaclass__ = PluginMount



