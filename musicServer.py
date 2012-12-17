
################################################################################
#
#	Copyright (C) 2011  Henry Hammond
#	email: HenryHHammond92@gmail.com
#	
#	This program is free software: you can redistribute it and/or modify
#	it under the terms of the GNU Lesser General Public License as published by
#	the Free Software Foundation, either version 3 of the License, or  any later
#	version.
#	
#	This program is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#	
#	For a copy of the GNU Lesser General Public License, see
#	<http://www.gnu.org/licenses/>.
#
################################################################################
#
#
#	To make this software work use the following syntax
#
#		python musicServer.py ~/Music/
#
#	where ~/Music/ is your music folder.
#
#
#	Note, streaming produces a lot of error messages, 
#
################################################################################
#
#This file contains all software to run on the server machine, player.html contains
#all software run on (served to) client machines.
#

import cgi, time, os, httplib, urllib, string, socket, sys, random
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from SocketServer import ThreadingMixIn
import sqlite3



#database = ':memory:'
database = 'tmp.db'

if os.path.exists(database) and database != ':memory:':
	os.remove(database)

conn = sqlite3.connect(database)
c = conn.cursor()
try:
	c.execute('create table songs (title text unique, format text)');
	conn.commit()
except:
	pass


musicFolder = ''

#Generic server class, which will be used to hold server details
class server():	
	def __init__(self,ipAddress,port):
		self.remoteClient = ipAddress
		self.remotePort = port
class ThreadingServer(ThreadingMixIn,HTTPServer):
	pass

class reqHandler(BaseHTTPRequestHandler):
	
	#Standard get requests handler
	def do_GET(self):
		try:				
			
			#if root directory of webserver, redirect to player
			if self.path == '/':
				self.path = '/player'
			
			#split path into array
			rString = self.path.split('/')
			#and delete the empty portion...
			del rString[0]
			
			#Request for player page
			if rString[0] == 'player':
				
				#Response Header
				self.send_response(200)		#200 - OK
				self.send_header('Content-type','text/html')
				self.end_headers()
				
				#Begin content
				#read basic player.html page...
				content = open('player.html').read()
				
				#load song data...
				if len(rString) == 2:
					songs = AudioPage(int(rString[1]),musicFolder)
				else:
					songs = AudioPage(20,musicFolder)
				
				#Inject song information into the page...
				content = content.replace("$SongContent$",str(songs))
				
				#Send page off to client...
				self.wfile.write(content)	
			
			#Request for streaming media...
			elif rString[0] == 'stream':
				
				if len(rString) >= (1+1):
					#Request for playlist...
					if rString[1] == 'plist':
						
						#Header information for a playlist...
						self.send_response(200)		#200 - OK
						self.send_header('Content-type','text/html')
						self.end_headers()	
						
						if len(rString) >= (1+2):
							length = int(rString[2]);
							self.wfile.write(createPlaylist(length,musicFolder))
						else:
							self.wfile.write(createPlaylist(10,musicFolder))
					
					#Request for song...
					if rString[1] == 'song':
						if len(rString)>=(1+2):
							
							#Header informaiton for song...
							self.send_response(200)		#200-OK
							self.send_header('Content-type','audio/mpeg')
							self.end_headers()
							
							#Decode URL data for request...
							file = os.sep.join(rString[2:])
							file = urllib.unquote(file)
							file = os.path.join(musicFolder,file)
							
							#Open file
							file = open(file)
							
							#Load data into memory
							songData = file.read()
							
							#Send data to Client for streaming
							self.wfile.write(songData)
			
			return
		except IOError:
			self.send_error(404,'Resource not found: %s' % (self.path))
	def do_HEAD(self):
		self.send_response(200)
		self.send_header('Content-type','text/html')
		self.end_headers()
	def do_POST(self):
		pass
			
#Check if file is an mp3 file... really basic
def isMP3(file):
	if os.path.splitext(file)[1] == '.mp3':
		return True
	return False

