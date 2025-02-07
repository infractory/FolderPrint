#!/usr/bin/python

#########################################################################
# Initialization
#########################################################################

from ruamel.yaml import YAML
import yaml as std_yaml
#import jinja2, json

import sys, os, subprocess
import datetime, argparse
#import random, string, hashlib

import logging
from logging.handlers import SysLogHandler

# Python version of "file" Linux command, actually provided by system File package by default
import magic
# To get regexp
import re
# to get sleep()
import time
# to deal with cups printing system
import cups

#########################################################################
# Functions
#########################################################################

##############################
# Jinja
##############################

def jinja_templating(dirname, yaml_template, input_data):
  # Loading YAML file through jinja2... or something
  env = jinja2.Environment(loader=jinja2.FileSystemLoader(searchpath=dirname))
  template = env.get_template(yaml_template)

  # Rendering YAML file to set data
  yaml_data = yaml.load(template.render(input_data))
  return yaml_data

##############################
# FS stuffs
##############################

#   # Rights management
#   # TODO: develop some the set up ACLs on file system.

def makedirs(path):
  if(os.path.exists(path)):
    if(not os.path.isdir(path)):
      log("Error: " + path + " is not a directory.")
  else:
    if (config['script_behavior']['debug'] == True) and (not os.path.isdir(path)):
      log("creating directory: " + path)
    if (config['script_behavior']['Production_mode'] == True):
      os.makedirs(path, exist_ok=True)

def get_files_in_directory(dirname):
  f = []
  for (dirpath, dirnames, filenames) in os.walk(dirname):
    f.extend(filenames)
  return(f)

def move_file(file_object, destination_directory, suffix=''):
  file_src = file_object['fullname']
  if (suffix != ''):
    file_dst = destination_directory + "/"
    splitted_filename = file_object['filename'].split('.')
    splitted_parts_ct = len(splitted_filename)
    for i in range(splitted_parts_ct):
      if (i == 0):
        file_dst += splitted_filename[i]
      if (i != splitted_parts_ct - 1) and (i != 0):
        file_dst += '.' + splitted_filename[i]
      if (i == splitted_parts_ct - 1):
        file_dst += suffix + '.' + splitted_filename[i]
  else:
    file_dst = destination_directory + "/" + file_object['filename']
  os.rename(file_src, file_dst)
  file_object['filename'] = file_dst.split('/')[-1]
  file_object['fullname'] = file_dst
  return file_object

##############################
# Files to file_object
##############################

def get_file_objects_list_from_dir(config, data, printer_name, src_folder_key):
  # Get current files list
  src_files_list = get_files_in_directory(data['printers_list'][printer_name]['folders'][src_folder_key])

  file_objects_list = []

  for filename in src_files_list:
    file_object = {}
    file_object['filename'] = filename
    file_object['fullname'] = data['printers_list'][printer_name]['folders'][src_folder_key] + "/" + filename
    file_object['dirname']  = data['printers_list'][printer_name]['folders'][src_folder_key]
    file_object['mime']     = format(magic.detect_from_filename(data['printers_list'][printer_name]['folders'][src_folder_key] + "/" + filename).name)
    file_object['size']     = os.path.getsize(data['printers_list'][printer_name]['folders'][src_folder_key] + "/" + filename)
    file_object['date']     = datetime.datetime.now().isoformat()

    file_objects_list += [file_object]
  return file_objects_list

##############################
# Acting on files
##############################

def add_line_to_file(filename, line):
  with open(filename, 'a') as file:
    file.write(line + '\n')
  file.close()

##############################
# logging
##############################

def log(message, severity='info'):
  full_message = str(datetime.datetime.now().isoformat()) + " " + os.path.basename(sys.argv[0]) + ": " + message
  if (config['script_behavior']['debug'] == True) and (config['logging'] != "debug only"):
    print(full_message)
  match config['logging']:
    case "syslog":
      log_through_syslog(full_message, severity)
    case "debug only":
      print(full_message)
    case _:
      log_through_file(full_message, severity)
  return 0

def log_through_syslog(message, severity='info'):
  logger.info(message)
  return 0

def log_through_file(message, severity='info'):
  add_line_to_file(config['logging'], message)
  return 0

##############################
# Two functions to get a pseudo-service behavior
##############################

def wait(config):
  time.sleep(config['sleep_duration'])

