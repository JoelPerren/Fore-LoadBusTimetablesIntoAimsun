#------------------------------------------------------------------------------
# This script imports CSV files containing bus information into Aimsun.
# It assumes that the CSV files have been produced from an XML file in the 
# Traveline National Dataset (TNDS) using the 'FORE - TNDS Parser' script.
#
# It generates a set of PT lines within Aimsun for each route which is a
# reflection of the changing routes within the timetable.
#
# (c) Joel Perren (Fore Consulting) 2019
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# Imports and Parameters
#------------------------------------------------------------------------------

import os
import re
import datetime, time

CSV_PATH = "C:\\Users\\Joel.Perren\\Documents\\Traveline Data\\TransXChange\\Wakefield Aimsun Model\\CSV"
PT_FOLDER = model.getCatalog().find(1671)
BUS_ID = 9


#------------------------------------------------------------------------------
# Function Definitions
#------------------------------------------------------------------------------

def match_stops_in_model(stops):
	"""
	Matches a list of bus stops with stops present in the model.
	The bus_station_ids provides a handling method for bus stations.
	Input all the ATCO codes associated with bus station stops into the array
	and ensure the Bus Terminal in Aimsun has the EID 'Bus Station'.

	Parameters
	----------
	stops : list
		A list of tuples containg two items of stop information: (stop_eid, time)

	Returns
	-------
	list
		A list of the stop tuples where the stop_eid exists in the model
	"""
	bus_station_ids = ['450030204', '450030188', '450030189', '450030190', '450030182', '450030183', '450030184', '450030185', '450030186',
						'450030196', '450030197', '450030191', '450030192', '450030187', '450030194', '450030193', '450030195', '450030202',
						'450030203', '450030198', '450030199', '450030200', '450030201', '450030331']
	model_route = []

	for stop in stops:
		model_stop = model.getCatalog().findObjectByExternalId(stop[0])

		if (model_stop != None):
			model_route.append(stop)
		elif (stop[0] in bus_station_ids):
			model_route.append(('Bus Station', stop[1]))

	return model_route

def get_route_name(file, first_stop, last_stop):
	"""
	Calculates the name of a route based on the csv filename and
	the first and last stops of the route.

	Parameters
	----------
	file : File
		The CSV file being parsed
	
	first_stop : str
		The EID of the first stop in the route which appears in the model

	last_stop : str
		The EID of the last stop in the route which appears in the model

	Returns
	-------
	str
		A name for the bus route
	"""
	filename = os.path.basename(file.name).strip('.csv')
	fs_name = model.getCatalog().findObjectByExternalId(first_stop).getName()
	ls_name = model.getCatalog().findObjectByExternalId(last_stop).getName()

	return "{}: {} [{}] to {} [{}]".format(filename, fs_name, first_stop, ls_name, last_stop)

def calculate_pt_leg(pt_line, leg):
	"""
	Calculates the route of a PT line based on an associated list of stops.
	Outputs a ROUTE ERROR if unable to successfully calculate the route.
	This is often due to the route involving sections outside the model and
	such errors should be considered critial and manually reviewed.

	Parameters
	----------
	pt_line : GKPublicLine
		The Public Transport Line to calculate a route for

	stops : list
		A list of tuples containg two items of stop information: (stop_eid, time)

	Returns
	-------
	None 
	"""
	route = leg["Route"]
	stops = leg["Stops"]

	pt_line.setRoute(route)

	added_stops = []

	for link in route:
		added = False

		for stop in stops:
			stop_obj = model.getCatalog().findObjectByExternalId(stop[0])

			if (stop_obj.getSection().getId() == link.getId()):
				added_stops.append(stop_obj)
				added = True
				break
		
		if (added == False):
			added_stops.append(None)

	pt_line.setStops(added_stops)

