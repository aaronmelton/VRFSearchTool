#!/usr/bin/env python
#
# VRFSearchTool.py
# Copyright (C) 2013 Aaron Melton <aaron(at)aaronmelton(dot)com>
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


import datetime	# Required for date format
import Exscript	# Required for SSH, queue & logging functionality
import os		# Required to determine OS of host
import re		# Required for REGEX operations

from datetime                   import datetime
from Exscript                   import Queue, Host, Logger
from Exscript.protocols 		import SSH2
from Exscript.util.file			import get_hosts_from_file
from Exscript.util.log          import log_to
from Exscript.util.decorator    import autologin
from Exscript.util.interact     import read_login
from Exscript.util.report		import status,summarize

def fileExist(fileName):
# This function checks the parent directory for the presence of a file
# Returns true if found, false if not

	try:
		# If file can be opened, it must exist
		with open(fileName, 'r') as openedFile:
			return 1	# File found

	# Exception: file cannot be opened, must not exist
	except IOError:
		return 0		# File NOT found

def upToDate(fileName):
# This function checks the modify date of the index file
# Returns true if file was last modified today, false if the file is older than today

	# If the modify date of the file is equal to today's date
	if datetime.fromtimestamp(os.path.getmtime(fileName)).date() == datetime.today().date():
		return 1	# File is "up-to-date" (modified today)

	# Else the modify date of the index file is not today's date
	else:
		return 0	# File is older than today's date

def confirm(prompt="", defaultAnswer="y"):
# This function prompts the user to answer "y" for yes or "n" for no
# Returns true if the user answers Yes, false if the answer is No
# The user will not be able to bypass this function without entering valid input: y/n

	while True:
		# Convert response to lower case for comparison
		response = raw_input(prompt).lower()
	
		# If no answer provided, assume Yes
		if response == '':
			return defaultAnswer
	
		# If response is Yes, return true
		elif response == 'y':
			return 1
	
		# If response is No, return false
		elif response == 'n':
			return 0
	
		# If response is neither Yes or No, repeat the question
		else:
			print "Please enter y or n."

def searchIndex(fileName):
# This function searches the index for search string provided by user and
# returns the results, if any are found

	# Ask the user to provide search string
	print
	searchString = raw_input("Enter the VRF Name or IP Address you are searching for: ")
	
	# Repeat the question until user provides ANY input
	while searchString == '':
		searchString = raw_input("Enter the VRF Name or IP Address you are searching for: ")
	
	# As long as the user provides ANY input, the application will search for it
	else:
		try:
			# If the index file can be opened, proceed with the search
			with open(fileName, 'r') as openedFile:
				# Quickly search the file for search string provided by user
				# If search string found in the file, we will search again to return the results
				# Otherwise inform the user their search returned no results
				if searchString in openedFile.read():
					openedFile.seek(0)	# Reset file cursor position
					searchFile = openedFile.readlines()	# Read each line in the file one at a time

					# Print table containing results
					print
					print "+--------------------+--------------------+--------------------+"
					print "|      VRF NAME      | REMOTE IP ADDRESS  |  LOCAL IP ADDRESS  |"
					print "+--------------------+--------------------+--------------------+"
	
					# Iterate through the file one at a time to find location of match
					for line in searchFile:
						if searchString in line:
							word = line.split(',')	# Split up matching line at the comments
							# Format the output to make it look pretty (not raw text)
							# Center text within column; Print word; Strip newline from last word
							print '|{:^20}|{:^20}|{:^20}|'.format(word[0], word[1], word[2].rstrip())
					# Close up the table after the search is complete
					print "+--------------------+--------------------+--------------------+"
	
				# Else: Search string was not found
				else:
					print "\nYour search string was not found in the index.\n"
	
		# Exception: index file was not able to be opened
		except IOError:
			print "\nAn error occurred opening the index file.\n"
							 
#@log_to(Logger())	# Logging decorator; Must precede buildIndex!
					# Logging (to screen) not useful unless # threads > 1
@autologin()		# Exscript login decorator; Must precede buildIndex!
def buildIndex(job, host, socket):
# This function builds the index file by connecting to the router and extracting all
# matching sections.  I chose to search for 'crypto keyring' because it is the only
# portion of a VPN config that contains the VRF name AND Peer IP.  Caveat is that
# the program temporarily captures the pre-shared key.  'crypto isakmp profile' was not
# a suitable query due to the possibility of multiple 'match identity address' statements

	print("Building index...")		# Let the user know the program is working dot dot dot
	socket.execute("terminal length 0")	# Disable user-prompt to page through config
										# Exscript doesn't always recognize Cisco IOS
										# for socket.autoinit() to work correctly

	# Send command to router to capture results
	socket.execute("show running-config | section crypto keyring")

	outputFile = file(indexFileTmp, 'a')	# Open output file (will overwrite contents)

	outputFile.write(socket.response)	# Write contents of running config to output file
	outputFile.close()					# Close output file
	socket.send("exit\r")				# Send the "exit" command to log out of router gracefully
	socket.close()						# Close SSH connection

	cleanIndex(indexFileTmp, host)		# Execute function to clean-up the index file
	
