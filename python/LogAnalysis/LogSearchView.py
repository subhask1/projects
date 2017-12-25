#!/usr/bin/env python

############################################################################
# Script Name:  LogSearchView.py
# Description:  This script parses various log files in a multi clustered
#               environment based Search Keywords, Produces output in HTML 
#               format with summary counts and sends email message.
# Functionalities: 
#       - Connects to machines (ITG and/or Prod) 
#		- Reads specified Log file (Local or remote machines connected via ssh) line by line
#		- Performs parallel processing of Log files when multiprocessing option is chosen.
#		- Separates Data Elements based on specified Delimiter Tag
#		- Parses Log Text based on specified Search Keyword(s) and criteria and extracts it when match found.
#		- Prepares output in structured HTML format
#		- Writes output information into a text file
#		- Sends email message in HTML Format to designated PDLs with output data 
#		- Produces JSON and XML output for the REST service call.
# Input Parameters:
#		- Environment (e.g. ITG, Production)
#       - Cluster Name (e.g. cluster1, cluster2, cluster3)
#       - Server Name (e.g. all or server1)
#		- Log Type (e.g access_log, db_log, server_log)
#		- Search Keywords (comma separated e.g. stderr,error)
#		- Search Criteria (All [equivalent to "and"], Any [equivalent to "or"])
# Dependency: 
#		- Properties File:
#			- Name: LogSearchView.properties
#			- Purpose: For Global Config Parameter Settings
# Installation:
#		- Logon to the Server 
#		- Switch to Application/Service Account, if required
#		- Create a new directory 
#		- Place LogSearchView.py, LogSearchView.properties and LogSearchViewWeb.py files inside the new directory
# Execution Steps:
#		- Foreground (unix/linux): python /<New_Directory>/LogSearchView.py <env> <cluster> <server> <log_type> <search_keywords> <serach_criteria> e.g. python /<New_Directory>/LogSearchView.py itg cluster1 all managed_server_log stderr,error all
#		- Background (unix/linux): nohup python /<New_Directory>/LogSearchView.py <env> <cluster> <server> <log_type> <search_keywords> <serach_criteria> > LogSearchView.log & e.g. nohup python /<New_Directory>/LogSearchView.py itg cluster1 all managed_server_log stderr,error all > LogSearchView.log & 
# Change History:
#	Initial:
#		- Date: 10/27/2016
############################################################################

import sys
import os
import re
import smtplib
from email.MIMEText import MIMEText
from email.MIMEMultipart import MIMEMultipart
import time
import socket
import subprocess
import pipes
import ConfigParser
from xml.etree import ElementTree as ET
from xml.dom import minidom
import multiprocessing

# Change Property file location if required
properties_file = "./LogSearchView.properties"
config = ConfigParser.ConfigParser()

input_param_env = ""
input_param_cluster_name = ""
input_param_server_name = ""
input_param_log_file_type = ""
input_param_search_keywords = ""
input_param_search_criteria = ""

def getProperty(group, prop):
  global properties_file, config
  config.read(properties_file)
  return config.get(group, prop)

def validateClusterServer(env, object_type, object_id):
  isFound = False
  machines = getProperty("machine_info", env).split(",")
  for machine in machines:
    clusters = getProperty(machine, "clusters").split(",")
    if object_type == "cluster":
      if object_id in clusters:
        isFound = True    
    if object_type == "server":
      for cluster in clusters:
        servers = getProperty(machine, cluster).split(",")
        if object_id in servers:
          isFound = True
          break
      if isFound:
        break
  return isFound
      
