import sys
import os
import flow.config as config

SITEPACKAGES = os.path.join(config.AIMSUN_SITEPACKAGES,
                            "lib/python2.7/site-packages")
sys.path.append(SITEPACKAGES)

sys.path.append(os.path.join(config.AIMSUN_NEXT_PATH,
                             'programming/Aimsun Next API/AAPIPython/Micro'))

from flow.core.params import InFlows
from copy import deepcopy
import argparse
import json
import numpy as np


# Load an empty template
gui = GKGUISystem.getGUISystem().getActiveGui()
gui.newDoc(os.path.join(config.PROJECT_PATH,
                        "flow/utils/aimsun/Aimsun_Flow.ang"),
           "EPSG:32601")
model = gui.getActiveModel()


def create_parser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='FIXME',
        epilog='FIXME')

    # required input parameters
    parser.add_argument(
        'filename', type=str, help='Directory containing nodes and edges')
    return parser


def generate_net(nodes, edges, connections, inflows, veh_types):
    inflows = inflows.get()
    lane_width = 3.6  # TODO additional params??
    type_section = model.getType("GKSection")
    type_node = model.getType("GKNode")
    type_turn = model.getType("GKTurning")
    type_traffic_state = model.getType("GKTrafficState")
    type_vehicle = model.getType("GKVehicle")
    type_demand = model.getType("GKTrafficDemand")

    # draw edges
    for edge in edges:
        points = GKPoints()
        if "shape" in edge:
            for p in edge["shape"]: #TODO add x, y offset (radius)
                new_point = GKPoint()
                new_point.set(p[0], p[1], 0)
                points.append(new_point)

            cmd = model.createNewCmd(model.getType("GKSection"))
            cmd.setPoints(edge["numLanes"], lane_width, points)
            model.getCommander().addCommand(cmd)
            section = cmd.createdObject()
            section.setName(edge["id"])
            edge_aimsun = model.getCatalog().findByName(
                edge["id"], type_section)
            edge_aimsun.setSpeed(edge["speed"])
        else:
            first_node, last_node = get_edge_nodes(edge, nodes)
            theta = get_edge_angle(first_node, last_node)
            first_node_offset = [0, 0]  # x, and y offset
            last_node_offset = [0, 0] # x, and y offset

            # offset edge ends if there is a radius in the node
            if "radius" in first_node:
                first_node_offset[0] = first_node["radius"] * \
                                       np.cos(theta*np.pi/180)
                first_node_offset[1] = first_node["radius"] * \
                                       np.sin(theta*np.pi/180)
            if "radius" in last_node:
                last_node_offset[0] = - last_node["radius"] * \
                                      np.cos(theta*np.pi/180)
                last_node_offset[1] = - last_node["radius"] * \
                                      np.sin(theta*np.pi/180)

            # offset edge ends if there are multiple edges between nodes
            # find the edges that share the first node
            edges_shared_node = [edg for edg in edges
                                 if first_node["id"] == edg["to"]
                                 or last_node["id"] == edg["from"]]
            for new_edge in edges_shared_node:
                new_first_node, new_last_node = get_edge_nodes(new_edge, nodes)
                new_theta = get_edge_angle(new_first_node, new_last_node)
                if new_theta == theta - 180 or new_theta == theta + 180:
                    first_node_offset[0] += lane_width * 0.5 *\
                                          np.sin(theta * np.pi / 180)
                    first_node_offset[1] -= lane_width * 0.5 * \
                                          np.cos(theta * np.pi / 180)
                    last_node_offset[0] += lane_width * 0.5 *\
                                          np.sin(theta * np.pi / 180)
                    last_node_offset[1] -= lane_width * 0.5 *\
                                          np.cos(theta * np.pi / 180)
                    break

            new_point = GKPoint()
            new_point.set(first_node['x'] + first_node_offset[0],
                          first_node['y'] + first_node_offset[1],
                          0)
            points.append(new_point)
            new_point = GKPoint()
            end_node = next(node for node in nodes if node["id"] == edge["to"])
            new_point.set(last_node['x'] + last_node_offset[0],
                          last_node['y'] + last_node_offset[1],
                          0)
            points.append(new_point)
            cmd = model.createNewCmd(type_section)
            cmd.setPoints(edge["numLanes"], lane_width, points)
            model.getCommander().addCommand(cmd)
            section = cmd.createdObject()
            section.setName(edge["id"])
            edge_aimsun = model.getCatalog().findByName(
                edge["id"], type_section)
            edge_aimsun.setSpeed(edge["speed"])

    # draw nodes and connections
    for node in nodes:
        # add a new node in Aimsun
        node_pos = GKPoint()
        node_pos.set(node['x'], node['y'], 0)
        cmd = model.createNewCmd(type_node)
        cmd.setPosition(node_pos)
        model.getCommander().addCommand(cmd)
        new_node = cmd.createdObject()
        new_node.setName(node["id"])
        node_aimsun = model.getCatalog().findByName(
            node["id"], type_node)
        # # list of edges from and to the node
        from_edges = [
            edge['id'] for edge in edges if edge['from'] == node['id']]
        to_edges = [edge['id'] for edge in edges if edge['to'] == node['id']]

        #if the node is a junction with a list of connections
        if len(to_edges) > 1 and len(from_edges) > 1 \
                and connections[node['id']] is not None:
            # add connections
            for connection in connections[node['id']]:
                print (connection)
                cmd = model.createNewCmd(type_turn)
                from_section = model.getCatalog().findByName(
                    connection["from"], type_section, True)
                to_section = model.getCatalog().findByName(
                    connection["to"], type_section, True)
                cmd.setTurning(from_section, to_section)
                model.getCommander().addCommand(cmd)
                turn = cmd.createdObject()
                turn_name = "{}_to_{}".format(connection["from"],
                                              connection["to"])
                turn.setName(turn_name)
                existing_node = turn.getNode()
                if existing_node is not None:
                    existing_node.removeTurning(turn)
                # add the turning to the node
                new_node.addTurning(turn, False, True)

        # if the node is not a junction or connections is None
        else:
            for i in range(len(from_edges)):
                for j in range(len(to_edges)):
                    cmd = model.createNewCmd(type_turn)
                    to_section = model.getCatalog().findByName(
                        from_edges[i], type_section, True)
                    from_section = model.getCatalog().findByName(
                        to_edges[j], type_section, True)
                    cmd.setTurning(from_section, to_section)
                    model.getCommander().addCommand(cmd)
                    turn = cmd.createdObject()
                    turn_name = "{}_to_{}".format(from_edges[i], to_edges[j])
                    turn.setName(turn_name)
                    existing_node = turn.getNode()
                    if existing_node is not None:
                        existing_node.removeTurning(turn)

                    # add the turning to the node
                    new_node.addTurning(turn, False, True)

    # get the control plan
    control_plan = model.getCatalog().findByName(
            "Control Plan", model.getType("GKControlPlan"))

    # add traffic lights
    # determine junctions
    junctions = get_junctions(nodes)
    # add meters for all nodes in junctions
    for node in junctions:
        node = model.getCatalog().findByName(
            node['id'], model.getType("GKNode"))
        meters = create_node_meters(model, control_plan, node)


    # set vehicle types
    vehicles = model.getCatalog().getObjectsByType(type_vehicle)
    if vehicles is not None:
        for vehicle in vehicles.itervalues():
            name = vehicle.getName()
            if name == "Car":
                for veh_type in veh_types:
                    cmd = GKObjectDuplicateCmd()
                    cmd.init(vehicle)
                    model.getCommander().addCommand(cmd)
                    new_veh = cmd.createdObject()
                    new_veh.setName(veh_type["veh_id"])

    # Create new states based on vehicle types
    for veh_type in veh_types:
        new_state = create_state(model, veh_type["veh_id"])
        # find vehicle type
        veh_type = model.getCatalog().findByName(
            veh_type["veh_id"], model.getType("GKVehicle"))
        # set state vehicles
        new_state.setVehicle(veh_type)
        #set_state_vehicle(model, new_state, veh_type["veh_id"])
        # set_state_vehicle(model, veh_type["veh_id"], veh_type["veh_id"])

    # add traffic inflows to traffic states
    for inflow in inflows:
        traffic_state_aimsun = model.getCatalog().findByName(
            inflow["vtype"], type_traffic_state)
        edge_aimsun = model.getCatalog().findByName(
            inflow['edge'], type_section)
        traffic_state_aimsun.setEntranceFlow(
            edge_aimsun, None, inflow['vehsPerHour'])

    # set traffic demand
    for veh_type in veh_types:
        # find the state for each vehicle type
        state_car = model.getCatalog().findByName(
            veh_type["veh_id"], type_traffic_state)
        demand = model.getCatalog().findByName(
            "Traffic Demand 864", type_demand)
        if demand is not None and demand.isA("GKTrafficDemand"):
            # clear the demand of any previous item
            demand.removeSchedule()
            # Add the state
            if state_car != None and state_car.isA("GKTrafficState"):
                set_demand_item(model, demand, state_car)
            model.getCommander().addCommand(None)
        else:
            create_traffic_demand(model, veh_type["veh_id"])  # TODO debug

    # set the view to "whole world" in Aimsun
    view = gui.getActiveViewWindow().getView()
    if view is not None:
        view.wholeWorld()

    # set view mode, each vehicle type with different color
    set_vehicles_color(model)

    # save
    gui.saveAs('flow.ang')