def create_pt_line(name, leg):
	"""
	Creates a PT line, timetable, and schedule

	Parameters
	----------
	name : str
		A name for the PT line

	stops : list
		A list of tuples containg two items of stop information: (stop_eid, time)

	Returns
	-------
	pt_line : GKPublicLine
		The public transport line which has been created
	"""
	pt_line = GKSystem.getSystem().newObject("GKPublicLine", model)
	pt_line.setName(name)
	calculate_pt_leg(pt_line, leg)
	timetable = GKSystem.getSystem().newObject("GKPublicLineTimeTable", model)
	timetable.setName("Timetable - " + name)
	pt_line.addTimeTable(timetable)
	schedule = timetable.createNewSchedule()
	schedule.setTime(QTime(0, 0, 0))
	schedule.setDepartureType(GKPublicLineTimeTableSchedule.eFixed)
	schedule.setDuration(GKTimeDuration(23,59,59))
	timetable.addSchedule(schedule)

	PT_FOLDER.append(pt_line)

	return pt_line

def add_departure(pt_line, time):
	"""
	Adds a departure to an existing PT line/timetable

	Parameters
	----------
	pt_line : GKPublicLine
		The public transport line to add the departures to

	time : str
		A string representing the time of departure

	Returns
	-------
	None
	"""
	timetable = pt_line.getTimeTables()[0]
	schedule = timetable.getSchedules()[0]
	bus = model.getCatalog().find(BUS_ID)
	departure = GKPublicLineTimeTableScheduleDeparture()
	departure.setVehicle(bus)
	departure.setDepartureTime(QTime.fromString(time, "hh:mm:ss"))
	departure.setMeanTime(GKTimeDuration(0, 0, 0))
	schedule.addDepartureTime(departure)

def set_dwell_times():
	"""
	Sets the dwell time for all bus stops where the mean or 
	deviation dwell times are 0 to the default values of
	mean: 20s, deviation 10s
	"""
	public_line_type = model.getType("GKPublicLine")
	for types in model.getCatalog().getUsedSubTypesFromType(public_line_type):

		for public_line in types.itervalues():
			timetables = public_line.getTimeTables()
			bus_stops = public_line.getStops()
			
			for timetable in timetables:
				schedules = timetable.getSchedules()
				
				for schedule in schedules:
				
					for bus_stop in bus_stops:
						stop_time = schedule.getStopTime(bus_stop, 1)
						mean = stop_time.mean
						deviation = stop_time.deviation
							
						if (mean == 0):
							mean = 20
								
						if (deviation == 0):
							deviation = 10
								
						schedule.setStopTime(bus_stop, 1, mean, deviation)

def find_route_legs(stops):
	legs = []
	sections = []
	for stop in stops:
		section = model.getCatalog().findObjectByExternalId(stop[0]).getSection()
		sections.append(section)

	sp_manager = GKSPManager()
	sp_manager.setCostType(GKSPManager.eDistance)
	sp_manager.build(model, None)

	route = []
	route_stops = []
	for i, section in enumerate(sections):
		try:
			path = sp_manager.getPath(section, sections[i + 1])
			path_len = len(path)
			route_stops.append(stops[i])

			if (path_len > 20):
				warning = "PATH LENGTH WARNING: A calculated path between stop {} and stop {} is {} sections long. This could be inaccurate.".format(stops[i][0], stops[i + 1][0], path_len)
				if (warning not in error_log):
					error_log.append(warning)

			if (len(path) == 0):
				leg = {
					"Route" : route,
					"Stops" : route_stops,
				}
				legs.append(leg)
				route = []
				route_stops = []
			else:
				for link in path:
					if (len(route) == 0):
						route.append(link)
					else:
						if (link != route[-1]):
							route.append(link)
		except:
			pass
	
	route_stops.append(stops[-1])
	leg = {
			"Route" : route,
			"Stops" : route_stops,
	}
	legs.append(leg)
	return legs