def validateInputParameters():
  param_list = []
  isErrorFound = False
  global input_param_env, input_param_cluster_name, input_param_server_name, input_param_log_file_type, input_param_search_keywords, input_param_search_criteria
  if len(sys.argv) <> 7:
    print getProperty("messages", "error_type") + " " + getProperty("messages", "error_invalid_number_of_parameters")
    sys.exit()
  env = getProperty("environments", "env").split(",")
  if not sys.argv[1].lower() in env:
    print getProperty("messages", "error_type") + " " + getProperty("messages", "error_invalid_parameter_value") + " - " + sys.argv[1]
    isErrorFound = True
  if not isErrorFound:
    if not validateClusterServer(sys.argv[1].lower(), "cluster", sys.argv[2]):
      print getProperty("messages", "error_type") + " " + getProperty("messages", "error_invalid_parameter_value") + " - " + sys.argv[2]
      isErrorFound = True
  if not isErrorFound:
    if not sys.argv[3].lower() == "all":
      if not validateClusterServer(sys.argv[1].lower(), "server", sys.argv[3]):
        print getProperty("messages", "error_type") + " " + getProperty("messages", "error_invalid_parameter_value") + " - " + sys.argv[3]
        isErrorFound = True
  log_filetype = getProperty("log_fileinfo", "log_filetype").split(",")
  if not sys.argv[4] in log_filetype:
    print getProperty("messages", "error_type") + " " + getProperty("messages", "error_invalid_parameter_value") + " - " + sys.argv[4]
    isErrorFound = True
  search_criteria = getProperty("log_fileinfo", "search_criteria").split(",")
  if not sys.argv[6].lower() in search_criteria:
    print getProperty("messages", "error_type") + " " + getProperty("messages", "error_invalid_parameter_value") + " - " + sys.argv[6]
    isErrorFound = True
  if isErrorFound:
    sys.exit()
  param_list.append(sys.argv[1].lower()) # Env
  param_list.append(sys.argv[2])         # Cluster
  param_list.append(sys.argv[3])         # Managed Server
  param_list.append(sys.argv[4].lower()) # Log File Type
  param_list.append(sys.argv[5].lower()) # Search Keywords
  param_list.append(sys.argv[6].lower()) # Search Criteria
  input_param_env = sys.argv[1]
  input_param_cluster_name = sys.argv[2]
  input_param_server_name = sys.argv[3]
  input_param_log_file_type = sys.argv[4]
  input_param_search_keywords = sys.argv[5]
  input_param_search_criteria = sys.argv[6]
  return param_list

def getMachines(env, object_type, object_id):
  isFound = False
  machines = []
  all_machines = getProperty("machine_info", env).split(",")
  for machine in all_machines:
    clusters = getProperty(machine, "clusters").split(",")
    if object_type == "cluster":
      if object_id in clusters:
        machines.append(machine)
    if object_type == "server":
      for cluster in clusters:
        servers = getProperty(machine, cluster).split(",")
        if object_id in servers:
          machines.append(machine)
          isFound = True
          break
      if isFound:
        break
  return machines

def updateKeywordCount(keyword_count_server, line, search_keywords):
  for search_keyword in search_keywords:
    for keyword_count_server_row in keyword_count_server:
      if keyword_count_server_row[0] == search_keyword:
        keyword_count_server_row[1] = keyword_count_server_row[1] + line.lower().count(search_keyword)
  return keyword_count_server
      
def mergeLine(c, l):
  if c:
    return c.rstrip() + " " + l
  else:
    return l

def parseSinglelineBlock(machine_name, log_filename_with_path, regex_start_plus_end_tag, number_of_data_elements):
  if machine_name == socket.gethostname():
    if os.path.isfile(log_filename_with_path):
      try:
        with open(log_filename_with_path) as lines:
          for line in lines:
            if len(re.findall(regex_start_plus_end_tag, line)) == (number_of_data_elements - 1):
              yield line
              continue
      except:
        print getProperty("messages", "error_reading_log_file") + " - " + log_filename_with_path
        sys.exit()
  else:
    if subprocess.call(["ssh", machine_name, 'test -e ' + pipes.quote(log_filename_with_path)]) == 0:
      try:
        ssh = subprocess.Popen(["ssh", machine_name, "cat", log_filename_with_path], stdout=subprocess.PIPE)
        for line in ssh.stdout:
          if len(re.findall(regex_start_plus_end_tag, line)) == (number_of_data_elements - 1):
            yield line
            continue
      except:
        print getProperty("messages", "error_reading_log_file") + " - " + machine_name + ":" + log_filename_with_path
        sys.exit()

def parseMultilineBlock(machine_name, log_filename_with_path, regex_start_tag, regex_end_tag, regex_start_plus_end_tag, number_of_data_elements):
  if machine_name == socket.gethostname():
    if os.path.isfile(log_filename_with_path):
      try:
        with open(log_filename_with_path) as lines:
          linecache, halfline = ("", False)
          for line in lines:
            if len(re.findall(regex_start_plus_end_tag, line)) == number_of_data_elements:
              yield line
              continue
            if not halfline:
              linecache = ""
            linecache = mergeLine(linecache, line)
            if halfline:
              halfline = not re.match(regex_end_tag, line)
            else:
              halfline = re.match(regex_start_tag, line)
            if not halfline:
              yield linecache
          if halfline:
            yield linecache
      except:
        print getProperty("messages", "error_reading_log_file") + " - " + log_filename_with_path
        sys.exit()
  else:
    if subprocess.call(["ssh", machine_name, 'test -e ' + pipes.quote(log_filename_with_path)]) == 0:
      try:
        ssh = subprocess.Popen(["ssh", machine_name, "cat", log_filename_with_path], stdout=subprocess.PIPE)
        linecache, halfline = ("", False)
        for line in ssh.stdout:
          if len(re.findall(regex_start_plus_end_tag, line)) == number_of_data_elements:
            yield line
            continue
          if not halfline:
            linecache = ""
          linecache = mergeLine(linecache, line)
          if halfline:
            halfline = not re.match(regex_end_tag, line)
          else:
            halfline = re.match(regex_start_tag, line)
          if not halfline:
            yield linecache
        if halfline:
          yield linecache
      except:
        print getProperty("messages", "error_reading_log_file") + " - " + machine_name + ":" + log_filename_with_path
        sys.exit()