def get_junctions(nodes):
    junctions = []  # TODO check
    for node in nodes:
        if "type" in node:
            if node["type"] == "traffic_light":
                junctions.append(node)
    return junctions


# get first and last nodes of an edge
def get_edge_nodes(edge, nodes):
    first_node = next(node for node in nodes
                      if node["id"] == edge["from"])
    last_node = next(node for node in nodes
                     if node["id"] == edge["to"])
    return first_node, last_node


# compute the edge angle
def get_edge_angle(first_node, last_node):
    del_x = np.array([last_node['x'] - first_node['x']])
    del_y = np.array([last_node['y'] - first_node['y']])
    theta = np.arctan2(del_y, del_x) * 180 / np.pi
    return theta


def get_state_folder(model):
    folder_name = "GKModel::trafficStates"
    folder = model.getCreateRootFolder().findFolder(folder_name)
    if folder == None:
        folder = GKSystem.getSystem().createFolder(
            model.getCreateRootFolder(), folder_name)
    return folder


def create_state(model, name):
    state = GKSystem.getSystem().newObject("GKTrafficState", model)
    state.setName(name)
    folder = get_state_folder(model)
    folder.append(state)
    return state


def get_demand_folder(model):
    folder_name = "GKModel::trafficDemands"
    folder = model.getCreateRootFolder().findFolder(folder_name)
    if folder == None:
        folder = GKSystem.getSystem().createFolder(
            model.getCreateRootFolder(), folder_name)
    return folder


