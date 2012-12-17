
import os, sqlite3, re
import cgi, time, httplib,urllib,socket,string,sys,random
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from SocketServer import ThreadingMixIn
from xml.sax.saxutils import escape, quoteattr


databaseLoc = 'songs.db'

class Server():
	def __init__(self, ipAddress,port):
		self.remoteClient = ipAddress
		self.remotePort = port

class ThreadingServer(ThreadingMixIn,HTTPServer):
	pass

class reqHandler(BaseHTTPRequestHandler):
	
	#Standard get request
	def do_GET(self):
		try:
			
			#Set root path of server to player module
			if self.path == '/':
				self.path = '/player'

			#split path into array
			rString = self.path.split('/')
			#delete empty portion
			del rString[0]

			#Requst to player page
			if rString[0] == 'player':

				#Response header
				self.send_response(200)	#200 OK
				self.send_header('Content-type','text/html')
				self.end_headers()

				#Begin Content
				content = open('player.dyn').read()

				

				#Load song data
				dbm = DBManager(databaseLoc)
				songs = dbm.query("select title, album, artist, id from songs order by artist, album, id")

				songs = ",".join( [ "".join(str(s)) for s in songs])

				content = content.replace("$SongContent$","[%s]"%songs)
				
				
				self.wfile.write(content)

			#Media Streaming requests
			elif rString[0] == 'stream':
				#request for song media
				if rString[1] == 'song':
					
					#Get song id from request
					songId = int(rString[2])
					print songId
					#locate song
					dbm = DBManager(databaseLoc)
					filepath = dbm.query("select filepath from songs where id='%s';"%songId)
					
					#no results returned from database
					if filepath == []:
						self.do404()
						return

					filepath = filepath[0][0]

					#Header informaiton for song...
					self.send_response(200)		#200-OK
					self.send_header('Content-type','audio/mpeg')
					self.end_headers()		
					
					file = open(filepath)
					songData = file.read()

					#send data for streaming
					self.wfile.write(songData)

			elif rString[0] == 'tracks.xml':

				dbm = DBManager(databaseLoc)
				songs = dbm.query("select title, artist, album, id from songs order by artist, album")

				xml = "<songList>\n"
				for s in songs:

					if len(s) < 4:
						break

					tag = "<song><title>%s</title><id>%s</id><artist>%s</artist><album>%s</album></song>\n"%(
						self.cleanXML(s[0]),
						self.cleanXML(s[3]),
						self.cleanXML(s[1]),
						self.cleanXML(s[2])
						)
					
					xml += tag

				xml += "</songList>"

				#Response header
				self.send_response(200)	#200 OK
				self.send_header('Content-type','text/xml')
				self.end_headers()

				self.wfile.write(xml)

			elif rString[0][rString[0].rindex('.'):] == '.png':
				

				if( os.path.exists(rString[0])):
					#Response header
					self.send_response(200)	#200 OK
					self.send_header('Content-type','image/png')
					self.end_headers()
					file = open(rString[0])

					self.wfile.write(file.read())
				else:
					self.do404();
			else:
				self.do404()
				pass
		except IOError:
			self.do404()


	def do_HEAD(self):
		pass

	def doPOST(self):
		pass

	def do404(self):
		self.send_error(404,'Resource not found: %s' % (self.path))

	def cleanXML(self,s):

		s = escape( str(s), {"'":"&quot;"})
		try:
			s = unicode(s,errors='ignore')
		except Exception, e:
			print s, e
		return s


#DATABASE CLASSES
class DBManager:
	
	def __init__(self,database):
		self.database = database
		
		self.conn = sqlite3.connect(database)
		self.conn.text_factory = str
		self.c = self.conn.cursor()

	def query(self,qString):
		try:
			self.c.execute(qString)		
			return self.unpackData(self.c.fetchall())
		except Exception, e:
			print e
			#print sys.exec_info()[0]
			return []
			#self.c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
			#return self.c.fetchall()

	def unpackData(self, rows):
		list = []

		for row in rows:
			r = []
			for v in row:
				if type(v) == type(""):
					v = v.replace('\'\'',"\'")
				r.append(v)
			list.append(r)

		return list