def parseLogFileMP(log_files_with_param_list):
  output_list = []
  all_keyword_counts = []
  all_log_elements = []
  param_list = log_files_with_param_list[0]
  machine = log_files_with_param_list[1]
  cluster = log_files_with_param_list[2]
  server = log_files_with_param_list[3]
  log_filename = log_files_with_param_list[4]
  log_filetype = param_list[3]
  data_element_tag = getProperty(log_filetype, "data_element_tag")
  number_of_data_elements = len(getProperty(log_filetype, "data_element_logmsg_headers").split(','))
  search_keywords = param_list[4].split(",")
  search_criteria = param_list[5]
  if len(data_element_tag) == 0:
    regex_start_plus_end_tag = re.compile(r"!.")
  elif len(data_element_tag) == 1:
    regex_start_plus_end_tag = re.compile(r"" + re.escape(data_element_tag) + r"")
  elif data_element_tag[:1] == "\\":
    regex_start_plus_end_tag = re.compile(r"" + data_element_tag + r"")
  elif len(data_element_tag) == 2:
    data_element_start_tag = data_element_tag[:1]
    data_element_end_tag = data_element_tag[1:]
    regex_start_tag = re.compile(r"" + re.escape(data_element_start_tag) + r"(.*?)")
    regex_end_tag = re.compile(r"(.*?)" + r"" + re.escape(data_element_end_tag))
    regex_start_plus_end_tag = re.compile(r"" + re.escape(data_element_start_tag) + r"(.*?)" + r"" + re.escape(data_element_end_tag))  
  log_elements = []
  keyword_count_server = []
  for search_keyword in search_keywords:
    keyword_count_server.append([search_keyword, 0])
  if len(data_element_tag) == 0 or len(data_element_tag) == 1 or data_element_tag[:1] == "\\":
    for line in parseSinglelineBlock(machine, log_filename, regex_start_plus_end_tag, number_of_data_elements):
      line_elements = []
      search_found = False
      if search_criteria == "any":
        if any(x in line.lower() for x in search_keywords):
          search_found = True
      if search_criteria == "all":
        if all(x in line.lower() for x in search_keywords):
          search_found = True
      if search_found:
        if len(data_element_tag) == 0:
          line_elements = [line]
        elif len(data_element_tag) == 1:
          line_elements = line.split(data_element_tag) 
        elif data_element_tag[:1] == "\\":
          line_elements = re.split(regex_start_plus_end_tag, line)
        log_elements.append(line_elements)
        keyword_count_server = updateKeywordCount(keyword_count_server, line, search_keywords)
  elif len(data_element_tag) == 2:
    for line in parseMultilineBlock(machine, log_filename, regex_start_tag, regex_end_tag, regex_start_plus_end_tag, number_of_data_elements):
      line_elements = []
      search_found = False
      if not data_element_start_tag in line and not data_element_end_tag in line:
        continue
      if search_criteria == "any":
        if any(x in line.lower() for x in search_keywords):
          search_found = True
      if search_criteria == "all":
        if all(x in line.lower() for x in search_keywords):
          search_found = True
      if search_found:
        line_elements = re.findall(regex_start_plus_end_tag, line)
        if len(line_elements) == number_of_data_elements:
          log_elements.append(line_elements)
          keyword_count_server = updateKeywordCount(keyword_count_server, line, search_keywords)
  if len(log_elements) > 0:
    all_log_elements.append([param_list[0], machine, cluster, server, log_elements])
    all_keyword_counts.append([param_list[0], machine, cluster, server, keyword_count_server]) 
  output_list.append(all_keyword_counts)
  output_list.append(all_log_elements)
  return output_list

