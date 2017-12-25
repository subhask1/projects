#!/usr/bin/env python

############################################################################
# Script Name:  LogSearchViewWeb.py
# Description:  This script enables Users to run the log search viewer script from the Web Browser
# Usage:	On Web Browser enter http://<host_name_fqdn>:<port>/LogSearchView after following the "Execution Steps" below
# Dependency:	
#		- Script File: LogSearchView.py on Same Directory Location
#		- Properties File: LogSearchView.properties
# Functionalities: 
#		- Accepts Input Parameters from HTML Form
#		- Invokes Relevant functions from LogSearchView.py to get log Information for all Servers
#		- Displays HTML Output on log Information along with Summary count for Keywords.
#		= Provides REST Service APIs to get Log Data in JSON and XML
# Parameters:
#		- Server Selection (Drop Down List)
#       - Log Type Selection (Drop Down List)
#		- Search Keywords (input text: e.g. stderr,error)
#		- Search Criteria (Drop Down List e.g. all or any)
# Installation:
#       - Logon to the Server
#       - Switch to Application/Service Account, if required
#       - Create a New directory
#       - Place LogSearchViewWeb.py, LogSearchView.properties and LogSearchView.py files inside the new Directory
# Execution Steps:
#       - Foreground: python /<New_Directory>/LogSearchViewWeb.py
#       - Background: nohup python <New_Directory>/LogSearchViewWeb.py > LogSearchViewWeb.log &
# Web URL:
#		- http://<host_name_fqdn>:<port>/LogSearchView
# REST Service APIs:
#		- http://<host_name_fqdn>:<port>/LogSearchView/rest/<output_format>/<env>/<cluster>/<server>/log_type/<search_keywords>/<search_criteria> 
#		  e.g. http://<host_name_fqdn>:<port>/LogSearchView/rest/json/itg/cluster1/all/managed_server_log/stderr,error/all
# Change History:
#	Initial:
#		- Date: 11/20/2017
############################################################################

import sys
import os
import time
from BaseHTTPServer import BaseHTTPRequestHandler,HTTPServer
from SocketServer import ThreadingMixIn
import cgi
import ConfigParser
import json
from LogSearchView import performProcessingLogData, buildHTMLOutput, buildJSONOutput, buildXMLOutput, writeTextOutput
from xml.dom import minidom

# Change Property file location if required
properties_file = "./LogSearchView.properties"
config = ConfigParser.ConfigParser()

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
  allow_reuse_address = True

def main():
  global properties_file, config
  try:
    config.read(properties_file)
    port_number = int(config.get("http_server", "port_number"))
    server = ThreadedHTTPServer(('', port_number), HTTPRequestHandler)
    print 'Started httpserver on port ',port_number
    server.serve_forever()
  except KeyboardInterrupt:
    print '^C received, shutting down the web server'
    server.socket.close()
    server.shutdown

