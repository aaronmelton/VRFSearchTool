#!/usr/bin/env python
#
# VRFSearchTool.py
# Copyright (C) 2013-2014 Aaron Melton <aaron(at)aaronmelton(dot)com>
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.


import argparse     # Required to read arguments from the command line
import base64       # Required to decode password
import datetime     # Required for date format
import ConfigParser # Required for configuration file
import Exscript     # Required for SSH, queue functionality
import re           # Required for REGEX operations
import sys          # Required for printing without newline
import os           # Required to determine OS of host

from argparse                   import ArgumentParser, RawDescriptionHelpFormatter
from base64                     import b64decode
from ConfigParser               import ConfigParser
from datetime                   import datetime
from Exscript                   import Account, Queue, Host, Logger
from Exscript.protocols         import SSH2
from Exscript.util.file         import get_hosts_from_file
from Exscript.util.log          import log_to
from Exscript.util.decorator    import autologin
from Exscript.util.interact     import read_login
from Exscript.util.report       import status,summarize
from re                         import search, sub
from sys                        import stdout
from os                         import getcwd, makedirs, name, path, remove, system


class Application:
# This class was created to provide me with an easy way to update application
# details across all my applications.  Also used to display information when
# application is executed with "--help" argument.
    author = "Aaron Melton <aaron@aaronmelton.com>"
    date = "(2014-03-17)"
    description = "Search for VRF names across multiple Cisco routers."
    name = "VRFSearchTool.py"
    url = "https://github.com/aaronmelton/VRFSearchTool"
    version = "v0.0.18-beta"


logger = Logger()   # Log stuff
@log_to(logger)     # Logging decorator; Must precede buildIndex!
@autologin()        # Exscript login decorator; Must precede buildIndex!
def buildIndex(job, host, socket):
# This function builds the index file by connecting to the router and extracting all
# matching sections.  I chose to search for "crypto keyring" because it is the only
# portion of a VPN config that contains the VRF name AND Peer IP.  Caveat is that
# the program temporarily captures the pre-shared key.  "crypto isakmp profile" was not
# a suitable query due to the possibility of multiple "match identity address" statements

    stdout.write(".")                   # Write period without trailing newline
    socket.execute("terminal length 0") # Disable user-prompt to page through config
                                        # Exscript doesn't always recognize Cisco IOS
                                        # for socket.autoinit() to work correctly

    # Send command to router to capture results
    socket.execute("show running-config | section crypto keyring")

    with open(indexFileTmp, "a") as outputFile:
        try:
            outputFile.write(socket.response)   # Write contents of running config to output file
        
        # Exception: indexFileTmp could not be opened
        except IOError:
            print
            print "--> An error occurred opening "+indexFileTmp+"."

    socket.send("exit\r")    # Send the "exit" command to log out of router gracefully
    socket.close()           # Close SSH connection

    cleanIndex(indexFileTmp, host)  # Execute function to clean-up the index file
    
def cleanIndex(indexFileTmp, host):
# This function strips all the unnecessary information collected from the router leaving
# only the VRF name, remote Peer IP and local hostname or IP

    try:
        # If the temporary index file can be opened, proceed with clean-up
        with open(indexFileTmp, "r") as srcIndex:

            try:
                # If the actual index file can be opened, proceed with clean-up
                # Remove unnecessary details from the captured config
                with open(indexFile, "a") as dstIndex:
                    # Use REGEX to step through config and remove everything but
                    # the VRF Name, Peer IP & append router hostname/IP to the end
                    a = srcIndex.read()
                    b = sub(r"show running-config \| section crypto keyring.*", "", a)
                    c = sub(r"crypto keyring ", "", b)
                    d = sub(r".(\r?\n)..pre-shared-key.address.", ",", c)
                    e = sub(r".key.*\r", ","+host.get_name(), d)
                    f = sub(r".*#", "", e)
                    dstIndex.write(f)

            # Exception: indexFile could not be opened
            except IOError:
                print
                print "--> An error occurred opening "+indexFile+"."

    # Exception: indexFileTmp could not be opened
    except IOError:
        print
        print "--> An error occurred opening "+indexFileTmp+"."
    
    # Always remove the temporary index file
    finally:
        remove(indexFileTmp)    # Critical to remove temporary file as it contains passwords!