def parseLogFile(param_list):
  output_list = []
  all_keyword_counts = []
  all_log_elements = []
  cluster = param_list[1]
  server = param_list[2]
  log_filetype = param_list[3]
  log_filepath_from_property_file = getProperty("log_fileinfo", "log_filepath")
  log_filename_from_property_file = getProperty(log_filetype, "log_filename")
  data_element_tag = getProperty(log_filetype, "data_element_tag")
  number_of_data_elements = len(getProperty(log_filetype, "data_element_logmsg_headers").split(','))
  search_keywords = param_list[4].split(",")
  search_criteria = param_list[5]
  if len(data_element_tag) == 0:
    regex_start_plus_end_tag = re.compile(r"!.")
  elif len(data_element_tag) == 1:
    regex_start_plus_end_tag = re.compile(r"" + re.escape(data_element_tag) + r"")
  elif data_element_tag[:1] == "\\":
    regex_start_plus_end_tag = re.compile(r"" + data_element_tag + r"")
  elif len(data_element_tag) == 2:
    data_element_start_tag = data_element_tag[:1]
    data_element_end_tag = data_element_tag[1:]
    regex_start_tag = re.compile(r"" + re.escape(data_element_start_tag) + r"(.*?)")
    regex_end_tag = re.compile(r"(.*?)" + r"" + re.escape(data_element_end_tag))
    regex_start_plus_end_tag = re.compile(r"" + re.escape(data_element_start_tag) + r"(.*?)" + r"" + re.escape(data_element_end_tag))
  if server == "all":
    machines = getMachines(param_list[0], "cluster", cluster)
  else:
    machines = getMachines(param_list[0], "server", server)
  for machine in machines:
    if param_list[2] == "all":
      servers = getProperty(machine, cluster).split(",")
    else:
      servers = [server]
    for server in servers:
      log_filename_with_path = ""
      log_elements = []
      log_filepath = log_filepath_from_property_file.replace("$cluster", cluster).replace("$server", server)
      log_filename = log_filename_from_property_file.replace("$server", server)
      log_filename_with_path = log_filepath + log_filename
      keyword_count_server = []
      for search_keyword in search_keywords:
        keyword_count_server.append([search_keyword, 0])
      if len(data_element_tag) == 0 or len(data_element_tag) == 1 or data_element_tag[:1] == "\\":
        for line in parseSinglelineBlock(machine, log_filename_with_path, regex_start_plus_end_tag, number_of_data_elements):
          line_elements = []
          search_found = False
          if search_criteria == "any":
            if any(x in line.lower() for x in search_keywords):
              search_found = True
          if search_criteria == "all":
            if all(x in line.lower() for x in search_keywords):
              search_found = True
          if search_found:
            if len(data_element_tag) == 0:
              line_elements = [line]
            elif len(data_element_tag) == 1:
              line_elements = line.split(data_element_tag) 
            elif data_element_tag[:1] == "\\":
              line_elements = re.split(regex_start_plus_end_tag, line)
            log_elements.append(line_elements)
            keyword_count_server = updateKeywordCount(keyword_count_server, line, search_keywords)
      elif len(data_element_tag) == 2:
        for line in parseMultilineBlock(machine, log_filename_with_path, regex_start_tag, regex_end_tag, regex_start_plus_end_tag, number_of_data_elements):
          line_elements = []
          search_found = False
          if not data_element_start_tag in line and not data_element_end_tag in line:
            continue
          if search_criteria == "any":
            if any(x in line.lower() for x in search_keywords):
              search_found = True
          if search_criteria == "all":
            if all(x in line.lower() for x in search_keywords):
              search_found = True
          if search_found:
            line_elements = re.findall(regex_start_plus_end_tag, line)
            if len(line_elements) == number_of_data_elements:
              log_elements.append(line_elements)
              keyword_count_server = updateKeywordCount(keyword_count_server, line, search_keywords)
      if len(log_elements) > 0:
        all_log_elements.append([param_list[0], machine, cluster, server, log_elements])
        all_keyword_counts.append([param_list[0], machine, cluster, server, keyword_count_server]) 
  output_list.append(sorted(all_keyword_counts, key=lambda x : x[4], reverse=True))
  output_list.append(all_log_elements)
  return output_list

def getLogFilenames(param_list):
  log_filenames_with_param_list = []
  env = param_list[0]
  cluster = param_list[1]
  server = param_list[2]
  log_filetype = param_list[3]
  log_filepath_from_property_file = getProperty("log_fileinfo", "log_filepath")
  log_filename_from_property_file = getProperty(log_filetype, "log_filename")
  if server == "all":
    machines = getMachines(env, "cluster", cluster)
  else:
    machines = getMachines(env, "server", server)
  for machine in machines:
    if param_list[2] == "all":
      servers = getProperty(machine, cluster).split(",")
    else:
      servers = [server]
    for server in servers:
      log_filenames = []
      log_filename_with_path = ""
      log_filepath = log_filepath_from_property_file.replace("$cluster", cluster).replace("$server", server)
      log_filename = log_filename_from_property_file.replace("$server", server)
      log_filename_with_path = log_filepath + log_filename
      log_filenames.append(param_list)
      log_filenames.append(machine)
      log_filenames.append(cluster)
      log_filenames.append(server)
      log_filenames.append(log_filename_with_path)
      log_filenames_with_param_list.append(log_filenames)
  return log_filenames_with_param_list