class DatabaseBuilder:
	
	def __init__(self,database,musicFolder):
		self.database = database
		self.musicFolder = musicFolder

		self.initDB(database,musicFolder)
		#self.populateDB( self.scanFolder(musicFolder) )
	

	#Init our database
	def initDB(self,database,musicFolder=''):
		#Check if database exists, if so delete it and remake
		if os.path.exists(database) and database != ":memory:":
			#os.remove(database)
			self.conn = sqlite3.connect(database)
			c = self.conn.cursor()
			#return
		else:
			print "Generating"
			self.conn = sqlite3.connect(database)
			c = self.conn.cursor()
			try:
				c.execute('create table songs (title text, artist text, album text, year integer, genre integer, filepath text, id INTEGER PRIMARY KEY)');
				self.conn.commit()
			except:
				return
			print "Scanning %s"%musicFolder
			self.populateDB( self.scanFolder(musicFolder) )


	#Scan folder for mp3 files recursively
	def scanFolder(self,inDirectory,initialDir=""):
		
		if initialDir == "":
			initialDir = self.musicFolder

		files = []

		#SEARCH FILE DIRECTORY
		for item in os.listdir(inDirectory):
			#JOIN ITEMPATHS TO GLOBAL PATH
			itempath = os.path.join(inDirectory,item)
			
			#CHECK IF MP3 OR DIRECTORY
			#IS FILE?
			if os.path.isfile(itempath):
				#IS MP3?
				if self.isMP3(itempath):
					#ADD THIS FILE PATH TO LIST
					files.append(itempath)
				#TODO: ADD MORE MEDIA TYPES
			#IS DIRECTORY?
			elif os.path.isdir(itempath):
				#RECURSE DIRECTORIES AND MERGE WITH CURRENT LIST
				files = files + self.scanFolder(itempath,initialDir)
		
		#RETURN FILES
		return files
	
	#GET MP3 ID3 TAGS
	def getID3(self,filename):
		
		tags = {
			"title":"null",
			"artist":"null",
			"album":"null",
			"year":"null",
			"comment":"null",
			"genre":"null"
		}
	
		tagDataMap = {"title"   : (  3,  33, 'self.stripNulls'),
	                  "artist"  : ( 33,  63, 'self.stripNulls'),
	                  "album"   : ( 63,  93, 'self.stripNulls'),
	                  "year"    : ( 93,  97, 'self.stripNulls'),
	                  "comment" : ( 97, 126, 'self.stripNulls'),
	                  "genre"   : (127, 128, 'ord')}
		
		#Initialize and read file
		fp = open(filename, 'r')
		tagDataTop = fp.read(128)
		fp.seek(-128,2)
		tagDataBottom = fp.read(128)
		fp.close()
		
		id3Included = False;
	
		#Tag data
		for tagData in [tagDataBottom,tagDataTop]:
			if tagData[:3] == "TAG":
				for tag in tags:
					#convert and set tags
					tagRange = [ tagDataMap[tag][0], tagDataMap[tag][1] ]
					if tag == 'genre':
						tags[tag] = ord( tagData[tagRange[0]:tagRange[1]] )
					else:
						tags[tag] = self.stripNulls( tagData[tagRange[0]:tagRange[1]] )

				id3Included = True
				break
		
		tags['id3'] = id3Included
		return tags

#POPULATE SONG DATA INTO DATABASE
	def populateDB(self,files):
		
		index = 100000

		c = self.conn.cursor()
		commands = []
		for song in files:
			id3 = self.getID3(song)
			songIndex = -1
			albumIndex = -2
			artistIndex = -3
			
			for val in id3:
				if id3[val] == '':
					id3[val] = 'null'
	
	
			#check for flagged tags and fix...
			if id3['title'] == 'null':
				id3['title'] = song.split(os.sep)[songIndex]
			if id3['artist'] == 'null':
				id3['artist'] = song.split(os.sep)[artistIndex]
			if id3['album'] == 'null':
				id3['album'] = song.split(os.sep)[albumIndex]
			id3['title'] = re.sub('^\d\d -?\s?','',id3['title'])
			id3['year'] = re.sub('\D','',id3['year'])
			
			if id3['year'] == '':
				id3['year'] = 'null'

			vals = (
						self.clean(id3['title']),
						self.clean(id3['artist']),
						self.clean(id3['album']),
						self.clean(id3['year']),
						"%s"%id3['genre'],
						self.clean(song),
						index
						)

			commands.append( vals )
			index = index+1

			#enter data into database now
		try:
			self.conn.text_factory=str
			c.executemany( "INSERT INTO songs VALUES (?,?,?,?,?,?,?) ", commands )
		except sqlite3.Error, e:
			print e
			pass
	
		self.conn.commit()
	

	def stripNulls(self,data):
		return data.replace("\00", "").strip()
	
	def clean(self,string):
		return string.replace('\'','\'\'')

	def isMP3(self,file):
		if os.path.splitext(file)[-1] == '.mp3':
			return True
		return False

	def query(string):
		self.conn.cursor().execute(string)
		return self.conn.cursor().fetchall()		



def main():
	print "Initilizing database (this may take several minutes if not done before)"
	DBM = DatabaseBuilder(databaseLoc,'/Users/henryhhammond92/Music/')
	print "...finished."
	#start the server process...
	startServer()

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
			print "Attempting Connection to public network..."
			print
			
			#an outgoing connection will allow us to find our public address
			s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			s.connect(("google.com",80)) #get public IP address...
			
			print "...Connected to public network."
			
			print "Serving on the following URL:"
			print "http://%s:%s/"%(s.getsockname()[0],PORT)
			
		except:
			try:
				
				#connection to the outside world failed...
				#serve locally
				s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				s.connect(("127.0.0.1",80)) #get local IP address...
				
				print "...Could not connect to public network."
				print "serving locally."
				
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
	

if __name__ == "__main__":
	
	"""
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
	"""	
	#preprocessing work is complete... begin main functions
	main()
	