def confirm(prompt="", defaultAnswer="y"):
# This function prompts the user to answer "y" for yes or "n" for no
# Returns true if the user answers Yes, false if the answer is No
# The user will not be able to bypass this function without entering valid input: y/n

    while True:
        # Convert response to lower case for comparison
        response = raw_input(prompt).lower()
    
        # If no answer provided, assume Yes
        if response == "":
            return defaultAnswer
    
        # If response is Yes, return true
        elif response == "y":
            return True
    
        # If response is No, return false
        elif response == "n":
            return False
    
        # If response is neither Yes or No, repeat the question
        else:
            print "Please enter y or n."

def fileExist(fileName):
# This function checks the parent directory for the presence of a file
# Returns true if found, false if not

    try:
        # If file can be opened, it must exist
        with open(fileName, "r") as openedFile:
            return True # File found

    # Exception: file cannot be opened, must not exist
    except IOError:
        return False    # File NOT found

def routerLogin():
# This function prompts the user to provide their login credentials and logs into each
# of the routers before calling the buildIndex function to extract relevant portions of
# the router config.  As designed, this function actually has the capability to login to
# multiple routers simultaneously.  I chose to not allow it to multi-thread given possibility
# of undesirable results from multiple threads writing to the same index file simultaneously

    try:# Check for existence of routerFile; If exists, continue with program
        with open(routerFile, "r"): pass
        
        # Read hosts from specified file & remove duplicate entries, set protocol to SSH2
        hosts = get_hosts_from_file(routerFile,default_protocol="ssh2",remove_duplicates=True)

        if username == "":          # If username is blank
            print
            account = read_login()  # Prompt the user for login credentials

        elif password == "":        # If password is blank
            print
            account = read_login()  # Prompt the user for login credentials

        else:                       # Else use username/password from configFile
            account = Account(name=username, password=b64decode(password))
        
        # Minimal message from queue, 1 threads, redirect errors to null
        queue = Queue(verbose=0, max_threads=1, stderr=(open(os.devnull, "w")))
        queue.add_account(account)              # Use supplied user credentials
        print
        stdout.write("--> Building index...")   # Print without trailing newline
        queue.run(hosts, buildIndex)            # Create queue using provided hosts
        queue.shutdown()                        # End all running threads and close queue

        # If logFileDirectory does not exist, create it.
        if not path.exists(logFileDirectory): makedirs(logFileDirectory)

        # Define log filename based on date
        logFilename = logFileDirectory+"VRFSearchTool_"+date+".log"

        # Check to see if logFilename currently exists.  If it does, append an
        # integer onto the end of the filename until logFilename no longer exists
        incrementLogFilename = 1
        while fileExist(logFilename):
            logFilename = logFileDirectory+"VRFSearchTool_"+date+"_"+str(incrementLogFilename)+".log"
            incrementLogFilename = incrementLogFilename + 1

        # Write log results to logFile
        with open(logFilename, "w") as outputLogFile:
            try:
                outputLogFile.write(summarize(logger))

            # Exception: router file was not able to be opened
            except IOError:
                print
                print "--> An error occurred opening "+logFileDirectory+logFile+"."

    # Exception: routerFile could not be opened
    except IOError:
        print
        print "--> An error occurred opening "+routerFile+"."