def main(config, data, cups_conn):
  # For each declared printer, we act.
  for printer_name in data['printers_list'].keys():
    # date is regenerated for each printer to understand time needed to treat each one
    printer_date = datetime.datetime.now().isoformat()

    folders = {}
    # Set printer directories name
    folders['main_dir']           = config['folders']['main'] + "/" + printer_name
    folders['pdf_input']          = folders['main_dir'] + "/" + config['folders']['users_folders']['PDF_conversion']['01-input']
    folders['pdf_output']         = folders['main_dir'] + "/" + config['folders']['users_folders']['PDF_conversion']['02-output']
    folders['print_input']        = folders['main_dir'] + "/" + config['folders']['users_folders']['Direct_print']['01-input']
    folders['print_output']       = folders['main_dir'] + "/" + config['folders']['users_folders']['Direct_print']['02-output']

    folders['temp_dir']           = folders['main_dir'] + "/" + config['folders']['temp_folders']['main']
    folders['temp_file_to_pdf']   = folders['temp_dir'] + "/" + config['folders']['temp_folders']['PDF_conversion']['11-to_be_converted']
    folders['temp_pdf_to_print']  = folders['temp_dir'] + "/" + config['folders']['temp_folders']['PDF_conversion']['12-to_be_printed']
    folders['temp_file_to_print'] = folders['temp_dir'] + "/" + config['folders']['temp_folders']['Direct_print']['12-to_be_printed']

    data['printers_list'][printer_name]['folders'] = folders

    # Creating these directories if needed
    for dir_key, dir_name in folders.items():
      makedirs(dir_name)

    # Preparing list to host file (kind of) objects
    for key in folders.keys():
      if (key not in data['printers_list'][printer_name].keys()):
        data['printers_list'][printer_name][key] = []
    # Preparing list to host job (kind of) objects
    if ('jobs_list' not in data['printers_list'][printer_name].keys()):
      data['printers_list'][printer_name]['jobs_list'] = []

    # PDF conversion
    #
    # move files which are fully uploaded
    check_input_files(config, data, printer_name, 'pdf_input', 'temp_file_to_pdf')
    # convert files
    convert_to_pdf(config, data, printer_name, 'temp_file_to_pdf', 'temp_pdf_to_print')
    # printing files
    data['printers_list'][printer_name]['jobs_list'] += print_files(config, data, printer_name, 'temp_pdf_to_print', 'pdf_output', cups_conn)

    # Print files
    #
    # move files which are fully uploaded
    check_input_files(config, data, printer_name, 'print_input', 'temp_file_to_print')
    # printing files
    data['printers_list'][printer_name]['jobs_list'] += print_files(config, data, printer_name, 'temp_file_to_print', 'print_output', cups_conn)

    # Cleaning jobs
    remaining_job_id = cups_conn.getJobs().keys()
    for i in range(len(data['printers_list'][printer_name]['jobs_list'])):
      job = data['printers_list'][printer_name]['jobs_list'][i]
      if (job['job_number'] not in remaining_job_id):
        # moving file
        filename = job['fullname'].split('/')[-1]
        os.rename(job['fullname'], job['dest_dir'] + "/" + filename)
        # deleting job from jobs_list
        data['printers_list'][printer_name]['jobs_list'].pop(i)
  return 0

##############################
# PDF conversion and printing
##############################

def convert_to_pdf(config, data, printer_name, src_folder_key, dest_folder_key):
  # Get current file_objects list
  src_file_objects_list = get_file_objects_list_from_dir(config, data, printer_name, src_folder_key)

  for src_file_object in src_file_objects_list:
    # Converting file to PDF
    pdf_output_dir = data['printers_list'][printer_name]['folders'][dest_folder_key]
    log('For printer ' + printer_name + " converting " + src_file_object['fullname'] + " into " + pdf_output_dir)
    cmd_result = subprocess.run([config['path_to_libreoffice'], "--headless", "--convert-to", "pdf:writer_pdf_Export", src_file_object['fullname'], "--outdir", pdf_output_dir], capture_output=True, text=True)

    # as PDF is created in addition to source file, we remove source file is the commad returned 0
    if (cmd_result.returncode == 0):
      os.unlink(src_file_object['fullname'])