def create_traffic_demand(model, name):
    demand = GKSystem.getSystem().newObject("GKTrafficDemand", model)
    demand.setName(name)
    folder = get_demand_folder(model)
    folder.append(demand)
    return demand


def set_demand_item(model, demand, item):
    if item.getVehicle() == None:
        model.getLog().addError("Invalid Demand Item: no vehicle")
    else:
        schedule = GKScheduleDemandItem()
        schedule.setTrafficDemandItem(item)
        # Starts at 8:00:00 AM
        schedule.setFrom(8 * 3600)
        # Duration: 500 hour
        schedule.setDuration(500 * 3600)
        demand.addToSchedule(schedule)


def set_state_vehicle(model, state, veh_type_name):
    # find vehicle type
    veh_type = model.getCatalog().findByName(
        veh_type_name, model.getType("GKVehicle"))
    # set state vehicles
    state.setVehicle(veh_type)
    # find the state object
    # state_car = model.getCatalog().findByName(
    #     state_name, model.getType("GKTrafficState"))
    # state_car.setVehicle(veh_type)


def set_vehicles_color(model):
    viewMode = model.getGeoModel().findMode(
        "GKViewMode::VehiclesByVehicleType", False)
    if viewMode is None:
        viewMode = GKSystem.getSystem().newObject("GKViewMode", model)
        viewMode.setInternalName("GKViewMode::VehiclesByVehicleType")
        viewMode.setName("DYNAMIC: Simulation Vehicles by Vehicle Type")
        model.getGeoModel().addMode(viewMode)
    viewMode.removeAllStyles()
    viewStyle = model.getGeoModel().findStyle(
        "GKViewModeStyle::VehiclesByVehicleType")
    if viewStyle is None:
        viewStyle = GKSystem.getSystem().newObject("GKViewModeStyle", model)
        viewStyle.setInternalName("GKViewModeStyle::VehiclesByVehicleType")
        viewStyle.setName("DYNAMIC: Simulation Vehicles by Vehicle Type")
        viewStyle.setStyleType(GKViewModeStyle.eColor)
        viewStyle.setVariableType(GKViewModeStyle.eDiscrete)
        simType = model.getType("GKSimVehicle")
        typeColumn = simType.getColumn("GKSimVehicle::vehicleTypeAtt",
                                       GKType.eSearchOnlyThisType)
        viewStyle.setColumn(simType, typeColumn)
        ramp = GKColorRamp()
        ramp.setType(GKColorRamp.eRGB)
        vehicles = model.getCatalog().getObjectsByType(
            model.getType("GKVehicle"))
        if vehicles is not None:
            ramp.lines(len(vehicles))
            i = 0
            for vehicle in vehicles.itervalues():
                color_range = viewStyle.addRange(vehicle.getName())
                color_range.color = ramp.getColor(i)
                i = i + 1
        model.getGeoModel().addStyle(viewStyle)
    viewMode.addStyle(viewStyle)


# Returns (and creates if needed) the folder for the control plan
def get_control_plan_folder(model):
    folder_name = "GKModel::controlPlans"
    folder = model.getCreateRootFolder().findFolder(folder_name)
    if folder == None:
        folder = GKSystem.getSystem().createFolder(model.getCreateRootFolder(),
                                                   folder_name)
    return folder