def searchIndex(fileName):
# This function searches the index for search string provided by user and
# returns the results, if any are found

    # Ask the user to provide search string
    print
    searchString = raw_input("Enter the VRF Name or IP Address you are searching for: ")
    
    # Repeat the question until user provides ANY input
    while searchString == "":
        searchString = raw_input("Enter the VRF Name or IP Address you are searching for: ")
    
    # As long as the user provides ANY input, the application will search for it
    else:
        try:
            # If the index file can be opened, proceed with the search
            with open(fileName, "r") as openedFile:
                # Quickly search the file for search string provided by user
                # If search string found in the file, we will search again to return the results
                # Otherwise inform the user their search returned no results
                if searchString in openedFile.read():
                    openedFile.seek(0)  # Reset file cursor position
                    searchFile = openedFile.readlines() # Read each line in the file one at a time

                    # Print table containing results
                    print
                    print "+--------------------+--------------------+--------------------+"
                    print "|      VRF NAME      | REMOTE IP ADDRESS  |  LOCAL IP ADDRESS  |"
                    print "+--------------------+--------------------+--------------------+"
    
                    # Iterate through the file one at a time to find location of match
                    for line in searchFile:
                        if searchString in line:
                            word = line.split(",")  # Split up matching line at the comments
                            # Format the output to make it look pretty (not raw text)
                            # Center text within column; Print word; Strip newline from last word
                            print "|{:^20}|{:^20}|{:^20}|".format(word[0], word[1], word[2].rstrip())
                    # Close up the table after the search is complete
                    print "+--------------------+--------------------+--------------------+"
    
                # Else: Search string was not found
                else:
                    print
                    print "--> Your search string was not found in "+indexFile+"."
    
        # Exception: indexFile could not be opened
        except IOError:
            print
            print "--> An error occurred opening "+indexFile+"."
                             
def upToDate(fileName):
# This function checks the modify date of the index file
# Returns true if file was last modified today, false if the file is older than today

    # If the modify date of the file is equal to today's date
    if datetime.fromtimestamp(path.getmtime(fileName)).date() == datetime.today().date():
        return True     # File is "up to date" (modified today)

    # Else the modify date of the index file is not today's date
    else:
        return False    # File is older than today's date


# Check to determine if any arguments may have been presented at the command
# line and generate help message for "--help" switch
parser = ArgumentParser(
    formatter_class=RawDescriptionHelpFormatter,description=(
        Application.name+" "+Application.version+" "+Application.date+"\n"+
        "--\n"+
        "Description: "+Application.description+"\n\n"+
        "Author: "+Application.author+"\n"+
        "URL:    "+Application.url
    ))
# Add additional argument to handle any optional configFile passed to application
parser.add_argument("-c", "--config", dest="configFile", help="config file", default="settings.cfg", required=False)
args = parser.parse_args()      # Set "args" = input from command line
configFile = args.configFile    # Set configFile = config file from command line OR "settings.cfg"

# Determine OS in use and clear screen of previous output
if name == "nt":    system("cls")
else:               system("clear")

# PRINT PROGRAM BANNER
print Application.name+" "+Application.version+" "+Application.date
print "-"*(len(Application.name+Application.version+Application.date)+2)


# START PROGRAM
# Steps below refer to documented program flow in VRFSearchTool.png
# Step 1: Check for presence of settings.cfg file
try:
# Try to open configFile
    with open(configFile, "r"): pass

# Step 2: Create example settings.cfg file
except IOError:
# Except if configFile does not exist, create an example configFile to work from
    try:
        with open (configFile, "w") as exampleFile:
            print
            print "--> Config file not found; Creating "+configFile+"."
            exampleFile.write("## VRFSearchTool.py CONFIGURATION FILE ##\n#\n")
            exampleFile.write("[account]\n#password is base64 encoded! Plain text passwords WILL NOT WORK!\n#Use website such as http://www.base64encode.org/ to encode your password\nusername=\npassword=\n#\n")
            exampleFile.write("[VRFSearchTool]\n#variable=C:\path\\to\\filename.ext\nrouterFile=routers.txt\nindexFile=index.txt\nindexFileTmp=index.txt.tmp\nlogFileDirectory=\n")
    
    # Exception: configFile could not be created
    except IOError:
        print
        print "--> An error occurred creating the example "+configFile+"."