def performMultiProcessing(param_list):
  output_list_keyword_count = []
  output_list_log_data = []
  output_list = []
  output_list_MP_for_all_processes = []
  output_list_keyword_count_servers_sorted = []
  output_list_log_data_sorted = []
  log_filenames_with_param_list = getLogFilenames(param_list)
     
  cpu_usage = int(getProperty("processing_info", "cpu_usage")[:-1])
  cpu_counts = multiprocessing.cpu_count()*cpu_usage/100
  # Divide Log files based on cpu_counts for multi processing.
  log_filenames_for_processes = [log_filenames_with_param_list[i:i+cpu_counts] for i in range(0, len(log_filenames_with_param_list), cpu_counts)]
  for log_filenames_for_each_process in log_filenames_for_processes:
    output_list_MP_for_each_process = []
    pool = multiprocessing.Pool(processes=len(log_filenames_for_each_process))
    output_list_MP_for_each_process = pool.map(parseLogFileMP, log_filenames_for_each_process)
    pool.close()
    pool.join()
    output_list_MP_for_all_processes.append(output_list_MP_for_each_process)
  # Extract Keyword counts
  for output_list_MP_for_all_process in output_list_MP_for_all_processes:
    for output_list_MP_for_all_process_row in output_list_MP_for_all_process:
      if len(output_list_MP_for_all_process_row[0]) > 0:
        output_list_keyword_count.append(output_list_MP_for_all_process_row[0][0])
  # Sort Keyword count list in descending order
  output_list_keyword_count_sorted = sorted(output_list_keyword_count, key=lambda x : x[4], reverse=True)
  output_list.append(output_list_keyword_count_sorted)
  for output_list_keyword_count_sorted_item in output_list_keyword_count_sorted:
    output_list_keyword_count_servers_sorted.append(output_list_keyword_count_sorted_item[3])
  for output_list_MP_for_all_process in output_list_MP_for_all_processes:
    for output_list_MP_for_all_process_row in output_list_MP_for_all_process:
      if len(output_list_MP_for_all_process_row[0]) > 0:
        for i in range(len(output_list_MP_for_all_process_row[1])):
          output_list_log_data.append(output_list_MP_for_all_process_row[1][i]) 
  # Arrange Log Data as per the sorted order of Keyword Counts
  for output_list_keyword_count_server_sorted in output_list_keyword_count_servers_sorted:
    idx = next((i for i, sublist in enumerate(output_list_log_data) if output_list_keyword_count_server_sorted in sublist), -1)
    output_list_log_data_sorted.append(output_list_log_data[idx])
  output_list.append(output_list_log_data_sorted)
  return output_list

def performProcessingLogData(param_list):
  output_list = []
  multi_processing = getProperty("processing_info", "multi_processing").lower()
  if multi_processing == "yes":
    output_list = performMultiProcessing(param_list)
  else:
    output_list = parseLogFile(param_list)
  return output_list

