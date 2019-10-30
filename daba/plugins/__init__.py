#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os,sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))
from collections import defaultdict
from daba.orthography import Syllabify

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


class TonesConverter(object):
    def __init__(self, word, debug=False):
        self.debug = debug
        self.toreplace = defaultdict(list)
        self.invalid = False
        self.word = word

    def syllabify(self):
        try:
            self.syllabic = Syllabify(self.word)
            return True
        except (ValueError) as e:
            if self.debug:
                print(str(e).encode('utf-8'))
            self.invalid = True
            return False

    def convert(self):
        if self.invalid:
            return [self.word]
        else:
            for j, tones in self.toreplace.items():
                if all(tones[0] == tone for tone in tones):
                    self.syllabic.set_tone(j, tones[0])
                else:
                    if self.debug:
                        print('Conflicting conversion rules:', u' '.join([self.word, self.syllabic.base(j), u' '.join(tones)]).encode('utf-8'))

            if self.toreplace:
                if self.debug:
                    print(u' '.join([self.word, '->', self.syllabic.form()]).encode('utf-8'))
                return [self.syllabic.form()]
            else:
                return [self.word]