#Scan a directory to be added to database file
def scanFolder(indirectory,initialDir):
	
	#pre processsing...
	c = conn.cursor()
	files = ""
	
	#recursively check files
	for item in os.listdir(indirectory):		
		itempath = os.path.join(indirectory,item)
		try:
			if os.path.isfile(itempath) :
				# if mp3 insert into database
				if isMP3(itempath):
					song = itempath.replace(initialDir,'')
					song = song.replace('\'','\'\'')
					c.execute("insert into songs values ('%s','mp3');"%(song))
				
			elif os.path.isdir(itempath):
				#if folder recurse
				scanFolder(itempath,initialDir)
				conn.commit()
				#files = "%s%s"%(files, scanFolder(itempath,initialDir))
		except:pass	
	return files

#Create playlist data in utf-8 for broadcast
def createPlaylist(l,musicFolder):
	
	#preprocessing...
	songs = []
	songConn = conn
	songConn = sqlite3.connect(database)
	songConn.row_factory = sqlite3.Row
	cursor = songConn.cursor()
	#grab info from databse file...
	cursor.execute('select * from songs')
	
	#encode for web...
	for row  in cursor.fetchall():
		songs.append(row['title'].encode('utf-8'))
	
	#and return the data
	return songs
	
	#return scanFolder(musicFolder,musicFolder).split('\n')[1:]
	
#
def AudioPage(numSongs,musicFolder):
	
	songs = createPlaylist(numSongs,musicFolder)
	songlist = []
	
	for song in songs:
		txt = "\"%s\"," % song
		songlist.append(txt)
	
	return "\n".join(songlist)			

#Start the server process
def startServer():

	#prepare server details and requirements

	#get server port to broadcast on...
	print 'Select network port:'
	PORT = raw_input()

	#clean data to ensure a proper port is used 
	#note this software can run on port 80, standard http port
	PORT = PORT.strip()

	if len(PORT) >= 1: PORT = int(PORT)
	else : PORT = 10001						#Default to 10001
	
	#Now prepare to start the server
	try:
		
		
		print 'Starting server on port %s...'%PORT
		print 'This may take several seconds, depending on network speed'
		
		#Switched single HTTPServer for threaded server in order to make this
		#software handle multiple requests better.
		#requests on the server should probably be kept to low amount as
		#streaming may be memory intensive
		
		#server = HTTPServer(('',PORT),reqHandler)
		server = ThreadingServer(('',PORT),reqHandler)
		server.server_version = 'Custom Server - HHHMedia'
		
		#Do some magic and tell the user how to connect to this server...
		try:
			
			print
			print "Connecting to public network..."
			print
			
			#an outgoing connection will allow us to find our public address
			s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			s.connect(("google.com",80))
			
			print "...Connected to public network."
			
			print "Serving on the following URL:"
			print "http://%s:%s/"%(s.getsockname()[0],PORT)
			
		except:
			try:
				
				#connection to the outside world failed...
				#serve locally
				s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				s.connect(("127.0.0.1",80))
				
				print "...Could not connect to public network; serving locally."
				
				print "Serving on the following URL:"
				print "http://%s:%s/"%(s.getsockname()[0],PORT)
			except:
				pass
			pass
		
		#start the process
		server.server_activate()
		print
		#mission accomplished...
		server.serve_forever()
		
	#exit the program	
	except KeyboardInterrupt:
		print
		server.socket.close()
		print "Server stopped"
		#remove databse if not stored in memory
		if database != ':memory:':
			os.remove(database)
		
		
def main():

	#Scan music directory into database
	scanFolder(musicFolder,musicFolder)
	#commit database changes
	conn.commit()
	
	#start the server process...
	startServer()
	
if __name__ == "__main__":
	
	#prepare music folder
	if len(sys.argv) > 1:
		musicFolder = sys.argv[1]
	else:
		musicFolder = raw_input("Please enter your music folder: ")
		
		if len(musicFolder) == 0:
			musicFolder = '.'

	#ensure music folder path is in a proper format...
	if musicFolder[-1] != os.path.sep:
		musicFolder = "%s%s"%(musicFolder,os.path.sep)
		
	#preprocessing work is complete... begin main functions
	main()
	
	
