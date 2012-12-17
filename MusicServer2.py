

import os, sqlite3, re, cgi, time, urllib, string, socket, sys, random
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from SocketServer import ThreadingMixIn


#Init database
database = 'tmp.db'
#GLOBAL FILENAME HOLDER
musicFolder = ''

def initDB(database):
	#CHECK IF DATABASE EXISTS... IF SO DELETE IT
	if os.path.exists(database) and database != ":memory:":
		os.remove(database)
	
	#GENERATE DATABASE
	conn = sqlite3.connect(database)
	c = conn.cursor()
	try:
		#WRITE STRUCTURE TO DATABASE
		c.execute('create table songs (title text, artist text, album text, year integer, genre integer, id3 integer,filepath text)');
		conn.commit()
	except:
		pass

#CHECK IF FILE IS AN MP3
def isMP3(file):
	#CHECK LAST PART OF FILENAME
	if os.path.splitext(file)[-1] == '.mp3':
		return True;
	return False

#SCAN DIRECTORY FOR MP3 FILES
def scanFolder(inDirectory,initialDir):
	#PRE PROCESSING
	c = conn.cursor
	files = []

	#SEARCH FILE DIRECTORY
	for item in os.listdir(inDirectory):
		#JOIN ITEMPATHS TO GLOBAL PATH
		itempath = os.path.join(inDirectory,item)
		
		#CHECK IF MP3 OR DIRECTORY
		#IS FILE?
		if os.path.isfile(itempath):
			#IS MP3?
			if isMP3(itempath):
				#ADD THIS FILE PATH TO LIST
				files.append(itempath)
			#TODO: ADD MORE MEDIA TYPES
		#IS DIRECTORY?
		elif os.path.isdir(itempath):
			#RECURSE DIRECTORIES AND MERGE WITH CURRENT LIST
			files = files + scanFolder(itempath,initialDir)
	
	#RETURN FILES
	return files

#STRIP NULLS AND WHITESPACE FROM ID3
def stripNulls(data):
    return data.replace("\00", "").strip()

#GET MP3 ID3 TAGS
def getID3(filename):
	
	tags = {
		"title":"null",
		"artist":"null",
		"album":"null",
		"year":"null",
		"comment":"null",
		"genre":"null"
	}

	tagDataMap = {"title"   : (  3,  33, 'stripNulls'),
                  "artist"  : ( 33,  63, 'stripNulls'),
                  "album"   : ( 63,  93, 'stripNulls'),
                  "year"    : ( 93,  97, 'stripNulls'),
                  "comment" : ( 97, 126, 'stripNulls'),
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
				tags[tag] = eval(
					"%s(tagData[%s:%s])"%(tagDataMap[tag][2],tagRange[0],tagRange[1]),
					{},
					{'stripNulls':stripNulls,'ord':ord,'tagData':tagData} 
					)
			id3Included = True
			break
	
	tags['id3'] = id3Included

	#return tags
	return tags

#SANITIZE DATA FOR DATABASE
def clean(string):
	return string.replace('\'','\'\'')

#POPULATE SONG DATA INTO DATABASE
def populateDB(files):
	
	for song in files:
		id3 = getID3(song)
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
		
		
		#print song
		#print id3

		#enter data into database now
		try:
			query = "insert into songs values ('%s','%s','%s',%s,%s,%s,'%s');" % (
					clean(id3['title']),
					clean(id3['artist']),
					clean(id3['album']),
					clean(id3['year']),
					id3['genre'],
					1 if id3['id3'] else 0,
					clean(song)
					)

			c.execute(query)
			
		except sqlite3.Error, e:
			print "Eror occured with ",song, id3
			print e
			pass

	conn.commit()

if __name__ == "__main__":
	
	musicFolder = '/Users/henryhhammond92/Music/'
	initDB(database)
	files = scanFolder(musicFolder,musicFolder)
	populateDB(files)