def get_timetable(csv_file):
	"""
	Gets the timetable associed with a given csv file.
	If the associated PT route already exists, it just adds a new departure.
	If the associated PT route does not exist, it creates a new one.
	Outputs a TIMETABLE ERROR if it encounters issues creating a departure.
	Generally this is because the route does not enter the model area at a
	particular time due to variation in the route throughout the day.

	Parameters
	----------
	csv_file : file
		The CSV file to parse

	Returns
	-------
	None
	"""
	csv = open("{}\\{}".format(CSV_PATH, csv_file), "r")

	for i, row in enumerate(csv):
		stops = []
		data = row.strip().split(",")

		if (i == 0):
			continue

		for stop in data:
			stop_eid = re.sub(r'\([^)]*\)', '', stop).strip()
			time = re.search(r'\((.*?)\)', stop).group(1)
			stops.append((stop_eid, time))
		
		model_stops = match_stops_in_model(stops)

		if (len(model_stops) == 0):
			err = "ROUTE NOT IN MODEL: {} beginning at {} has no stops within the model area. Skipping.".format(csv_file, stops[0][1])
			continue

		route_legs = find_route_legs(model_stops)

		for leg in route_legs:
			if (len(leg["Stops"]) < 2):
				continue

			leg_name = get_route_name(csv, leg["Stops"][0][0], leg["Stops"][-1][0])
			pt_line = model.getCatalog().findByName(leg_name)

			if (pt_line == None):
				pt_line = create_pt_line(leg_name, leg)

			add_departure(pt_line, leg["Stops"][0][1])

def delete_pt_routes():
	"""
	Deletes existing PT routes and PT timetables
	"""
	route_type = model.getType("GKPublicLine") # GKType
	routes = model.getCatalog().getObjectsByType(route_type) # GKPublicLine
	if routes != None:
		for route in routes.itervalues():
			cmd = route.getDelCmd()
			model.getCommander().addCommand(cmd)

	timetable_type = model.getType("GKPublicLineTimeTable") # GKType
	timetables = model.getCatalog().getObjectsByType(timetable_type) # GKPublicLine
	if timetables != None:
		for timetable in timetables.itervalues():
			cmd = timetable.getDelCmd()
			model.getCommander().addCommand(cmd)
	
	print("Existing PT routes and timetables removed")

def output_errors(errors):
	"""
	Outputs any errors to a log file

	Parameters
	----------
	errors : list
		A list of error strings to output into a log file
	"""
	num = len(errors)

	if (num > 1):
		now = datetime.datetime.now()
		f = open("{}\\{}".format(CSV_PATH, "Error Log.txt"), "w")
		f.write("{}\n".format(now.strftime("%d/%m/%Y")))
		f.write("{}\n".format(now.strftime("%H:%M")))
		f.write("\n")
		f.write("{} errors\n".format(len(errors)))
		f.write("\n")
		
		for error in errors:
			f.write("{}\n".format(error))

		f.close()
		print("Load Bus Timetable script complete!\n{} warnings output to {}.".format(num, f.name))
	else:
		print("Load Bus Timetable complete!\nNo warnings reported.")
		

#------------------------------------------------------------------------------
# Main Script
#------------------------------------------------------------------------------

print("Load Bus Timetable script starting...")
delete_pt_routes()
csv_files = []
error_log = []

for file in os.listdir(CSV_PATH):
	if file.endswith(".csv"):
		csv_files.append(file)

task = GKSystem.getSystem().createTask(model)
task.setName("Load Bus Timetables")
steps = len(csv_files)
task.setTotalSteps(steps)
task.setStepsUpdate(0)
task.start()

for i, csv in enumerate(csv_files):
	before = time.time()

	try:
		get_timetable(csv)
	except Exception as e:
		err = "CSV FILE ERROR: Could not parse {}. {}.".format(csv, e)
		error_log.insert(0, err)

	after = time.time()
	dur = after - before
	task.stepTask(i, dur)
	task.setState("{} of {} complete".format(i + 1, steps))

task.end(task.eDoNotStore)
task.cancel()
set_dwell_times()
output_errors(error_log)
