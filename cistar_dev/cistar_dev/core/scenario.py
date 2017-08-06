import logging
from collections import OrderedDict

from rllab.core.serializable import Serializable

from cistar_dev.core.generator import Generator
from cistar_dev.controllers.rlcontroller import RLController

# TODO(cathywu) Make this an abstract class

class Scenario(Serializable):
    def __init__(self, name, type_params, net_params, cfg_params=None,
                 initial_config=None, cfg=None, generator_class=None):
        """
        Abstract base class. Initializes a new scenario. This class can be
        instantiated once and reused in multiple experiments. Note that this
        function stores all the relevant parameters. The generate() function
        still needs to be called separately.

        :param name: A tag associated with the scenario
        :param vehicle_params: See README.md
        :param net_params: See README.md
        :param cfg_params: See README.md
        :param initial_config:
            { 'shuffle' : True }: Shuffle the starting positions of vehicles.
            { 'positions' : [(route0, pos0), (route1, pos1), ... ]}: Places
            vehicles on route route0, position on edge (pos0).
            Note: this needs to be implemented in a child class.
        :param cfg: Path to .sumo.cfg file (which will include path to the
        output files)
        :param generator_class: Class for generating a configuration files
        and net files with placed vehicles, e.g. CircleGenerator
        """
        Serializable.quick_init(self, locals())

        self.name = name
        self.type_params = type_params

        # these numbers are not always static; better to get them from id list in the env class
        self.num_vehicles = sum([x[1][0] for x in type_params.items()])
        self.num_rl_vehicles = sum([x[1][0] for x in type_params.items() if x[1][1][0] == RLController])

        if not net_params:
            ValueError("No network params specified!")
        self.net_params = net_params

        if cfg:
            self.cfg = cfg
        elif not cfg:
            if not generator_class:
                ValueError("Must supply either a CFG or a simulator!!")
            self.generator_class = generator_class
            if cfg_params is None:
                ValueError("No config params specified")
            self.cfg_params = cfg_params

        self.initial_config = {}
        if initial_config:
            self.initial_config = initial_config

    def generate(self):
        """
        Applies self.generator_class to create a net and corresponding cfg
        files, including placement of vehicles (name.rou.xml).
        :return: (path to cfg files (the .sumo.cfg), path to output files {
        "netstate", "amitran", "lanechange", "emission" })
        """
        logging.info("Config file not defined, generating using generator")

        # Default scenario parameters
        net_path = Generator.NET_PATH
        cfg_path = Generator.CFG_PATH

        if "net_path" in self.net_params:
            net_path = self.net_params["net_path"]
        if "cfg_path" in self.cfg_params:
            cfg_path = self.cfg_params["cfg_path"]

        self.generator = self.generator_class(net_path, cfg_path, self.name)
        self.generator.generate_net(self.net_params)
        cfg_name = self.generator.generate_cfg(self.cfg_params)
        # Note that self (the whole scenario instance) is passed on here,
        # so this is where self.type_params (for instance) is used.
        self.generator.make_routes(self, self.initial_config, self.cfg_params)

        return self.generator.cfg_path + cfg_name

    def __str__(self):
        # TODO(cathywu) return the parameters too.
        return "Scenario " + self.name + " with " + str(self.num_vehicles) + " vehicles."