class HTTPRequestHandler(BaseHTTPRequestHandler):

  html_html_open = """<!DOCTYPE html>\n \
		<html>\n"""
     
  html_head = """<head>\n \
	<title>View_log</title>\n \
        <meta content="IE=edge" http-equiv="X-UA-Compatible" />\n \
	</head>\n"""
  html_body_open = """<body>\n
        <div>
		<h1 style='text-align:center;height:20px;display:block;'>Log Search View</h1>"""
  html_note_text = """<br><br>\n \
        <b>Instructions: <a href='#' onclick="javascript:document.getElementById('LogSearchView_inst').style.display='';">Read Me</a></b>\n \
        <div id="LogSearchView_inst" style="display:none; border:1px solid black; width:950px; top:0; left:0; background:#f8f8f8; position:relative; z-index:10">\n \
        <table border="0" width="100%">\n \
          <tr><th>Log Search View</th></tr>\n \
          <tr><td><hr size="1"></td></tr>\n \
          <tr><td><b>Description: </b></td></tr>\n \
          <tr>\n \
            <td> \n \
              <ul style="margin:0">\n \
                <li>This Tool enable users to search Application Logs based on single or multiple keywords.</li>\n \
                <li>It produces output with Keyword Search Counts in HTML format with navigation to selected set of Log Messages.</li>\n \
              </ul>\n \
            </td>\n \
          </tr>\n \
          <tr><td><b>REST APIs: </b></td></tr>\n \
          <tr>\n \
            <td>\n \
              <ul style="margin:0">\n \
                <li>URL Structure: http://<Host_name_fqdn>:port/LogSearchView/rest/&lt;output_format&gt;/&lt;env&gt;/&lt;cluster&gt;/&lt;server&gt;/&lt;log_type&gt;/&lt;search_keywords&gt;/&lt;search_criteria&gt;</li>\n \
                <li>Parameters: &lt;output_format&gt;: json or xml; &lt;env&gt;: itg or prd; &lt;cluster&gt;: cluster1, cluster2, cluster3; &lt;server&gt;: Server Id e.g. server111 or all; &lt;log_type&gt;: access_log, db_log, managed_server_log or audit_log; &lt;search_keywords&gt;: Single or Multiple separated by comma e.g nullpointer or stderr,error; &lt;search_criteria&gt; all or any</li>\n \
                <li>Example: http://<Host_name_fqdn>:port/LogSearchView/rest/json/itg/cluster2/all/managed_server_log/stderr,error/all</li>\n \
              </ul>\n \
            </td>\n \
          </tr>\n \
          <tr><td><hr size="1"></td></tr>\n \
          <tr><td align="center"><input type="button" name="vol_button" id="vol_button" value="Close" onclick="document.getElementById('LogSearchView_inst').style.display='none';"></td></tr>\n \
        </table>\n \
        </div>\n \
        <br>\n \
        <font color='red'><b>Please Note:</b>\n
        <ul style='margin:0;'>\n
        <li>All Input Fields are Mandatory.</li>\n
        <li>Caution: If Log file size happens to be very large, the Search Criteria "Any" might cause longer time to get the Output Data.</li>\n
        </ul>\n
        </font>"""
  html_body_close = """</div>\n \
	</body>\n"""
  html_html_close = """</html>"""

  def set_HEADERS(self):
    self.send_response(200)
    self.send_header('Content-type', 'text/html')
    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
    self.send_header("Pragma", "no-cache")
    self.send_header("Expires", "0")
    self.end_headers()
	
  def do_GET(self):
    try:
      sendReply = False
      output_filename = self.getProperty("log_fileinfo", "output_filename")
      if self.path == "/LogSearchView":
        self.set_HEADERS()
        self.log_filename_from_web_list = self.buildServerList()
        html = self.buildHTML("")
        for line in html.splitlines():
          self.wfile.write(line)
      elif output_filename in self.path:
        with open(output_filename, "r") as f:
          self.send_response(200)
          self.send_header("Content-Type", 'application/text')
          self.send_header("Content-Disposition", 'attachment; filename=' + output_filename)
          self.end_headers()
          self.wfile.write(f.read())
      elif "LogSearchView/rest/" in self.path:
        input_params = []
        param_list = []
        input_params = self.path.rsplit("/", 7)
        output_type = input_params[1]
        param_list.append(input_params[2])
        param_list.append(input_params[3])
        param_list.append(input_params[4])
        param_list.append(input_params[5])
        param_list.append(input_params[6])
        param_list.append(input_params[7])
        self.send_response(200)
        if output_type.lower() == "json":
          self.send_header("Content-Type", 'application/json')
        elif output_type.lower() == "xml":
          self.send_header("Content-Type", 'application/xml')
        self.end_headers()
        output_list = performProcessingLogData(param_list)
        if output_type.lower() == "json":
          output_dict = buildJSONOutput(param_list, output_list)
          self.wfile.write(json.dumps(output_dict, sort_keys=True, indent=4, separators=(',', ': ')))
        elif output_type.lower() == "xml":
          output_xml = buildXMLOutput(param_list, output_list)
          self.wfile.write(minidom.parseString(output_xml).toprettyxml(indent = "    "))
      return
    except IOError:
      self.send_error(404,'Error in sending html: %s' % self.path)

  def getProperty(self, group, prop):
    global properties_file, config
    config.read(properties_file)
    return config.get(group, prop)

  def buildServerList(self):
    server_ddl = []
    server_ddl_all = []
    sorted_server_ddl = []
    environments = self.getProperty("environments", "env").split(",")
    # -- Build All Options --#
    for environment in environments:
      machines = self.getProperty("machine_info", environment).split(",")
      for machine in machines:
        clusters = self.getProperty(machine, "clusters").split(",")
        for cluster in clusters:
          servers = self.getProperty(machine, cluster).split(",")
          for server in servers:
            server_ddl_all_item = environment + ":all:" + cluster + ":all"
            if not server_ddl_all_item in server_ddl_all:
              server_ddl_all.append(server_ddl_all_item)
    # -- Build individual server options -- #
    for environment in environments:
      machines = self.getProperty("machine_info", environment).split(",")
      for machine in machines:
        clusters = self.getProperty(machine, "clusters").split(",")
        for cluster in clusters:
          servers = self.getProperty(machine, cluster).split(",")
          for server in servers:
            server_ddl_item = environment + ":" + machine + ":" + cluster + ":" + server
            server_ddl.append(server_ddl_item)
    # -- Build new Server DDL List sorted on env + cluster  + server -- #
    for server_ddl_all_item in server_ddl_all:
      all_option_list = server_ddl_all_item.split(":")
      for server_ddl_item in server_ddl:
        option_list = server_ddl_item.split(":")
        if all_option_list[0] == option_list[0] and all_option_list[2] == option_list[2]:
          if not server_ddl_all_item in sorted_server_ddl:
            sorted_server_ddl.append(server_ddl_all_item)
          sorted_server_ddl.append(server_ddl_item)
    return sorted_server_ddl

  def do_POST(self):
    if self.path=="/LogSearchView":
      start_time = time.time()
      form = cgi.FieldStorage( \
        fp=self.rfile, \
        headers=self.headers, \
        environ={'REQUEST_METHOD':'POST', 'CONTENT_TYPE':self.headers['Content-Type']}
        )
      param_list = []
      log_filename_from_web_items = form["log_filename_from_web"].value.split(":")
      param_list.append(log_filename_from_web_items[0].lower()) # Env
      param_list.append(log_filename_from_web_items[2]) # Cluster
      param_list.append(log_filename_from_web_items[3].lower()) # Managed Server
      param_list.append(form["log_filetype_from_web"].value.lower()) # Log File Type
      param_list.append(form["search_keywords_from_web"].value.lower()) # Search Keywords
      param_list.append(form["search_criteria_from_web"].value) # Search Criteria
      output_list = performProcessingLogData(param_list)
      html_message = buildHTMLOutput(param_list, output_list, True)
      writeTextOutput(param_list, output_list)  
      self.set_HEADERS()
      self.log_filename_from_web_list = self.buildServerList()
      html = self.buildHTML(html_message)
      end_time = time.time()
      mi, ss = divmod(end_time - start_time, 60)
      html = html.replace("$processing_time", self.getProperty("processing_info", "processing_time_header") + " " + str("%02dm %fs" %(mi, ss)))
      for line in html.splitlines():
        self.wfile.write(line)
      return
	  
  def buildHTML(self, output):
    html = "";
    html = html + self.html_html_open + self.html_head + self.html_body_open
    html = html + """<div id='input'>\n \
      <form name='LogSearchView' id='LogSearchView' method='POST'>\n \
	  <fieldset>\n \
	  <legend><b>Input Parameters</b></legend>\n"""
    html_server_ddl = """[env:machine:cluster:server]: <select name='log_filename_from_web' id='log_filename_from_web'>\n"""
    server_ddl = self.buildServerList()
    for server_ddl_item in server_ddl:
      html_server_ddl = html_server_ddl + """<option value='""" + server_ddl_item + """'>""" + server_ddl_item + """</option>\n"""
    html_server_ddl = html_server_ddl + """</select>\n"""
    html = html + html_server_ddl + "&nbsp;&nbsp;"
    html_log_filetypes = """Log Type <select name='log_filetype_from_web' id='log_filetype_from_web'>\n"""
    log_filetypes = self.getProperty("log_fileinfo", "log_filetype").split(",")
    for log_filetype in log_filetypes:
      html_log_filetypes = html_log_filetypes + """<option value='""" + log_filetype + """'>""" + log_filetype + """</option>\n"""
    html_log_filetypes = html_log_filetypes + """</select>\n"""
    html = html + html_log_filetypes + "&nbsp;&nbsp;"
    html_search_keywords_input = """Search Keywords (e.g. stderr,error): <input type='text' name='search_keywords_from_web' id='search_keywords_from_web' size='30' required />\n"""
    html = html + html_search_keywords_input + "&nbsp;&nbsp;"
    html_search_criteria = """Search Criteria: <select name='search_criteria_from_web' id='search_criteria_from_web'>\n""" 
    search_criteria = self.getProperty("log_fileinfo", "search_criteria").split(",")
    for search_criteria_item in search_criteria:
      html_search_criteria = html_search_criteria + """<option value='""" + search_criteria_item + """'>""" + search_criteria_item + """</option>\n"""
    html_search_criteria = html_search_criteria + """</select>\n"""
    html = html + html_search_criteria + "&nbsp;&nbsp;"
    html_submit = """<input type='submit' name='submit' id='submit' value='Submit'>"""
    html = html + html_submit
    html = html + self.html_note_text
    html = html + """</fieldset>\n \
      </form>\n"""
    html = html + """</div>\n"""
    if len(output) > 0:
      html = html + """<div id='output'>\n 
        <fieldset>\n 
        <legend><b>Output Result</b></legend>\n""" + output + """\n
        </fieldset>"""
      html = html + """</div>\n"""	  
    html = html + self.html_body_close + self.html_html_close
    return html

if __name__ == "__main__":
  main()