def buildHTMLOutput(param_list, output_list, invokedFromWeb):
  html_message = ""
  html_message_count_body = ""
  html_message_data_body = ""
  processing_time = "$processing_time"
  log_filetype = param_list[3]
  search_keywords = param_list[4].split(",")
  search_criteria = param_list[5]
  all_keyword_counts = output_list[0]
  all_log_elements = output_list[1]
  data_element_fixed_headers = getProperty("log_fileinfo", "data_element_fixed_headers").split(",")
  data_element_logmsg_headers = getProperty(log_filetype, "data_element_logmsg_headers").split(",")
  data_element_count_headers = getProperty("log_fileinfo", "data_element_count_headers").split(",")
  output_filename = getProperty("log_fileinfo", "output_filename")
  global input_param_env, input_param_cluster_name, input_param_server_name, input_param_log_file_type, input_param_search_keywords, input_param_search_criteria
  html_message = """\
    <html>\n \
      <head>\n \
        <title>View Log</title>\n \
        <div><h2 style="text-align:center;">""" + getProperty("log_fileinfo", "output_report_header") + " " + time.strftime("%x %X") + """</h2><label style="float:right;vertical-align:middle;">""" + processing_time + """</label></div>\n \
        <br><br>\n"""
  if invokedFromWeb: 
    html_message = html_message + """\n \
        <b>Input Parameters - Environment:</b> """ + param_list[0] + """\n \
        &nbsp;&nbsp;&nbsp;&nbsp;\n \
        <b>Cluster:</b> """ + param_list[1] + """\n \
        &nbsp;&nbsp;&nbsp;&nbsp;\n \
        <b>Server(s):</b> """ + param_list[2] + """\n \
        &nbsp;&nbsp;&nbsp;&nbsp;\n \
        <b>Log File Type:</b> """ + param_list[3] + """\n \
        &nbsp;&nbsp;&nbsp;&nbsp;\n \
        <b>Search Keywords:</b> """ + param_list[4] + """\n \
        &nbsp;&nbsp;&nbsp;&nbsp;\n \
        <b>Search Criteria :</b> """ + param_list[5] + """\n"""
  else:
    html_message = html_message + """ \
        <b>Input Parameters - Environment:</b> """ + input_param_env + """\n \
        &nbsp;&nbsp;&nbsp;&nbsp;\n \
        <b>Cluster:</b> """ + input_param_cluster_name + """\n \
        &nbsp;&nbsp;&nbsp;&nbsp;\n \
        <b>Server(s):</b> """ + input_param_server_name + """\n \
        &nbsp;&nbsp;&nbsp;&nbsp;\n \
        <b>Search Keywords:</b> """ + input_param_search_keywords + """\n \
        &nbsp;&nbsp;&nbsp;&nbsp;\n \
        <b>Search Criteria :</b> """ + input_param_search_criteria + """\n"""
  html_message = html_message + """\n \
        <br>\n"""
  if len(all_log_elements) == 0:
    html_message = html_message +  """ \
      <table border=1 align=center><tr><td><h3><font color=red>""" + getProperty("messages", "info_no_data_found") + """</font></h3></td></tr></table>\n \
        </head>\n \
      </html>\n"""
    return html_message
  for all_keyword_count in all_keyword_counts:
    html_message_count_body_row = ""
    keyword_count_server = all_keyword_count[4]
    for keyword_count_server_row in keyword_count_server:
      if keyword_count_server_row[1] > 0:
        html_message_count_body_row = html_message_count_body_row + """<tr>\n"""
        html_message_count_body_row = html_message_count_body_row + """\n"""
        for i in range(len(all_keyword_count) - 1): 
          html_message_count_body_row = html_message_count_body_row + """\n \
             <td>""" + all_keyword_count[i] + """</td>\n"""
        html_message_count_body_row = html_message_count_body_row + """\n \
          <td>""" + keyword_count_server_row[0] + """</td>\n"""
        if invokedFromWeb:
          if param_list[2] == "all":
            html_message_count_body_row = html_message_count_body_row + """\n \
            <td id='""" + all_keyword_count[len(all_keyword_count) - 2] + """' align='right'><a href="#" onclick="highlightSelectedRow('logCount', '""" + all_keyword_count[len(all_keyword_count) - 2] + """');showHideLogData('logData', '""" + all_keyword_count[len(all_keyword_count) - 2] + """');">""" + str(keyword_count_server_row[1]) + """</a></td>\n"""
          else:
            html_message_count_body_row = html_message_count_body_row + """\n \
            <td align='right'>""" + str(keyword_count_server_row[1]) + """</td>\n"""
        else:
          html_message_count_body_row = html_message_count_body_row + """\n \
          <td align='right'>""" + str(keyword_count_server_row[1]) + """</td>\n"""
        html_message_count_body_row = html_message_count_body_row + """</tr>\n"""
    html_message_count_body = html_message_count_body + html_message_count_body_row
  for all_log_element in all_log_elements:
    html_message_data_body_row = ""
    log_msg_list = all_log_element[4]
    for log_msg_list_row in log_msg_list:
      html_message_data_body_row =  html_message_data_body_row + """<tr id='""" + all_log_element[3] + """'>\n""" 
      html_message_data_body_row = html_message_data_body_row + """\n"""
      for i in range(len(all_log_element) - 1):
        html_message_data_body_row = html_message_data_body_row + """\n \
          <td>""" + all_log_element[i] + """</td>\n"""
      for i in range(len(log_msg_list_row)):
        html_message_data_body_row = html_message_data_body_row + """\n \
          <td>""" + log_msg_list_row[i] + """</td>\n"""
      html_message_data_body_row = html_message_data_body_row + """</tr>\n"""
    html_message_data_body = html_message_data_body + html_message_data_body_row
  if invokedFromWeb:
    html_message = html_message + """<b>Download:</b> <a href='/""" + output_filename +      """'>Text Output File</a><br><br>\n""" 
  html_message = html_message + """\n \
            </h4>\n \
            <script type="text/javascript">\n \
              function highlightSelectedRow(table_id, server) {\n \
                table = document.getElementById(table_id);\n \
                for (var i = 1; i < table.rows.length; i++) {\n \
                  var cells = table.rows[i].cells;
                  if (cells[5].id == server) \n \
                    table.rows[i].style.backgroundColor = "yellow";\n \
                  else\n \
                    table.rows[i].style.backgroundColor = "";\n \
                }\n \
              }\n \
              function showHideLogData(table_id, cluster) {\n \
                table = document.getElementById(table_id);\n \
                for (var i = 0; i < table.rows.length; i++) {\n \
                  if (table.rows[i].id == cluster)\n \
                    table.rows[i].style.display = "";\n \
                  else\n \
                    table.rows[i].style.display = "none";\n \
                }\n \
              }\n \
            </script>\n \
          </head>\n \
	  <body>\n \
	    <table id='logCount' border=1>\n \
              <thead>\n \
	      <tr bgcolor=#f0f0f0>\n"""
  for header in data_element_fixed_headers:
    html_message = html_message + """<th>""" + header + """</th>\n"""
  for header in data_element_count_headers:
    html_message = html_message + """<th>""" + header + """</th>\n"""
  html_message = html_message + """</tr>\n \
        </thead>\n \
        <tbody>\n"""
  html_message = html_message + html_message_count_body + """\n \
              </tbody>\n \
            </table>\n \
            <br>\n \
            <br>\n \
	    <table id='logData' border=1>\n \
              <thead>\n \
	      <tr bgcolor=#f0f0f0>\n """
  for header in data_element_fixed_headers:
    html_message = html_message + """<th>""" + header + """</th>\n"""
  for header in data_element_logmsg_headers:
    html_message = html_message + """<th>""" + header + """</th>\n"""
  html_message = html_message + """</tr>\n \
        </thead>\n \
        <tbody>\n"""
  html_message = html_message + html_message_data_body + """\n \
        </tbody>\n \
        </table>\n \
      </body>\n \
    </html>"""
  return html_message