def cleanIndex(indexFileTmp, host):
# This function strips all the unnecessary information collected from the router leaving
# only the VRF name, remote Peer IP and local hostname or IP

	try:
		# If the temporary index file can be opened, proceed with clean-up
		with open(indexFileTmp, 'r') as srcIndex:

			try:
				# If the actual index file can be opened, proceed with clean-up
				# Remove unnecessary details from the captured config
				with open(indexFile, 'a') as dstIndex:
					# Use REGEX to step through config and remove everything but
					# the VRF Name, Peer IP & append router hostname/IP to the end
					a = srcIndex.read()
					b = re.sub(r'show running-config \| section crypto keyring.*', '', a)
					c = re.sub(r'crypto keyring ', '' ,b)
					d = re.sub(r'.(\r?\n)..pre-shared-key.address.', ',' ,c)
					e = re.sub(r'.key.*\r', ','+host.get_name() ,d)
					f = re.sub(r'.*#', '', e)
					dstIndex.write(f)

			# Exception: actual index file was not able to be opened
			except IOError:
				print "\nAn error occurred opening the index file.\n"

	# Exception: temporary index file was not able to be opened
	except IOError:
		print "\nAn error occurred opening the temporary index file.\n"
	
	# Always remove the temporary index file
	finally:
		os.remove(indexFileTmp)	# Critical to remove temporary file as it contains passwords!
			
def routerLogin():
# This function prompts the user to provide their login credentials and logs into each
# of the routers before calling the buildIndex function to extract relevant portions of
# the router config.  As designed, this function actually has the capability to login to
# multiple routers simultaneously.  I chose to not allow it to multi-thread given possibility
# of undesirable results from multiple threads writing to the same index file simultaneously

	try:# Check for existence of routerFile; If exists, continue with program
		with open(routerFile, 'r'): pass
		
		# Read hosts from specified file & remove duplicate entries, set protocol to SSH2
		hosts = get_hosts_from_file(routerFile,default_protocol='ssh2',remove_duplicates=True)
		userCreds = read_login()	# Prompt the user for his name and password
	
		queue = Queue(verbose=0, max_threads=1)	# Minimal message from queue, 1 threads
		queue.add_account(userCreds)			# Use supplied user credentials
		print	# Added to create some white space between prompts
		queue.run(hosts, buildIndex)			# Create queue using provided hosts
		queue.shutdown()						# End all running threads and close queue
		
		#print status(Logger())	# Print current % status of operation to screen
								# Status not useful unless # threads > 1

	# Exception: router file was not able to be opened
	except IOError:
		print "\nAn error occurred opening the router file.\n"


# Determine OS in use and clear screen of previous output
os.system('cls' if os.name=='nt' else 'clear')

print "VRF Search Tool v0.0.10-beta"
print "----------------------------"

# Change the filenames of these variables to suit your needs
routerFile='routers.txt'
indexFile='index.txt'
indexFileTmp='index.txt.tmp'

# START PROGRAM
# Steps below refer to documented program flow in VRFSearchTool.png
# Step 1: Check for presence of routerFile
# Does routerFile exist?
if fileExist(routerFile):
	# Step 2: Check for presence of indexFile file
	# Does indexFile exist?
	if fileExist(indexFile):
		# Step 3: Check date of file
		# File created today?
		if upToDate(indexFile):
			# Step 4: Prompt user to provide search string
			# Step 5: Search and return results, if any
			# END PROGRAM
			print
			print("--> Index found and appears up to date.")
			searchIndex(indexFile)
			print
		else: # if upToDate(indexFile):
			# Step 6: Ask user if they would like to update indexFile
			# Update indexFile?
			print
			if confirm("The index does not appear up-to-date.\n\nWould you like to update it? [Y/n] "):
				# Step 7: Prompt user for username & password
				# Step 8: Login to routers and retrieve VRF, Peer information
				# Step 9: Sort indexFile to remove unnecessary data
				# GOTO Step 2 (Check for presence of indexFile file)
				print
				# Remove old indexFile to prevent duplicates from being added by appends
				os.remove(indexFile)
				routerLogin()
				searchIndex(indexFile)
			else: # if confirm("Would you like to update the index? [Y/n] "):
				# GOTO Step 4: (Prompt user to provide search string)
				# Step 5: Search and return results, if any
				searchIndex(indexFile)
				print
	else: # if fileExist(indexFile):
		# Step 7: Prompt user for username & password
		# Step 8: Login to routers and retrieve VRF, Peer information
		# Step 9: Sort indexFile to remove unnecessary data
		# GOTO Step 2 (Check for presence of indexFile file)
		print
		print("--> No index file found, we will create one now.")
		print
		routerLogin()
		searchIndex(indexFile)
		
else: # if fileExist(routerFile):
	# Step 10: Create example routerFile and exit program
	# END PROGRAM	
	try:
		with open (routerFile, 'w') as exampleFile:
			exampleFile.write("192.168.1.1\n192.168.1.2\nRouterA\nRouterB\nRouterC\netc...")
			print
			print "Required file "+routerFile+" not found; One has been created for you."
			print "This file must contain a list, one per line, of Hostnames or IP addresses the"
			print "application will then connect to download the running-config."
			print
	except IOError:
		print
		print "Required file "+routerFile+" not found."
		print "This file must contain a list, one per line, of Hostnames or IP addresses the"
		print "application will then connect to download the running-config."
		print