# Creates a new control plan
def create_control_plan(model, name):
    control_plan = GKSystem.getSystem().newObject("GKControlPlan", model)
    control_plan.setName(name)
    folder = get_control_plan_folder(model)
    folder.append(control_plan)
    return control_plan


# Finds an object using its identifier and checks if it is really a node
def find_node(model, entry):
    node = model.getCatalog().find(int(entry))
    if node != None:
        if node.isA("GKNode") == False:
            node = None
    return node


# Finds an object using its identifier and checks if it is really a turn
def find_turn(model, entry):
    turn = model.getCatalog().find(int(entry))
    if turn != None:
        if turn.isA("GKTurning") == False:
            turn = None
    return turn


# Returns (and creates if needed) the signals list.
#
def create_signal_groups(model, node):  #TODO generalize
    signals = []

    if len(node.getSignals()) == 0:
        signal = GKSystem.getSystem().newObject("GKControlPlanSignal", model)
        signal.addTurning(findTurn(model, 970))
        signal.addTurning(findTurn(model, 979))
        node.addSignal(signal)
        signals.append(signal)

        signal = GKSystem.getSystem().newObject("GKControlPlanSignal", model)
        signal.addTurning(findTurn(model, 973))
        signal.addTurning(findTurn(model, 976))
        node.addSignal(signal)
        signals.append(signal)
    else:
        for signal in node.getSignals():
            signals.append(signal)

    return signals


# Creates the phases, set the cycle time and sets the phases times
def set_signal_times(cp, node, signal_groups):  #TODO generalize
    cp_node = cp.createControlJunction(node)
    cp_node.setCycle(40)
    cp_node.setControlJunctionType(GKControlJunction.eFixedControl)

    from_time = 0;

    # add phases
    for signal in signal_groups:
        phase1 = cp_node.createPhase()
        phase1.setFrom(from_time)
        phase1.setDuration(15)
        phase1.addSignal(signal.getId())

        phase2 = cp_node.createPhase()
        phase2.setFrom(from_time + 15)
        phase2.setDuration(5)
        phase2.setInterphase(True)

        from_time = from_time + 20


def create_meter(model, section):
    meter_length = 2
    pos = section.getLanesLength2D() - meter_length
    type = model.getType("GKMetering")
    cmd = model.createNewCmd(model.getType("GKSectionObject"))
    cmd.init(type, section, 0, 0, pos, meter_length)  # TODO double check the zeros
    model.getCommander().addCommand(cmd)
    meter = cmd.createdObject()
    meter.setName("meter_{}".format(section.getName()))
    return meter


def set_metering_times(
        cp, meter, cycle, green, yellow, offset, min_green, max_green):
    cp_meter = cp.createControlMetering(meter)
    cp_meter.setControlMeteringType(GKControlMetering.eExternal)
    cp_meter.setCycle(cycle)
    cp_meter.setGreen(green)
    cp_meter.setYellowTime(yellow)
    cp_meter.setOffset(offset)
    cp_meter.setMinGreen(min_green)
    cp_meter.setMaxGreen(max_green)


def create_node_meters(model, cp, node):
    meters = []
    enter_sections = node.getEntranceSections()
    for section in enter_sections:
        meter = create_meter(model, section)
        # default light params
        cycle = 40
        green = 17
        yellow = 3
        min_green = 5
        max_green = 40
        # offset for vertical edges is 20 and for horizontal edges is 0
        if "bot" in meter.getName() or "top" in meter.getName():
            offset = 0
        elif "left" in meter.getName() or "right" in meter.getName():
            offset = 20
        set_metering_times(cp, meter, cycle, green, yellow, offset, min_green,
                           max_green)
        meters.append(meter)


# collect the scenario-specific data
data_file = 'flow/core/kernel/scenario/data.json'
with open(os.path.join(config.PROJECT_PATH, data_file)) as f:
    data = json.load(f)

# export the data from the dictionary
nodes = data['nodes']
edges = data['edges']
types = data['types']
connections = data['connections']
veh_types = data['vehicle_types']

for i in range(len(edges)):
    if 'type' in edges[i]:
        for typ in types:
            if typ['id'] == edges[i]['type']:
                new_dict = deepcopy(typ)
                new_dict.pop("id")
                edges[i].update(new_dict)
                break

if data['inflows'] is not None:
    inflows = InFlows()
    inflows.__dict__ = data['inflows'].copy()
else:
    inflows = None

# generate the network
generate_net(nodes, edges, connections, inflows, veh_types)

# run the simulation
# find the replication
replication_name = "Replication 870"
replication = model.getCatalog().findByName(replication_name)
# execute, "play": run with GUI, "execute": run in batch mode
GKSystem.getSystem().executeAction("execute", replication, [], "")