# Step 3: Open settings.cfg file and read options
finally:
# Finally, using the provided configFile (or example created), pull values
# from the config and login to the router(s)
    config = ConfigParser(allow_no_value=True)
    config.read(configFile)
    username = config.get("account", "username")
    password = config.get("account", "password")
    routerFile = config.get("VRFSearchTool", "routerFile")
    indexFile = config.get("VRFSearchTool", "indexFile")
    indexFileTmp = config.get("VRFSearchTool", "indexFileTmp")
    logFileDirectory = config.get("VRFSearchTool", "logFileDirectory")

    # If logFileDirectory is blank, use current working directory
    if logFileDirectory == "":  logFileDirectory = getcwd()

    # If logFileDirectory does not contain trailing backslash, append one
    if logFileDirectory != "":
        if logFileDirectory[-1:] != "\\": logFileDirectory = logFileDirectory+"\\"
    
    # Define "date" variable for use in the output filename
    date = datetime.now()           # Determine today's date
    date = date.strftime("%Y%m%d")  # Format date as YYYYMMDD

    # Step 4: Check for presence of routerFile
    # Does routerFile exist?
    if fileExist(routerFile):
        # Step 5: Check for presence of indexFile file
        # Does indexFile exist?
        if fileExist(indexFile):
            # Step 6: Check date of file
            # File created today?
            if upToDate(indexFile):
                # Step 7: Prompt user to provide search string
                # Step 8: Search and return results, if any and END PROGRAM
                print
                print("--> Index found and appears up to date.")
                searchIndex(indexFile)
            else: # if upToDate(indexFile):
                # Step 9: Ask user if they would like to update indexFile
                # Update indexFile?
                print
                if confirm("--> The index does not appear up to date.\n\nWould you like to update it? [Y/n] "):
                    # Step 10: Prompt user for username & password (if not stored in settings.cfg)
                    # Step 11: Login to routers and retrieve VRF, Peer information
                    # Step 12: Sort indexFile to remove unnecessary data
                    # GOTO Step 2 (Check for presence of indexFile file)
                    # Remove old indexFile to prevent duplicates from being added by appends
                    remove(indexFile)
                    routerLogin()
                    print
                    searchIndex(indexFile)
                else: # if confirm("Would you like to update the index? [Y/n] "):
                    # GOTO Step 7: (Prompt user to provide search string)
                    # Step 8: Search and return results, if any and END PROGRAM
                    searchIndex(indexFile)
        else: # if fileExist(indexFile):
            # Step 10: Prompt user for username & password (if not stored in settings.cfg)
            # Step 11: Login to routers and retrieve VRF, Peer information
            # Step 12: Sort indexFile to remove unnecessary data
            # GOTO Step 2 (Check for presence of indexFile file)
            print
            print("--> No index file found, we will create one now.")
            routerLogin()
            print
            searchIndex(indexFile)
    else: # if fileExist(routerFile):
        # Step 13: Create example routerFile and exit program and END PROGRAM    
        try:
            with open (routerFile, "w") as exampleFile:
                print
                print "--> Router file not found; Creating "+routerFile+"."
                print "    Edit this file and restart the application."
                exampleFile.write("## VRFSearchTool.py ROUTER FILE ##\n#\n")
                exampleFile.write("#Enter a list of hostnames or IP Addresses, one per line.\n#For example:\n")
                exampleFile.write("192.168.1.1\n192.168.1.2\nRouterA\nRouterB\nRouterC\netc...")
        
        # Exception: routerFile could not be created
        except IOError:
            print
            print "--> Required file "+routerFile+" not found; An error has occurred creating "+routerFile+"."
            print "This file must contain a list, one per line, of Hostnames or IP addresses the"
            print "application will then connect to download the running-config."

print
print "--> Done."
raw_input() # Pause for user input.