#!/usr/bin/env python
#
# VRFSearchTool.py
# Copyright (C) 2012-2013 Aaron Melton <aaron(at)aaronmelton(dot)com>
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
# This function searches the index for search criteria provided by user and
# returns the results, if any are found

	searchCriteria = raw_input("--> Please enter your search criteria: ")
	try:
		# If the index file can be opened, proceed with the search
		with open(fileName, 'r') as openedFile:
			# Quickly search the file for search criteria provided by user
			# If search criteria found in the file, we will search again to return the results
			# Otherwise inform the user their search returned no results
			if searchCriteria in openedFile.read():
				openedFile.seek(0)	# Reset file cursor position
				# stripLine = openedFile.readline() <-- PULLS FIRST LINE OFF THE FILE, MAY NOT BE REQUIRED?
				searchFile = openedFile.readlines()	# Read each line in the file one at a time

				print
				print "+-----------+-----------------+-----------------+"
				print "| VRF NAME  | Remote Peer IP  |   Our Peer IP   |"
				print "+-----------+-----------------+-----------------+"

				# Iterate through the file one at a time to find location of match
				for line in searchFile:
					if searchCriteria in line:
						word = line.split(',')	# Split up matching line at the comments
						# Format the output to make it look pretty (not raw text)
						# Center text within column; Print word; Strip newline from last word
						print '|{:^11}|{:^17}|{:^17}|'.format(word[0], word[1], word[2].rstrip())
				print "+-----------+-----------------+-----------------+"

			# Else: Search criteria was not found
			else:
				print "\nYour search criteria was not found in the index.\n"

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
# the program briefly captures the pre-shared key.  'crypto isakmp profile' was not
# a suitable query due to the possibility of multiple 'match identity address' statements

	print("Building index...\n")		# Let the user know the program is working dot dot dot
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
	cleanIndex(indexFileTmp, host)		# Execute function to cleanup the index file
	
def cleanIndex(indexFileTmp, host):
# This function strips all the unnecessary information collected from the router leaving
# only the VRF name, remote Peer IP and local hostname or IP

	try:
		# If the temporary index file can be opened, proceed with cleanup
		with open(indexFileTmp, 'r') as srcIndex:

			try:
				# If the actual index file can be opened, proceed with cleanup
				# Remove unnecessary details from the captured config
				with open(indexFile, 'a') as dstIndex:
					# Use REGEX to step through config and remove everything but
					# the VRF Name, Peer IP & append router hostname/IP to the end
					a = srcIndex.read()
					b = re.sub(r'show running-config \| section crypto', '', a)
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
	try:# Check for existence of routerFile; If exists, continue with program
		with open(routerFile, 'r'): pass
		
		# Read hosts from specified file & remove duplicate entries, set protocol to SSH2
		hosts = get_hosts_from_file(routerFile,default_protocol='ssh2',remove_duplicates=True)
		userCreds = read_login()	# Prompt the user for his name and password
	
		queue = Queue(verbose=0, max_threads=1)	# Minimal message from queue, 1 threads
		queue.add_account(userCreds)			# Use supplied user credentials
		queue.run(hosts, buildIndex)			# Create queue using provided hosts
		queue.shutdown()						# End all running threads and close queue
		
		#print status(Logger())	# Print current % status of operation to screen
								# Status not useful unless # threads > 1

	# Exception: router file was not able to be opened
	except IOError:
		print "\nAn error occurred opening the router file.\n"


# Determine OS in use and clear screen of previous output
os.system('cls' if os.name=='nt' else 'clear')

print "VRFSearchTool.py v0.06"
print "----------------------"

routerFile='routers.txt'
indexFile='index.txt'
indexFileTmp='index.txt.tmp'

# START PROGRAM
# Step 1: Check for presence of routerFile
# Does routerFile exist?
print("START PROGRAM")
print("Step 1: Check for presence of "+routerFile+" file")
print("Does "+routerFile+" exist?")
if fileExist(routerFile):
	# Step 2: Check for presence of index.txt file
	# Does index.txt exist?
	print("<YES>") # routerFile exists
	print("Step 2: Check for presence of index.txt file")
	print("Does index.txt exist?")
	if fileExist(indexFile):
		# Step 3: Check date of file
		# File created today?
		print("<YES>") # index.txt exists
		print("Step 3: Check date of file")
		print("File created today?")
		if upToDate(indexFile):
			# Step 4: Prompt user to provide search criteria
			# Step 5: Search and return results, if any
			# END PROGRAM
			print("<YES>") # index.txt up to date
			print("Step 4: Prompt user to provide search criteria")
			print("Step 5: Search and return results, if any")
			searchIndex(indexFile)
			print("END PROGRAM")
		else: # if upToDate(indexFile):
			# Step 6: Ask user if they would like to update index.txt
			# Update index.txt?
			print("<NO>") # index.txt not up to date
			print("Step 6: Ask user if they would like to update index.txt")
			print("Update index.txt?")
			if confirm("Would you like to update the index? [Y/n] "):
				# Step 7: Prompt user for username & password
				# Step 8: Login to routers and retrieve VRF, Peer information
				# Step 9: Sort index.txt to remove unnecessary data
				# GOTO Step 2 (Check for presence of index.txt file)
				print("<YES>") # update index.txt
				print("Step 7: Prompt user for username & password")
				print("Step 8: Login to routers and retrieve VRF, Peer information")
				routerLogin()
				print("Step 9: Sort index.txt to remove unnecessary data")
				print("GOTO Step 2 (Check for presence of index.txt file)")
				searchIndex(indexFile)
			else: # if confirm("Would you like to update the index? [Y/n] "):
				# GOTO Step 4: (Prompt user to provide search criteria)
				# Step 5: Search and return results, if any
				print("<NO>") # don't update index.txt
				print("GOTO Step 4: (Prompt user to provide search criteria)")
				print("Step 5: Search and return results, if any")
				searchIndex(indexFile)
				print("END PROGRAM")
	else: # if fileExist(indexFile):
		# Step 7: Prompt user for username & password
		# Step 8: Login to routers and retrieve VRF, Peer information
		# Step 9: Sort index.txt to remove unnecessary data
		# GOTO Step 2 (Check for presence of index.txt file)
		print("<NO>") # index.txt does not exist
		print("Step 7: Prompt user for username & password")
		print("Step 8: Login to router and retrieve VRF, Peer information")
		routerLogin()
		print("Step 9: Sort index.txt to remove unnecessary data")
		print("GOTO Step 2 (Check for presence of index.txt file)")
		searchIndex(indexFile)
		
else: # if fileExist(routerFile):
	# Step 10: Create example routerFile and exit program
	# END PROGRAM	
	print("<NO>") # routerFile does not exist
	print("Step 10: Create example "+routerFile+" file and exit program")
	try:
		with open (routerFile, 'w') as exampleFile:
			exampleFile.write("192.168.1.1\n192.168.1.2\nRouterA\nRouterB\nRouterC\netc...")
			print "Required file "+routerFile+" not found; One has been created for you."
			print "This file must contain a list, one per line, of Hostnames or IP addresses the"
			print "application will then connect to download the running-config."
	except IOError:
		print "Required file "+routerFile+" not found."
		print "This file must contain a list, one per line, of Hostnames or IP addresses the"
		print "application will then connect to download the running-config."
	print("END PROGRAM")