def print_files(config, data, printer_name, src_folder_key, dest_folder_key, cups_conn):
  # Get current file_objects list
  src_file_objects_list = get_file_objects_list_from_dir(config, data, printer_name, src_folder_key)

  jobs_list = {}

  for declared_printer_name, declared_printer_options in cups_conn.getPrinters().items():
    # Checking the printer is declared before sending print order
    if (declared_printer_name == printer_name):
      jobs_list = []

      for src_file_object in src_file_objects_list:
        # checking if current file was already pushed to this printer
        job_already_launched = False
        for job in data['printers_list'][printer_name]['jobs_list']:
          if (job['fullname'] == src_file_object['fullname']):
            job_already_launched = True
        # if not, launching the job
        if (job_already_launched == False):
          print_job = {}
          # Printing the document
          log('On printer ' + printer_name + ' printing ' + src_file_object['fullname'])
          print_job['job_number'] = cups_conn.printFile(printer_name, src_file_object['fullname'], " ", {})
          # getting information about that job
          print_job['fullname']   = src_file_object['fullname']
          print_job['dest_dir']   = data['printers_list'][printer_name]['folders'][dest_folder_key]
          # storing information about jobs
          jobs_list += [print_job]
      return jobs_list

##############################
# Controlling full upload of files
##############################

def check_input_files(config, data, printer_name, src_folder_key, dest_folder_key):
  # Memorize previously created file_objects list
  prev_file_objects_list = data['printers_list'][printer_name][src_folder_key]
  # Blanking the list in data object, it will be re-filled
  data['printers_list'][printer_name][src_folder_key] = []

  # Get current file_objects list
  src_file_objects_list = get_file_objects_list_from_dir(config, data, printer_name, src_folder_key)

  for cur_file_object in src_file_objects_list:
    prev_file_object_index = -1
    prev_file_object = {}

    # First, we check if cur_file_object is already into prev_file_objects_list
    for i in range(len(prev_file_objects_list)):
      if(prev_file_objects_list[i]['filename'] == cur_file_object['filename']):
        prev_file_object_index = i
        prev_file_object = prev_file_objects_list[i]

    # if prev_file_object_index == -1, that means cur_file_object is not present into the list
    # so we add this file_object to the list
    if(prev_file_object_index == -1):
      data['printers_list'][printer_name][src_folder_key] += [cur_file_object]

    # otherwise we check file size evolution size
    else:
      # if size did not changed, we move the file into next directory
      if (prev_file_object['size'] == cur_file_object['size']):
        suffix = "-" + cur_file_object['date']
        new_file_object = move_file(cur_file_object, data['printers_list'][printer_name]['folders'][dest_folder_key], suffix=suffix)
        data['printers_list'][printer_name][dest_folder_key] += [new_file_object]
        log('No size evolution for file: ' + cur_file_object['fullname'])
      # otherwise we replace the object into the list
      else:
        data['printers_list'][printer_name][src_folder_key][i] = cur_file_object
        log("Updating file information in list: " + cur_file_object['fullname'])

#########################################################################
# Start: initialization
#########################################################################

args_parser = argparse.ArgumentParser(description="A script to print files.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
args_parser.add_argument("-c", "--config_file", nargs=1, help='Path to config file.', required=True)
args_parser.add_argument("-l", "--printers_list_file", nargs=1, help='Path to printers list file.', required=True)
# args_parser.add_argument("-o", "--objects_desc_file", nargs='*', help='Path to objects description file.', required=True)

args = args_parser.parse_args()
args_vars = vars(args)

##############################
# Logging initialization
##############################

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = SysLogHandler(
  facility=SysLogHandler.LOG_DAEMON,
  address='/dev/log'
)
logger.addHandler(handler)

##############################
# YAML imports
##############################

yaml = YAML(typ='safe')
yaml.default_flow_style = False
yaml.default_flow_style = None

# NOTE: because nargs=1, args_vars['config_file'] is a list...
for config_file in args_vars['config_file']:
  with open(config_file, "r") as config_file_ptr:
    config = yaml.load(config_file_ptr)
  config_file_ptr.close()

#########################################################################
# Start: actions
#########################################################################

cups_conn = cups.Connection("localhost")

data = {}
data['printers_list'] = {}

# NOTE: because nargs=1, args_vars['printers_list_file'] is a list...
for printers_file in args_vars['printers_list_file']:
  with open(printers_file, "r") as config_file_ptr:
    for printer in config_file_ptr:
      # NOTE: rstrip() is there to remove blank trailing spaces but also "\n"
      data['printers_list'][printer.rstrip()] = {}
  config_file_ptr.close()


# Create main directory if needed
makedirs(config['folders']['main'])
# main temporary directory
makedirs(config['folders']['temp_folders']['main'])


while (True):
  main(config, data, cups_conn)
  wait(config)