# For REST API Service: JSON
def buildJSONOutput(param_list, output_list):
  output_input_params_dict = {}
  output_log_count_list = []
  output_log_data_list = []
  output_dict = {}
  all_output_dict = {}
  output_input_params_dict["env"] = param_list[0]
  output_input_params_dict["cluster"] = param_list[1]
  output_input_params_dict["server"] = param_list[2]
  output_input_params_dict["log_filetype"] = param_list[3]
  output_input_params_dict["search_keywords"] = param_list[4]
  output_input_params_dict["search_criteria"] = param_list[5]
  output_dict["input_parameters"] = output_input_params_dict
  data_element_fixed_headers = getProperty("log_fileinfo", "data_element_fixed_headers").split(",")
  data_element_count_headers = getProperty("log_fileinfo", "data_element_count_headers").split(",")
  all_keyword_counts = output_list[0]
  for all_keyword_count in all_keyword_counts:
    keyword_count_server = all_keyword_count[4]
    for keyword_count_server_row in keyword_count_server:
      if int(keyword_count_server_row[1]) > 0:
        output_log_count_dict_item = {}
        for i in range(len(all_keyword_count) - 1):
          output_log_count_dict_item[data_element_fixed_headers[i]] = all_keyword_count[i]
        for i in range(len(keyword_count_server_row)):
          output_log_count_dict_item[data_element_count_headers[i]] = keyword_count_server_row[i]
        output_log_count_list.append(output_log_count_dict_item) 
  output_dict["log_count"] = output_log_count_list
  data_element_logmsg_headers = getProperty(param_list[3], "data_element_logmsg_headers").split(",")
  all_log_elements = output_list[1]
  for all_log_element in all_log_elements:
    log_msg_list = all_log_element[4]
    for log_msg_list_row in log_msg_list:
      output_log_data_dict_item = {}
      for i in range(len(all_log_element) - 1):
        output_log_data_dict_item[data_element_fixed_headers[i]] = all_log_element[i]
      for i in range(len(log_msg_list_row)):
        output_log_data_dict_item[data_element_logmsg_headers[i]] = log_msg_list_row[i]
      output_log_data_list.append(output_log_data_dict_item)
  output_dict["log_data"] = output_log_data_list
  all_output_dict["results"] = output_dict
  return all_output_dict 

# For REST API Service: XML
def buildXMLOutput(param_list, output_list):
  results = ET.Element("results")
  input_parameters = ET.SubElement(results, "input_parameters")
  child = ET.SubElement(input_parameters, "env")
  child.text = param_list[0]
  child = ET.SubElement(input_parameters, "cluster")
  child.text = param_list[1]
  child = ET.SubElement(input_parameters, "server")
  child.text = param_list[2]
  child = ET.SubElement(input_parameters, "log_filetype")
  child.text = param_list[3]
  child = ET.SubElement(input_parameters, "search_keywords")
  child.text = param_list[4]
  child = ET.SubElement(input_parameters, "search_criteria")
  child.text = param_list[5]

  data_element_fixed_headers = getProperty("log_fileinfo", "data_element_fixed_headers").split(",")
  data_element_count_headers = getProperty("log_fileinfo", "data_element_count_headers").split(",")
  all_keyword_counts = output_list[0]
  log_count = ET.SubElement(results, "log_count")
  for all_keyword_count in all_keyword_counts:
    keyword_count_server = all_keyword_count[4]
    for keyword_count_server_row in keyword_count_server:
      if int(keyword_count_server_row[1]) > 0:
        log_count_item = ET.SubElement(log_count, "log_count_item")
        for i in range(len(all_keyword_count) - 1):
          child = ET.SubElement(log_count_item, data_element_fixed_headers[i].replace(" ", "_"))
          child.text = all_keyword_count[i]
        for i in range(len(keyword_count_server_row)):
          child = ET.SubElement(log_count_item, data_element_count_headers[i].replace(" ", "_"))
          child.text = (str(keyword_count_server_row[i]) if isinstance(keyword_count_server_row[i], int) else keyword_count_server_row[i])
  data_element_logmsg_headers = getProperty(param_list[3], "data_element_logmsg_headers").split(",")
  all_log_elements = output_list[1]
  log_data = ET.SubElement(results, "log_data")
  for all_log_element in all_log_elements:
    log_msg_list = all_log_element[4]
    for log_msg_list_row in log_msg_list:
      log_data_item = ET.SubElement(log_data, "log_data_item")
      for i in range(len(all_log_element) - 1):
        child = ET.SubElement(log_data_item, data_element_fixed_headers[i].replace(" ", ","))
        child.text = all_log_element[i]
      for i in range(len(log_msg_list_row)):
        child = ET.SubElement(log_data_item, data_element_logmsg_headers[i].replace(" ", "_"))
        child.text = log_msg_list_row[i]
  xml_tree_string = ET.tostring(results, "utf-8")
  return xml_tree_string

def writeTextOutput(param_list, output_list):
  output_header = ""
  all_log_elements = output_list[1]
  if len(all_log_elements) == 0:
    return
  log_filetype = param_list[3]
  data_element_fixed_headers = getProperty("log_fileinfo", "data_element_fixed_headers").split(",")
  data_element_logmsg_headers = getProperty(log_filetype, "data_element_logmsg_headers").split(",")
  output_filename = getProperty("log_fileinfo", "output_filename")
  for header in data_element_fixed_headers:
    if output_header == "":
      output_header = header
    else:
      output_header = output_header + """\t""" + header
  for header in data_element_logmsg_headers:
    if output_header == "":
      output_header = header
    else:
      output_header = output_header + """\t""" + header

  output_data = ""
  output_file = open(output_filename, "w")
  output_file.write(output_header)
  output_file.write('\n')
  for all_log_element in all_log_elements:
    log_msg_list = all_log_element[4]
    for log_msg_list_row in log_msg_list:
      output_data_row = ""
      for i in range(len(all_log_element) - 1):
        output_data_row = output_data_row + all_log_element[i] + """\t"""
      for i in range(len(log_msg_list_row)):
        output_data_row = output_data_row + log_msg_list_row[i] + """\t"""
      output_data_row = output_data_row.rstrip("\t")
      output_file.write(output_data_row)
      output_file.write('\n')
  output_file.close()

def sendEMailMessage(data):
  sent_from = getProperty("email_info", "email_sent_from") + "@" + socket.gethostname()
  email_recipient_list = getProperty("email_info", "email_recipient_list").split(",")
  output_filename = getProperty("log_fileinfo", "output_filename")
  msg = MIMEMultipart('alternative')
  msg['Subject'] = getProperty("email_info", "email_subject_header") + " " + time.strftime("%x %X")
  msg['From'] = sent_from
  msg['To'] = ",".join(email_recipient_list)
  msgType = MIMEText(data, 'html')
  msg.attach(msgType)
  if not getProperty("messages", "info_no_data_found") in data:
    fileName = output_filename
    f = file(fileName)
    attachFile = MIMEText(f.read())
    attachFile.add_header('Content-Disposition', 'attachment', filename=fileName)
    msg.attach(attachFile)
  s = smtplib.SMTP("localhost")
  s.sendmail(sent_from, email_recipient_list, msg.as_string())
  print getProperty("messages", "info_type") + " " + getProperty("messages", "info_email_sent")
  s.quit() 

if __name__ == "__main__":
  start_time = time.time()
  param_list = validateInputParameters()
  output_list = performProcessingLogData(param_list)
  html_message = buildHTMLOutput(param_list, output_list, False)
  end_time = time.time()
  mi, ss = divmod(end_time - start_time, 60)
  html_message = html_message.replace("$processing_time", getProperty("processing_info", "processing_time_header") + " " + str("%02dm %fs" %(mi, ss)))
  writeTextOutput(param_list, output_list)
  sendEMailMessage(html_message) 
  sys.exit()
